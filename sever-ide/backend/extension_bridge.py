"""Authenticated loopback WebSocket transport and per-command delivery receipts."""
import json,os,re,secrets,time,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from websockets.sync.server import serve
BASE=Path(__file__).resolve().parents[1]
CONFIG=BASE/'.local/extension-token'
from bridge_settings import PORT,WS_PORT
VERSION=3
BUILD=7

def token():return CONFIG.read_text().strip()

def safe_tab(tab):
 if not isinstance(tab,dict):return {}
 try:
  u=urlsplit(str(tab.get('url','')))
  if u.scheme!='https' or not u.hostname or u.username or u.password:return {}
  return {'url':u.scheme+'://'+u.netloc+u.path,'title':str(tab.get('title',''))[:160]}
 except ValueError:return {}

def safe_capabilities(value):
 return {k:value.get(k) is True for k in ('tabs','navigation','all_sites')} if isinstance(value,dict) else {}

class Broker:
 def __init__(self):
  self.lock=threading.RLock();self.ws=None;self.session=None;self.selection=None;self.seen=0;self.tab={};self.pending=None;self.version='';self.capabilities={};self.last_error='Подключи вкладку через расширение Rant Agent.'
 def status(self):
  with self.lock:
   connected=self.ws is not None and time.monotonic()-self.seen<35
   p=self.pending
   return {'protocol':VERSION,'build':BUILD,'capabilities':self.capabilities,'connected':connected,'session':self.session,'tab':self.tab,'version':self.version,'reason':'' if connected else self.last_error,'command':{k:p.get(k) for k in ('id','action','stage','seconds')} if p else None}
 def attach(self,ws,hello):
  with self.lock:
   old=self.ws
   if hello['selection']!=self.selection:
    self.session=secrets.token_hex(16);self.selection=hello['selection'];self.pending=None
   self.ws=ws;self.seen=time.monotonic();self.tab=hello['tab'];self.version=hello['version'];self.capabilities=hello.get('capabilities',{});self.last_error=''
   ws.send(json.dumps({'type':'ready','session':self.session,'protocol':VERSION}))
   # Delivery may have been interrupted. Extension journals IDs before executing.
   if self.pending and self.pending['stage'] in {'sent','received'} and self.pending['expires']>time.time():ws.send(json.dumps({'type':'command',**self.pending}))
  if old and old is not ws:old.close(1000,'Connection replaced')
 def message(self,ws,data):
  with self.lock:
   if self.ws is not ws:return
   self.seen=time.monotonic();p=self.pending
   if data.get('type')=='browser_state':
    self.tab=safe_tab(data.get('tab'));self.capabilities=safe_capabilities(data.get('capabilities'));return
   if data.get('type')=='ping':ws.send('{"type":"pong"}');return
   if data.get('type')=='disconnect':self.last_error='Вкладка отключена в расширении.';self.ws=None;ws.close();return
   if not p or data.get('id')!=p['id'] or p['stage'] in {'cancelled','done'}:return
   if data.get('type')=='received':p['stage']='received'
   if data.get('type')=='result':
    p.update(stage='done',result={k:data[k] for k in ('id','value','error','uncertain') if k in data},seconds=round(time.monotonic()-p['started'],2))
    ws.send(json.dumps({'type':'result_saved','id':p['id']}))
 def detach(self,ws):
  with self.lock:
   if self.ws is ws:self.ws=None;self.last_error='Связь с Chrome прервалась. Расширение переподключается; проверь его значок.'
 def submit(self,data):
  with self.lock:
   if data.get('session')!=self.session:raise ValueError('Подключение вкладки изменилось. Начни новую задачу.')
   if not self.status()['connected']:raise ValueError(self.last_error or 'Нет связи с расширением')
   if self.pending and self.pending['id']==data.get('id'):return {'ok':True}
   if self.pending and self.pending['stage'] in {'sent','received'}:raise ValueError('Предыдущее действие ещё выполняется')
   if data.get('action') not in {'snapshot','click','type','select','scroll','open','new_tab','tabs','switch'}:raise ValueError('Неизвестное действие')
   if not re.fullmatch('[a-f0-9]{32}',data.get('id','')) or not isinstance(data.get('args'),dict):raise ValueError('Некорректная команда')
   p={**data,'expires':min(float(data['expires']),time.time()+45),'stage':'sent','started':time.monotonic()};self.pending=p
   try:self.ws.send(json.dumps({'type':'command',**p}))
   except Exception:raise ValueError('Связь прервалась при передаче команды. Проверь вкладку перед повтором.') from None
   return {'ok':True}
 def receive(self,data):
  with self.lock:
   if data.get('session')!=self.session:raise ValueError('Вкладка переподключена. Начни задачу заново.')
   p=self.pending
   if not p or data.get('id')!=p['id']:raise ValueError('Команда больше не активна')
   return {'stage':p['stage'],'result':p.get('result'),'connected':self.status()['connected']}
 def cancel(self,data):
  with self.lock:
   p=self.pending
   if p and p['id']==data.get('id') and p['stage']!='done':
    p['stage']='cancelled'
    if self.ws:
     try:self.ws.send(json.dumps({'type':'cancel','id':p['id']}))
     except Exception:pass
   return {'ok':True}

