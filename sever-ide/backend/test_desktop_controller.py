"""Exercise screen-coordinate math with fake GUI methods, never the real desktop."""
import ast
from pathlib import Path
import base64,io,platform,time,unittest
from unittest.mock import Mock
from PIL import Image

source=Path(__file__).resolve().parents[1]/'desktop-companion/rant_connect.py'
module=ast.parse(source.read_text());controller=next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='Controller')
namespace={'base64':base64,'io':io,'platform':platform,'time':time}
exec(compile(ast.Module(body=[controller],type_ignores=[]),str(source),'exec'),namespace)

class ControllerTests(unittest.TestCase):
 def setUp(self):
  self.gui=Mock();self.gui.screenshot.return_value=Image.new('RGB',(2800,2000));self.gui.size.return_value=(1400,1000);self.gui.KEYBOARD_KEYS=['ctrl','v','command']
  self.clipboard=Mock();self.controller=namespace['Controller'](self.gui,self.clipboard)
 def test_retina_coordinates_require_fresh_screen(self):
  with self.assertRaises(ValueError):self.controller.execute('desktop_click',{'x':1,'y':1})
  image=self.controller.execute('desktop_screenshot',{});self.assertEqual((image['width'],image['height']),(1400,1000))
  self.controller.execute('desktop_click',{'x':700,'y':500});self.assertEqual(self.gui.click.call_args.args,(700,500))
  with self.assertRaises(ValueError):self.controller.execute('desktop_click',{'x':700,'y':500})
 def test_outside_screen_and_invalid_keys_are_rejected(self):
  self.controller.execute('desktop_screenshot',{})
  with self.assertRaises(ValueError):self.controller.execute('desktop_click',{'x':1400,'y':500})
  with self.assertRaises(ValueError):self.controller.execute('desktop_hotkey',{'keys':['not-a-key']})
  self.gui.click.assert_not_called();self.gui.hotkey.assert_not_called()
 def test_clipboard_restored_even_if_paste_fails(self):
  self.clipboard.paste.return_value='previous clipboard';self.gui.hotkey.side_effect=RuntimeError('blocked')
  with self.assertRaises(RuntimeError):self.controller.execute('desktop_type',{'text':'test'})
  self.assertEqual(self.clipboard.copy.call_args.args,('previous clipboard',))

if __name__=='__main__':unittest.main()
