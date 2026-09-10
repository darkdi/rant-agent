"""Start only our owned bridge; preserve the installation's pairing token."""
import json,os,signal,subprocess,sys,time,urllib.request
from extension_bridge import BASE,CONFIG,PORT,WS_PORT,VERSION,BUILD

def bridge_status():
 try:
  req=urllib.request.Request(f'http://127.0.0.1:{PORT}/status',data=b'{}',headers={'X-Sever-Extension':CONFIG.read_text().strip()})
  with urllib.request.urlopen(req,timeout=.6) as r:
   state=json.load(r);return {**state,'running':True,'extension_path':str(BASE/'chrome-extension'),'http_port':PORT,'websocket_port':WS_PORT}
 except Exception:return {'connected':False,'running':False,'reason':'Подключение Chrome не запущено.','extension_path':str(BASE/'chrome-extension'),'http_port':PORT,'websocket_port':WS_PORT}

def ensure_bridge():
 CONFIG.parent.mkdir(exist_ok=True,mode=0o700)
 if not CONFIG.exists():
  import secrets
  CONFIG.write_text(secrets.token_urlsafe(32));CONFIG.chmod(0o600)
 config=BASE/'chrome-extension/config.js';config.write_text('const SEVER_TOKEN = '+json.dumps(CONFIG.read_text().strip())+';\n'+f'const SEVER_BRIDGE_HTTP = "http://127.0.0.1:{PORT}";\nconst SEVER_BRIDGE_WS = "ws://127.0.0.1:{WS_PORT}/extension";\n');config.chmod(0o600)
 current=bridge_status()
 if current.get('protocol')==VERSION and current.get('build')==BUILD:return current
 # A known previous bridge can be replaced; never kill an unrelated port owner.
 pidfile=BASE/'.local/extension-bridge.pid'
 if pidfile.exists():
  try:
   pid=int(pidfile.read_text());cmd=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
   if str(BASE/'backend/extension_bridge.py') in cmd:
    os.kill(pid,signal.SIGTERM)
    for _ in range(30):
     try:os.kill(pid,0)
     except ProcessLookupError:break
     time.sleep(.1)
  except (ValueError,OSError,subprocess.CalledProcessError):pass
 log=open(BASE/'.local/extension-bridge.log','a')
 p=subprocess.Popen([sys.executable,str(BASE/'backend/extension_bridge.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True);log.close()
 for _ in range(25):
  if p.poll() is not None:raise ValueError('Не удалось запустить подключение Chrome. Порт занят или отсутствует зависимость websockets.')
  status=bridge_status()
  if status.get('protocol')==VERSION and status.get('build')==BUILD:return status
  time.sleep(.1)
 raise ValueError('Подключение Chrome не ответило при запуске')

if __name__=='__main__':
 ensure_bridge();print('Подключение Chrome запущено. Загрузи расширение Rant Agent Local из папки chrome-extension и нажми «Подключить эту вкладку». Окно расширения можно закрыть.')
