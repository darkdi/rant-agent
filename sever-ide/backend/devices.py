"""User-paired outbound desktop relay. No command redelivery after an uncertain action."""
import hashlib,json,secrets,sqlite3,time,uuid
from contextlib import contextmanager
from pathlib import Path
class AuthError(ValueError):
 def __init__(self,message,status=400):
  super().__init__(message);self.status=status

def hashed(value):return hashlib.sha256(value.encode()).hexdigest()
ACTIONS={'desktop_screenshot','desktop_click','desktop_type','desktop_hotkey','desktop_scroll'}
class Devices:
 def __init__(self,root):
  self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700);self.root.chmod(0o700);self.path=self.root/'devices.sqlite3'
  with self.db() as d:d.executescript('''PRAGMA journal_mode=WAL;
  CREATE TABLE IF NOT EXISTS pairs(code TEXT PRIMARY KEY,uid TEXT,expires REAL);
  CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,uid TEXT,token TEXT UNIQUE,name TEXT,seen REAL,armed INTEGER,revoked INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,device TEXT,action TEXT,args TEXT,status TEXT,result TEXT,created REAL);
  CREATE INDEX IF NOT EXISTS commands_device ON commands(device,status);
  ''')
 @contextmanager
 def db(self):
  d=sqlite3.connect(self.path,timeout=10);d.row_factory=sqlite3.Row
  try:
   with d:yield d
  finally:d.close()
 def pair(self,uid):
  code=secrets.token_hex(6).upper();now=time.time()
  with self.db() as d:
   d.execute('DELETE FROM pairs WHERE uid=? OR expires<?',(uid,now));d.execute('INSERT INTO pairs VALUES(?,?,?)',(hashed(code),uid,now+300))
  return {'code':code,'expires':now+300}
 def connect(self,code,name):
  if not isinstance(code,str) or len(code)!=12 or not isinstance(name,str):raise AuthError('Проверь код подключения.')
  now=time.time();token=secrets.token_urlsafe(32);id=uuid.uuid4().hex
  with self.db() as d:
   d.execute('BEGIN IMMEDIATE');p=d.execute('SELECT * FROM pairs WHERE code=? AND expires>?',(hashed(code.upper()),now)).fetchone()
   if not p:raise AuthError('Код истёк или уже использован.',403)
   if d.execute('SELECT COUNT(*) FROM devices WHERE uid=? AND revoked=0',(p['uid'],)).fetchone()[0]>=3:raise AuthError('Можно подключить до трёх компьютеров.')
   d.execute('DELETE FROM pairs WHERE code=?',(p['code'],));d.execute('INSERT INTO devices(id,uid,token,name,seen,armed) VALUES(?,?,?,?,?,0)',(id,p['uid'],hashed(token),name[:80] or 'Компьютер',now))
  return {'id':id,'token':token}
 def list(self,uid):
  with self.db() as d:rows=d.execute('SELECT id,name,seen,armed FROM devices WHERE uid=? AND revoked=0',(uid,)).fetchall()
  return [{**dict(r),'online':r['seen']>time.time()-15,'armed':bool(r['armed'])} for r in rows]
 def revoke(self,uid,id):
  with self.db() as d:
   d.execute('BEGIN IMMEDIATE');r=d.execute('SELECT id FROM devices WHERE id=? AND uid=?',(id,uid)).fetchone()
   if not r:raise AuthError('Компьютер не найден.',404)
   d.execute('UPDATE devices SET revoked=1,armed=0 WHERE id=?',(id,));d.execute("UPDATE commands SET status='revoked',result=NULL WHERE device=?",(id,))
 def authenticate(self,d,token):
  if not isinstance(token,str) or len(token)>200:raise AuthError('Нет доступа.',403)
  r=d.execute('SELECT * FROM devices WHERE token=? AND revoked=0',(hashed(token),)).fetchone()
  if not r:raise AuthError('Подключение отозвано. Создай новый код в Rant.',403)
  return r
 def poll(self,token,armed):
  now=time.time()
  with self.db() as d:
   d.execute('BEGIN IMMEDIATE');device=self.authenticate(d,token)
   d.execute('UPDATE devices SET seen=?,armed=? WHERE id=?',(now,int(armed is True),device['id']))
   d.execute('DELETE FROM commands WHERE created<?',(now-3600,))
   if armed is not True:
    d.execute("UPDATE commands SET status='stopped',result=NULL WHERE device=? AND status IN ('queued','delivered')",(device['id'],));return {'command':None}
   row=d.execute("SELECT * FROM commands WHERE device=? AND status='queued' AND created>? ORDER BY created LIMIT 1",(device['id'],now-30)).fetchone()
   if not row:return {'command':None}
   d.execute("UPDATE commands SET status='delivered' WHERE id=?",(row['id'],))
   return {'command':{'id':row['id'],'action':row['action'],'arguments':json.loads(row['args'])}}
 def result(self,token,id,result):
  if not isinstance(result,dict) or len(json.dumps(result))>1500000:raise AuthError('Ответ компьютера слишком большой.')
  with self.db() as d:
   d.execute('BEGIN IMMEDIATE');device=self.authenticate(d,token)
   row=d.execute('SELECT * FROM commands WHERE id=? AND device=?',(id,device['id'])).fetchone()
   if not row:raise AuthError('Команда не найдена.',404)
   if row['status']!='delivered':return {'ok':True} # late results never revive cancelled actions
   d.execute("UPDATE commands SET status='done',result=? WHERE id=?",(json.dumps(result),id))
  return {'ok':True}
 def stop(self,uid):
  with self.db() as d:d.execute("UPDATE commands SET status='stopped',result=NULL WHERE device IN (SELECT id FROM devices WHERE uid=?) AND status IN ('queued','delivered')",(uid,))
 def call(self,uid,action,args):
  if action not in ACTIONS or not isinstance(args,dict) or len(json.dumps(args))>20000:raise AuthError('Неверное действие компьютера.')
  now=time.time();id=uuid.uuid4().hex
  with self.db() as d:
   d.execute('BEGIN IMMEDIATE');rows=d.execute('SELECT * FROM devices WHERE uid=? AND revoked=0 AND armed=1 AND seen>?',(uid,now-15)).fetchall()
   if not rows:raise AuthError('Компьютер не готов. Открой Rant Connect и включи управление.',409)
   if len(rows)>1:raise AuthError('Активны несколько компьютеров. Оставь управление включённым только на нужном.',409)
   device=rows[0]
   if d.execute("SELECT COUNT(*) FROM commands WHERE device=? AND status IN ('queued','delivered') AND created>?",(device['id'],now-45)).fetchone()[0]:raise AuthError('Предыдущее действие ещё не завершено.',409)
   d.execute('INSERT INTO commands VALUES(?,?,?,?,?,?,?)',(id,device['id'],action,json.dumps(args),'queued',None,now))
  for _ in range(160):
   time.sleep(.25)
   with self.db() as d:
    row=d.execute('SELECT status,result FROM commands WHERE id=?',(id,)).fetchone()
    if not row:raise AuthError('Подключение прервано.',409)
    if row['status']=='done':
     result=json.loads(row['result']);d.execute('UPDATE commands SET result=NULL,status=? WHERE id=?',('consumed',id));return result
    if row['status'] in {'stopped','revoked'}:raise AuthError('Управление остановлено владельцем компьютера.',409)
  with self.db() as d:d.execute("UPDATE commands SET status='unknown',result=NULL WHERE id=? AND status IN ('queued','delivered')",(id,))
  raise AuthError('Компьютер не подтвердил результат. Действие могло выполниться: проверь экран перед повтором.',504)