BROKER=Broker()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  try:
   origin=self.headers.get('Origin','')
   if self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}' or (origin and not re.fullmatch(r'chrome-extension://[a-p]{32}',origin)) or not secrets.compare_digest(self.headers.get('X-Sever-Extension',''),token()):self.send_error(403);return
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=100000:raise ValueError('Размер запроса недопустим')
   data=json.loads(self.rfile.read(length))
   if not isinstance(data,dict):raise ValueError('Ожидается объект')
   if self.path=='/status':answer=BROKER.status()
   elif self.path=='/submit':answer=BROKER.submit(data)
   elif self.path=='/receive':answer=BROKER.receive(data)
   elif self.path=='/cancel':answer=BROKER.cancel(data)
   else:raise ValueError('Обнови расширение до версии 0.3: chrome://extensions → ↻, затем подключи вкладку.')
   code=200
  except (ValueError,TypeError,KeyError) as e:answer={'error':str(e)};code=400
  encoded=json.dumps(answer,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(encoded)));self.end_headers()
  try:self.wfile.write(encoded)
  except (BrokenPipeError,ConnectionResetError):pass

def ws_handler(ws):
 try:
  hello=json.loads(ws.recv(timeout=5))
  if hello.get('type')!='hello' or not secrets.compare_digest(str(hello.get('token','')),token()):ws.close(1008,'Authentication required');return
  if hello.get('protocol')!=VERSION:ws.close(1008,'Update extension');return
  if not re.fullmatch('[a-f0-9-]{36}',hello.get('selection','')):ws.close(1008,'Invalid selection');return
  hello['tab']=safe_tab(hello.get('tab'));hello['capabilities']=safe_capabilities(hello.get('capabilities'))
  BROKER.attach(ws,hello)
  for raw in ws:
   data=json.loads(raw)
   if isinstance(data,dict):BROKER.message(ws,data)
 except Exception:pass
 finally:BROKER.detach(ws)

def handshake(ws,request):
 if request.path!='/extension' or request.headers.get('Host')!=f'127.0.0.1:{WS_PORT}':return ws.respond(403,'Forbidden')

if __name__=='__main__':
 http=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
 with serve(ws_handler,'127.0.0.1',WS_PORT,origins=[re.compile(r'chrome-extension://[a-p]{32}')],process_request=handshake,max_size=100000,compression=None,close_timeout=1) as websocket:
  (BASE/'.local/extension-bridge.pid').write_text(str(os.getpid()))
  threading.Thread(target=websocket.serve_forever,daemon=True).start()
  http.serve_forever()
