import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from devices import Devices, AuthError

class DevicesTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.devices=Devices(self.tmp.name)
 def paired(self):
  pair=self.devices.pair('local');return self.devices.connect(pair['code'],'Test computer')
 def test_pair_once_expiry_and_user_isolation(self):
  code=self.devices.pair('local')['code'];self.devices.connect(code,'Test')
  with self.assertRaises(AuthError):self.devices.connect(code,'Again')
  self.assertEqual(self.devices.list('other'),[])
  with patch('devices.time.time',return_value=100):code=self.devices.pair('local')['code']
  with self.assertRaises(AuthError):self.devices.connect(code,'Expired')
 def test_revocation_rejects_existing_token(self):
  device=self.paired();self.devices.revoke('local',device['id'])
  with self.assertRaises(AuthError):self.devices.poll(device['token'],True)
  self.assertEqual(self.devices.list('local'),[])
 def test_disarmed_device_cannot_receive_action(self):
  device=self.paired();self.devices.poll(device['token'],False)
  with self.assertRaises(AuthError):self.devices.call('local','desktop_screenshot',{})
 def test_delivery_once_and_stop_does_not_revive(self):
  device=self.paired();self.devices.poll(device['token'],True);errors=[]
  def call():
   try:self.devices.call('local','desktop_click',{'x':1,'y':2})
   except AuthError as e:errors.append(str(e))
  worker=threading.Thread(target=call);worker.start()
  command=None
  for _ in range(50):
   command=self.devices.poll(device['token'],True)['command']
   if command:break
   time.sleep(.01)
  self.assertIsNotNone(command)
  self.assertIsNone(self.devices.poll(device['token'],True)['command'])
  self.devices.stop('local');self.devices.result(device['token'],command['id'],{'performed':True});worker.join(2)
  self.assertFalse(worker.is_alive());self.assertTrue(errors)
  with self.devices.db() as db:self.assertEqual(db.execute('SELECT status FROM commands WHERE id=?',(command['id'],)).fetchone()[0],'stopped')
 def test_result_returns_only_to_own_command(self):
  device=self.paired();self.devices.poll(device['token'],True);results=[]
  worker=threading.Thread(target=lambda:results.append(self.devices.call('local','desktop_screenshot',{})));worker.start()
  command=None
  for _ in range(50):
   command=self.devices.poll(device['token'],True)['command']
   if command:break
   time.sleep(.01)
  self.assertIsNotNone(command)
  other=self.paired()
  with self.assertRaises(AuthError):self.devices.result(other['token'],command['id'],{'image':'other'})
  self.devices.result(device['token'],command['id'],{'image':'synthetic'});worker.join(2)
  self.assertEqual(results,[{'image':'synthetic'}])
  with self.devices.db() as db:self.assertIsNone(db.execute('SELECT result FROM commands WHERE id=?',(command['id'],)).fetchone()[0])
 def test_multiple_armed_devices_are_not_guessed(self):
  for _ in range(2):self.devices.poll(self.paired()['token'],True)
  with self.assertRaises(AuthError):self.devices.call('local','desktop_screenshot',{})

if __name__=='__main__':unittest.main()