DESKTOP_TOOLS=[
 {'name':'desktop_screenshot','description':'See a screenshot of the user-paired computer. Use only for the current task on that computer. Coordinates of later clicks use the returned image dimensions.','parameters':{'type':'object','properties':{}}},
 {'name':'desktop_click','description':'Click a point in the MOST RECENT screenshot. Read a new screenshot after navigation.','parameters':{'type':'object','properties':{'x':{'type':'integer','minimum':0},'y':{'type':'integer','minimum':0},'double':{'type':'boolean'}},'required':['x','y']}},
 {'name':'desktop_type','description':'Enter text into the focused field on the paired computer. Do not invent personal details.','parameters':{'type':'object','properties':{'text':{'type':'string','maxLength':8000}},'required':['text']}},
 {'name':'desktop_hotkey','description':'Press a keyboard shortcut on the paired computer, e.g. ctrl+l or command+l.','parameters':{'type':'object','properties':{'keys':{'type':'array','items':{'type':'string'},'minItems':1,'maxItems':3}},'required':['keys']}},
 {'name':'desktop_scroll','description':'Scroll the active window; positive steps scroll up, negative down.','parameters':{'type':'object','properties':{'steps':{'type':'integer','minimum':-10,'maximum':10}},'required':['steps']}}
]
