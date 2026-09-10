"""Local-only IDE bridge. File writes are confined, version checked, and journaled."""
import io,zipfile
import argparse,fcntl,hashlib,json,mimetypes,os,re,secrets,shutil,signal,subprocess,sys,threading,time,uuid
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,unquote
from worker import Workspace,request_model,list_models,ASSISTANT,desktop_request
from local_runtime import LocalRuntime
from conversation import history_for,net_diff,export_conversation,chat_list
from agent_memory import get_memory,save_memory,memory_context
import attachments
from credentials import CredentialStore,origin
from setup_extension import bridge_status,ensure_bridge
import library
from workspace_tools import SITE,undo
from capabilities import prepare_release
from auto_context import options as context_options
from integrations import Connections
from media_local import MediaStudio
from devices import Devices,AuthError
HERE=Path(__file__).resolve().parents[1];DATA=Path(os.environ.get('RANT_DATA_DIR',str(HERE/'.local'))).resolve();DATA.mkdir(parents=True,exist_ok=True,mode=0o700)
CLOUD=False
os.environ.pop('RANT_MANAGED_URL',None)
os.environ.pop('RANT_MANAGED_TOKEN',None)
PROJECT_HOME=Path(os.environ.get('RANT_PROJECT_HOME',str(HERE/'projects'))).resolve()
PREVIEW_PORT=int(os.environ.get('RANT_PREVIEW_PORT','4312'))
def check_project(root):
 if CLOUD and (not root.is_relative_to(PROJECT_HOME) or root==PROJECT_HOME):raise PermissionError('Эта папка не принадлежит аккаунту')
 return root
def browser_state():
 return {'connected':False,'reason':'Chrome доступен в локальном приложении Rant Agent.'} if CLOUD else bridge_status()
def preview_url(name='index.html'):
 return '/preview/'+name if CLOUD else f'http://127.0.0.1:{PREVIEW_PORT}/'+name
RUNS=DATA/'runs';RUNS.mkdir(exist_ok=True);RELEASES=DATA/'releases';RELEASES.mkdir(exist_ok=True);TOKEN=secrets.token_urlsafe(32);MUTEX=threading.RLock();KEYS={};ACTIVE=None;PORT=4311
CREDENTIALS=CredentialStore(DATA/'credentials')
LOCAL=LocalRuntime(DATA,HERE/'backend/worker.py')
MEDIA=MediaStudio(DATA)
DEVICES=Devices(DATA/'devices')
class Conflict(ValueError):pass

def conversation_id(root=None):return load(DATA/'conversations.json',{}).get(str(root or project()),'legacy')

def persist(path,obj):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2));tmp.chmod(0o600);tmp.replace(path)

def load(path,default):
 try:return json.loads(path.read_text())
 except (OSError,ValueError):return default

def settings():return load(DATA/'settings.json',{})
def project():
 p=Path(settings().get('project',str(PROJECT_HOME/('Личные чаты' if CLOUD else 'demo')))).resolve()
 check_project(p)
 if not p.is_dir():raise ValueError('Папка проекта не найдена')
 return p

DEFAULT_PERMISSIONS={'files':'write','web':False,'release':False,'browser':False,'browser_auto':False}
def browser_access():
 saved=load(DATA/'browser-access.json',None)
 if isinstance(saved,dict):return {k:bool(saved.get(k)) for k in ('browser','browser_auto')}
 # Preserve the browser grant already given in this installation.
 previous=load(DATA/'permissions.json',{})
 if any(x.get('browser') for x in previous.values() if isinstance(x,dict)):
  return {'browser':True,'browser_auto':True}
 return {}

def permissions(root=None):
 return {**DEFAULT_PERMISSIONS,**load(DATA/'permissions.json',{}).get(str(Path(root or project()).resolve()),{}),**browser_access()}

def save_permissions(root,data):
 value={k:data.get(k,DEFAULT_PERMISSIONS[k]) for k in DEFAULT_PERMISSIONS}
 if value['files'] not in {'none','read','write'} or any(not isinstance(value[k],bool) for k in ('web','release','browser','browser_auto')):raise ValueError('Некорректные разрешения')
 if CLOUD and value['browser']:raise ValueError('Подключение личного Chrome доступно в локальном приложении.')
 if value['files']=='none':value['release']=False
 # Enabling browser access is the persistent grant; don't ask again on every action or project.
 value['browser_auto']=value['browser']
 items=load(DATA/'permissions.json',{});items[str(Path(root).resolve())]=value;persist(DATA/'permissions.json',items)
 persist(DATA/'browser-access.json',{k:value[k] for k in ('browser','browser_auto')})
 return value

def registered_projects():
 deleted=load(DATA/'deleted-projects.json',{});items=[x for x in load(DATA/'projects.json',[]) if x['path'] not in deleted];root=project()
 if str(root) not in deleted and not any(x['path']==str(root) for x in items):items.insert(0, {'name':root.name,'path':str(root)})
 return [x for x in items if Path(x['path']).is_dir()]

def register_project(root):
 check_project(root)
 previous=next((x for x in registered_projects() if x['path']==str(root)),None)
 items=[x for x in registered_projects() if x['path']!=str(root)]
 deleted=load(DATA/'deleted-projects.json',{});deleted.pop(str(root),None);persist(DATA/'deleted-projects.json',deleted)
 get_memory(root)
 items.insert(0,previous or {'name':root.name,'path':str(root)});persist(DATA/'projects.json',items[:30]);persist(DATA/'settings.json',{**settings(),'project':str(root)})

def create_project(data):
 name=data.get('name','').strip();parent=PROJECT_HOME if CLOUD else Path(data.get('parent') or PROJECT_HOME)
 if not name or len(name)>80 or not re.fullmatch(r'[\w][\w -]*',name) or name in {'.','..'}:raise ValueError('Название: буквы, цифры, пробелы, дефис; без слэшей и точек')
 if not parent.is_absolute() or not parent.is_dir():raise ValueError('Укажи существующую родительскую папку полным путём')
 root=parent.resolve()/name
 if root.exists():raise Conflict('Папка уже существует. Открой её или выбери другое название.')
 root.mkdir()

 register_project(root);return {'path':str(root),'files':Workspace(DATA/'inspection',root).files()}

BUILTIN_AGENTS=[{'id':'assistant','name':'Ассистент','mode':'chat','instruction':'Помогай с вопросами, текстами, идеями, планами и анализом. Не своди запросы пользователя к программированию.'},{'id':'browser','name':'Браузерный агент','mode':'browser','instruction':'Выполняй задания пользователя на разных сайтах. Проверяй результаты действий и сообщай о препятствиях.'},{'id':'developer','name':'Разработчик','mode':'edit','instruction':'Выполняй задачу небольшими правками. Читай фактические файлы, сохраняй существующее поведение и проверяй изменения.'},{'id':'reviewer','name':'Ревьюер','mode':'read','instruction':'Проверь проект, найди конкретные ошибки и укажи файлы. Не меняй код. Отделяй подтверждённые проблемы от предположений.'},{'id':'researcher','name':'Исследователь','mode':'read','instruction':'Используй доступные интернет-инструменты для поиска информации. Ссылайся на конкретные URL. Не выдумывай результаты поиска. Если инструмент отключён, объясни, какое разрешение или ключ требуется.'}]
def agents():return BUILTIN_AGENTS+load(DATA/'agents.json',[])
def get_agent(id):
 agent=next((x for x in agents() if x['id']==id),None)
 if not agent:raise ValueError('Агент не найден')
 return agent

def save_agent(data):
 name=data.get('name','').strip();instruction=data.get('instruction','').strip();mode=data.get('mode','read');id=data.get('id') or uuid.uuid4().hex
 if not re.fullmatch('[a-f0-9]{32}',id) or not name or len(name)>80 or len(instruction)>6000 or mode not in {'edit','read','chat','browser'}:raise ValueError('Проверь название, инструкции и режим агента')
 item={'id':id,'name':name,'instruction':instruction,'mode':mode};items=[x for x in load(DATA/'agents.json',[]) if x['id']!=id];items.append(item);persist(DATA/'agents.json',items);return item

def release_list(root):
 items=[load(p,{}) for p in RELEASES.glob('*.json')];return [x for x in items if x.get('root')==str(root)][-10:]

def profiles():
 local={'id':'local-9b','name':'Qwen 3.5 · 9B','kind':'local','model':'Qwen3.5-9B · MLX 4-bit','base_url':''}
 return ([] if CLOUD else [local])+[{**context_options(p),**p} for p in load(DATA/'profiles.json',[])]

def getprofile(id):
 p=next((dict(p) for p in profiles() if p['id']==id),None)
 if not p:raise ValueError('Подключение не найдено')
 p['key']=KEYS.get(id,'');return p

def run_path(id):
 if not isinstance(id,str) or not re.fullmatch('[a-f0-9]{32}',id):raise ValueError('Некорректный номер задачи')
 p=RUNS/id
 if not p.is_dir():raise ValueError('Задача не найдена')
 return p

def readrun(p,full=False):
 meta=load(p/'meta.json',{});report=load(p/'report.json',{})
 changes=load(p/'changes.json',[])
 running=ACTIVE is not None and ACTIVE['id']==p.name and ACTIVE['process'].poll() is None
 result={**meta,'status':'running' if running else report.get('status','interrupted'),'final':'' if running else report.get('final','Процесс завершился без итогового отчёта. Подробности в журнале.'),'changes':list(dict.fromkeys(c['path'] for c in changes))}
 if (p/'undone.txt').exists():result.update(changes=[],final='Правки задачи отменены.',status='undone')
 if running:result['pending']=load(p/'browser-pending.json',None)
 if full:result['partial']=load(p/'live.json',{}).get('text','') if running or result['status'] not in {'model_finished','validation_warnings','validation_failed'} else ''
 if full:result.update(log=(p/'output.log').read_text(errors='replace')[-18000:] if (p/'output.log').exists() else '',checks=report.get('checks',{}))
 return result

def state():
 root=project();runs=[p for p in RUNS.iterdir() if p.is_dir() and (p/'meta.json').exists()]
 runs.sort(key=lambda p:p.stat().st_mtime)
 return {'chats':chat_list(RUNS,root,conversation_id(root),load(DATA/'chat-index.json',{})),'browser':{k:v for k,v in browser_state().items() if k!='session'},'conversation':conversation_id(root),'local_model':LOCAL.state(),'projects':registered_projects(),'cloud':CLOUD,'project_home':str(PROJECT_HOME),'permissions':permissions(root),'search_has_key':bool(KEYS.get('brave-search')),'agents':agents(),'releases':release_list(root),'project':str(root),'files':Workspace(DATA/'inspection',root).files(),'profiles':[{**p,'has_key':bool(os.environ.get('RANT_MANAGED_URL') or KEYS.get(p['id']))} for p in profiles()], 'runs':[readrun(p) for p in runs if load(p/'meta.json',{}).get('root')==str(root) and load(p/'meta.json',{}).get('conversation','legacy')==conversation_id(root)], 'preview_url':preview_url() if (root/'index.html').is_file() else '', 'active':ACTIVE['id'] if ACTIVE and ACTIVE['process'].poll() is None else None}

def ensure_idle():
 if ACTIVE and ACTIVE['process'].poll() is None:raise Conflict('Дождись завершения агента или останови его')

def root_lock(root):
 path=ASSISTANT/'workspace.lock' if root==SITE.resolve() else root/'.agent.lock'
 f=path.open('a')
 try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:f.close();raise Conflict('Папка занята другим агентом. Закрой прежний Workspace.')
 return f

def validate_profile(data):
 kind=data.get('kind');url=data.get('base_url','').strip().rstrip('/')
 for suffix in ('/chat/completions','/messages','/models','/responses'):
  if url.endswith(suffix):url=url[:-len(suffix)];break
 u=urlsplit(url)
 if u.hostname=='api.timeweb.ai' and kind=='anthropic':kind='openai'
 if u.hostname=='api.anthropic.com':kind='anthropic'
 if u.hostname=='api.openai.com' and kind=='anthropic':kind='responses'
 if kind not in {'openai','anthropic','responses'}:raise ValueError('Неподдерживаемый тип API')
 if u.username or u.password or u.query or u.fragment or not u.hostname:raise ValueError('Укажи базовый адрес API без пароля и параметров')
 if CLOUD:
  from capabilities import public_endpoint
  public_endpoint(url)
 if u.scheme!='https' and not(u.scheme=='http' and u.hostname in {'127.0.0.1','localhost','::1'}):raise ValueError('Для удалённого API нужен HTTPS; HTTP разрешён только локально')
 name=data.get('name','').strip();model=data.get('model','').strip()
 if not name or not model or len(name)>120 or len(model)>200:raise ValueError('Заполни название подключения и модели')
 id=data.get('id') or uuid.uuid4().hex
 if not re.fullmatch('[a-f0-9]{32}',id):raise ValueError('Нельзя изменить встроенную модель')
 return {'id':id,'name':name,'kind':kind,'model':model,'base_url':url,**context_options(data)}

def finish_child(id,proc,handle,lock):
 global ACTIVE
 proc.wait();handle.close();p=RUNS/id
 with MUTEX:
  if not(p/'report.json').exists():persist(p/'report.json',{'status':'error' if proc.returncode else 'interrupted','final':'Процесс модели остановлен. Подробности в журнале.'})
  try:export_conversation(RUNS,Path(load(p/'meta.json',{})['root']),load(p/'meta.json',{}).get('conversation','legacy'))
  except (ValueError,OSError,KeyError):pass
  lock.close()
  if ACTIVE and ACTIVE['id']==id:ACTIVE=None

def launch(data):
 global ACTIVE
 ensure_idle();root=project();task=data.get('task','').strip();mode=data.get('mode','chat')
 if not task or len(task)>12000 or mode not in {'edit','read','chat','browser'}:raise ValueError('Укажи задачу до 12 000 символов')
 p=getprofile(data.get('profile_id'));access=permissions(root);agent=get_agent(data.get('agent_id','assistant'))
 if p['kind']=='local':LOCAL.ensure_available()
 if mode=='edit' and access['files']!='write':raise PermissionError('Для режима правки разреши изменение файлов в разделе «Доступы»')
 if mode=='read' and access['files']=='none':raise PermissionError('Для режима чтения разреши доступ к папке в разделе «Доступы»')
 if mode=='browser':
  if not access['browser']:raise PermissionError('Включи браузер в разделе «Доступы»')
  browser_state=bridge_status()
  if browser_state.get('protocol')!=3 or not browser_state.get('connected'):raise ValueError(browser_state.get('reason') or 'Подключи Chrome через расширение Rant Agent.')
  if not browser_state.get('capabilities',{}).get('tabs'):raise ValueError('Нужно обновить расширение: открой его значок в Chrome → «Обновить расширение», затем «Разрешить Chrome». Это один раз; сайты агент будет открывать сам.')
  if not browser_state.get('capabilities',{}).get('all_sites'):raise ValueError('В расширении Rant Agent нажми «Разрешить Chrome» и подтверди доступ к сайтам один раз. Затем агент сам открывает сайты и вкладки.')
 attached=attachments.selected(data.get('attachments',[]),root,conversation_id(root))
 if p['kind']=='local' and any(x['mime'].startswith('image/') for x in attached):raise ValueError('Этот локальный движок Qwen работает с текстом. Для картинок выбери API-модель с поддержкой зрения.')
 lock=root_lock(root);id=uuid.uuid4().hex;directory=RUNS/id;directory.mkdir()
 meta={'attachments':attached,'conversation':conversation_id(root),'id':id,'task':task,'profile':p['model'],'profile_id':p['id'],'root':str(root),'mode':mode,'agent':agent['name'],'permissions':access,'created':time.time()};persist(directory/'meta.json',meta)
 history=history_for(RUNS,root,conversation_id(root),mode,access,query=task,budget=5500 if p['kind']=='local' else 28000)
 opened=data.get('active_file','');view=data.get('view','code')
 if opened:
  try:
   candidate=Workspace(DATA/'inspection',root).path(opened)
   if not candidate.is_file():opened=''
  except (ValueError,OSError):opened=''
 ide_context={'model':p['model'],'mode':mode,'active_file':opened if access['files']!='none' and mode!='browser' else '', 'view':view if view in {'code','diff','log'} else 'code','history_tasks':len(history)//2,'screen_visible':False}
 meta['context']=ide_context;persist(directory/'meta.json',meta)
 config={'data_dir':str(DATA),'attachments':attached,'memory':memory_context(root,3500 if p['kind']=='local' else 18000),'conversation':conversation_id(root),'ide_context':ide_context,'browser_profile':str(DATA/'browser-profiles'/hashlib.sha256(str(root).encode()).hexdigest()[:16]),'permissions':access,'agent_instruction':agent['instruction'],'search_key':KEYS.get('brave-search',''),'release_dir':str(RELEASES),'preview_url':preview_url(),'root':str(root),'run':str(directory),'task':task,'profile':p,'mode':mode,'history':history}
 handle=(directory/'output.log').open('w')
 try:
  if p['kind']=='local':proc=LOCAL.submit(config)
  else:
   proc=subprocess.Popen([sys.executable,'-u',str(HERE/'backend/worker.py')],stdin=subprocess.PIPE,stdout=handle,stderr=subprocess.STDOUT,text=True,start_new_session=True,env={**os.environ,'RANT_DESKTOP_URL':f'http://127.0.0.1:{PORT}','RANT_DESKTOP_TOKEN':TOKEN})
   proc.stdin.write(json.dumps(config)+'\n');proc.stdin.close()
  ACTIVE={'id':id,'process':proc}
 except Exception:
  handle.close();lock.close();ACTIVE=None;raise
 threading.Thread(target=finish_child,args=(id,proc,handle,lock),daemon=True).start()
 return readrun(directory,True)

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send_json(self,obj,status=200):
  data=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def connector_download(self,kind):
  if kind not in {'desktop','browser'}:raise ValueError('Неизвестное подключение')
  if kind=='browser':ensure_bridge()
  folder=HERE/('desktop-companion' if kind=='desktop' else 'chrome-extension')
  names=['rant_connect.py','Start.command','requirements.txt','README.md'] if kind=='desktop' else ['manifest.json','config.js','background.js','navigation.js','page.js','controller.html','controller.js','popup.html','popup.js','style.css',*[f'icons/icon-{size}.png' for size in (16,32,48,128)]]
  buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED,strict_timestamps=False) as archive:
   for name in names:archive.write(folder/name,name)
   if kind=='desktop':archive.writestr('server.json',json.dumps({'url':f'http://127.0.0.1:{PORT}'}))
  raw=buffer.getvalue();self.send_response(200);self.send_header('Content-Type','application/zip');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
 def stream_run(self,id):
  p=run_path(id)
  with MUTEX:
   meta=load(p/'meta.json',{})
   if meta.get('root')!=str(project()) or meta.get('conversation','legacy')!=conversation_id():raise PermissionError('Ответ относится к другому чату')
  self.send_response(200);self.send_header('Content-Type','text/event-stream; charset=utf-8');self.send_header('Cache-Control','no-cache, no-store');self.send_header('X-Accel-Buffering','no');self.end_headers()
  previous='';last=time.monotonic()
  try:
   while True:
    with MUTEX:result=readrun(p,True)
    payload=json.dumps(result,ensure_ascii=False)
    if payload!=previous:
     self.wfile.write(('event: run\ndata: '+payload+'\n\n').encode());self.wfile.flush();previous=payload;last=time.monotonic()
    elif time.monotonic()-last>10:self.wfile.write(b': keepalive\n\n');self.wfile.flush();last=time.monotonic()
    if result['status']!='running':break
    time.sleep(.15)
  except (BrokenPipeError,ConnectionResetError):pass
 def guard(self,token=True):
  host=self.headers.get('Host','')
  allowed={f'127.0.0.1:{PORT}',f'localhost:{PORT}','127.0.0.1:4310','localhost:4310'}
  if host not in allowed:raise PermissionError('Недопустимый Host')
  origin=self.headers.get('Origin')
  if origin and origin not in {f'http://{x}' for x in allowed}:raise PermissionError('Недопустимый Origin')
  if self.headers.get('Sec-Fetch-Site')=='cross-site':raise PermissionError('Межсайтовый запрос отклонён')
  if token and not secrets.compare_digest(self.headers.get('X-Sever-Token',''),TOKEN):raise PermissionError('Обнови страницу IDE')
 def do_GET(self):
  try:
   u=urlsplit(self.path);q=parse_qs(u.query);route=u.path
   if route=='/auth/session':return self.send_json({'cloud':False,'user':None})
   if route=='/bridge/session':self.guard(False);return self.send_json({'token':TOKEN})
   if route.startswith('/bridge/'):
    self.guard()
    if route=='/bridge/connector-download':return self.connector_download(q.get('kind',[''])[0])
    if route=='/bridge/run-stream':return self.stream_run(q.get('id',[''])[0])
    if route=='/bridge/media-file':
     target=MEDIA.file(q.get('id',[''])[0]);raw=target.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(target)[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(raw)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
    with MUTEX:
     if route=='/bridge/state':result=state()
     elif route=='/bridge/devices':result=DEVICES.list('local')
     elif route=='/bridge/trash':result=library.trash(sys.modules[__name__])
     elif route=='/bridge/attachment':
      m,folder=attachments.load_attachment(q.get('id',[''])[0],project(),conversation_id(project()));raw=(folder/'data').read_bytes();self.send_response(200);self.send_header('Content-Type',m['mime']);self.send_header('Content-Length',str(len(raw)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
     elif route=='/bridge/integrations':result=Connections(DATA).public()
     elif route=='/bridge/media-profiles':result=MEDIA.catalog()
     elif route=='/bridge/media-jobs':result=MEDIA.jobs()
     elif route=='/bridge/export-chat':
      rows=[];root=project();cid=conversation_id(root)
      for folder in sorted(RUNS.iterdir(),key=lambda p:p.name):
       if not folder.is_dir():continue
       meta=load(folder/'meta.json',{})
       if meta.get('root')==str(root) and meta.get('conversation','legacy')==cid:
        report=load(folder/'report.json',{});rows.append({'created':meta.get('created',0),'model':meta.get('profile',''),'user':meta.get('task',''),'assistant':report.get('final',''),'status':report.get('status','running')})
      rows.sort(key=lambda x:x['created']);result={'format':'rant-chat-v1','conversation':cid,'messages':rows}
      if len(json.dumps(result).encode())>20000000:raise ValueError('Чат превышает 20 МБ. Обратись в поддержку для выгрузки.')
     elif route=='/bridge/memory':result=get_memory(project())
     elif route=='/bridge/file':
      name=q.get('path',[''])[0];w=Workspace(DATA/'inspection',project());result={'path':name,'content':w.read(name)}
     elif route=='/bridge/browser-status':result={k:v for k,v in browser_state().items() if k!='session'}
     elif route=='/bridge/run':result=readrun(run_path(q.get('id',[''])[0]),True)
     elif route=='/bridge/releases':result=release_list(project())
     elif route=='/bridge/release-download':
      id=q.get('id',[''])[0]
      if not re.fullmatch('[a-f0-9]{32}',id):raise ValueError('Некорректный архив')
      manifest=load(RELEASES/(id+'.json'),{})
      if manifest.get('root')!=str(project()):raise PermissionError('Архив относится к другой папке')
      data=(RELEASES/(id+'.zip')).read_bytes();self.send_response(200);self.send_header('Content-Type','application/zip');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data);return
     elif route=='/bridge/diff':
      p=run_path(q.get('id',[''])[0]);result={'diff':net_diff(load(p/'changes.json',[]),q.get('path',[None])[0]),'run_id':p.name}
     else:return self.send_json({'error':'Не найдено'},404)
    return self.send_json(result)
   self.guard(False)
   # Serve only compiled frontend assets; never project files or local settings.
   public=HERE/'dist/client';relative=unquote(u.path).lstrip('/') or 'index.html';target=(public/relative).resolve()
   if not target.is_relative_to(public.resolve()) or target.is_symlink():raise PermissionError('Недопустимый путь')
   if target.is_dir():target=target/'index.html'
   if not target.is_file():return self.send_json({'error':'Сначала собери интерфейс: npm run build'},404)
   data=target.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(target)[0] or 'application/octet-stream');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  except AuthError as e:self.send_json({'error':str(e)},e.status)
  except PermissionError as e:self.send_json({'error':str(e)},403)
  except (ValueError,OSError,KeyError) as e:self.send_json({'error':str(e)},400)
 def do_POST(self):
  try:
   route=urlsplit(self.path).path
   self.guard(not route.startswith('/device/'));n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=(12*1024*1024 if route in {'/bridge/attachment-upload','/device/result'} else 150000):raise ValueError('Запрос слишком большой или пустой')
   d=json.loads(self.rfile.read(n));route=urlsplit(self.path).path
   if not isinstance(d,dict):raise ValueError('Ожидается объект')
   if route.startswith('/device/'):
    token=self.headers.get('Authorization','').removeprefix('Bearer ')
    if route=='/device/connect':return self.send_json(DEVICES.connect(d.get('code'),d.get('name','Компьютер')))
    if route=='/device/poll':return self.send_json(DEVICES.poll(token,d.get('armed')))
    if route=='/device/result':return self.send_json(DEVICES.result(token,d.get('id'),d.get('result')))
    return self.send_json({'error':'Не найдено'},404)
   if route=='/bridge/desktop/status':return self.send_json({'ready':sum(x['online'] and x['armed'] for x in DEVICES.list('local'))==1})
   if route=='/bridge/desktop/cancel':DEVICES.stop('local');return self.send_json({'ok':True})
   if route=='/bridge/desktop':return self.send_json(DEVICES.call('local',d.get('action'),d.get('arguments')))
   with MUTEX:
    if route=='/bridge/device-pair':return self.send_json(DEVICES.pair('local'))
    if route=='/bridge/device-revoke':DEVICES.revoke('local',d.get('id'));return self.send_json({'ok':True})
    if route=='/bridge/media-profile':return self.send_json(MEDIA.save_profile(d))
    if route=='/bridge/media-create':return self.send_json(MEDIA.create(d))
    if route=='/bridge/integrations':
     if d.get('action')=='connect':ensure_idle()
     return self.send_json(Connections(DATA).change(d))
    if CLOUD and route=='/bridge/browser-reconnect':raise ValueError('Chrome доступен в локальном приложении.')
    if route=='/bridge/browser-reconnect':result={k:v for k,v in ensure_bridge().items() if k!='session'}
    elif route=='/bridge/attachment-upload':
     ensure_idle();result=attachments.upload(d,project(),conversation_id(project()))
    elif route=='/bridge/memory':
     ensure_idle();current=get_memory(project());key=d.get('key')
     if key not in current['documents']:raise ValueError('Неизвестный раздел памяти')
     if current['documents'][key]!=d.get('previous'):raise Conflict('Память изменилась. Открой её заново перед сохранением.')
     result=save_memory(project(),key,d.get('content'))
    elif route=='/bridge/run':result=launch(d)
    elif route=='/bridge/browser-decision':
     id=d.get('run_id');p=run_path(id)
     if not ACTIVE or ACTIVE['id']!=id or ACTIVE['process'].poll() is not None:raise Conflict('Задача уже завершена')
     pending=load(p/'browser-pending.json',{})
     if not pending or pending.get('id')!=d.get('id'):raise Conflict('Это действие уже не ожидает подтверждения')
     if d.get('decision') not in {'approve','approve_task','approve_project','reject'}:raise ValueError('Выбери выполнение или отказ')
     if (p/'browser-decision.json').exists():raise Conflict('Решение уже принято')
     decision=d['decision']
     if decision=='approve_project':
      if pending.get('action') in {'manual','question'}:raise ValueError('Для этого шага нужен ответ пользователя')
      save_permissions(project(),{**permissions(project()),'browser_auto':True});decision='approve_task'
     response=d.get('response','')
     if not isinstance(response,str) or len(response)>4000:raise ValueError('Ответ: до 4000 символов')
     if pending.get('action')=='question' and decision!='reject' and not response.strip():raise ValueError('Напиши ответ агенту')
     persist(p/'browser-decision.json',{'id':pending['id'],'decision':decision,'response':response});result={'ok':True}
    elif route=='/bridge/stop':
     DEVICES.stop('local')
     if ACTIVE and ACTIVE['id']==d.get('id'):
      proc=ACTIVE['process'];os.killpg(proc.pid,signal.SIGINT)
      if os.environ.get('RANT_MANAGED_URL'):
       try:desktop_request('cancel')
       except (ValueError,OSError):pass
      def later():
       try:proc.wait(timeout=8)
       except subprocess.TimeoutExpired:
        try:os.killpg(proc.pid,signal.SIGTERM)
        except ProcessLookupError:pass
      threading.Thread(target=later,daemon=True).start()
     result={'ok':True}
    elif route in {'/bridge/conversation-rename','/bridge/conversation-delete','/bridge/conversation-restore','/bridge/project-rename','/bridge/project-delete','/bridge/project-restore'}:
     result=library.change(sys.modules[__name__],route.rsplit('/',1)[-1],d)
    elif route=='/bridge/conversation-new':
     ensure_idle();root=project();id=uuid.uuid4().hex;items=load(DATA/'conversations.json',{});items[str(root)]=id;persist(DATA/'conversations.json',items)
     index=load(DATA/'chat-index.json',{});index.setdefault(str(root),{})[id]={'title':'Новый чат','created':time.time(),'updated':time.time()};persist(DATA/'chat-index.json',index);get_memory(root);result={'ok':True}
    elif route=='/bridge/conversation-select':
     ensure_idle();root=project();id=d.get('id');available=chat_list(RUNS,root,conversation_id(root),load(DATA/'chat-index.json',{}))
     if id not in {c['id'] for c in available}:raise ValueError('Чат не найден в этом проекте')
     items=load(DATA/'conversations.json',{});items[str(root)]=id;persist(DATA/'conversations.json',items);result={'ok':True}

    elif route=='/bridge/model-unload':
     ensure_idle();LOCAL.close();result={'ok':True}
    elif route=='/bridge/models':
     ensure_idle()
     if d.get('draft'):
      draft=d['draft'];p=validate_profile({**draft,'name':draft.get('name') or 'Модель','model':draft.get('model') or 'catalog'})
      old=next((x for x in profiles() if x['id']==p['id']),None)
      p['key']=draft.get('key') or (KEYS.get(p['id'],'') if old and origin(old['base_url'])==origin(p['base_url']) else '')
     else:p=getprofile(d.get('id'))
     result={'models':list_models(p)}
    elif route=='/bridge/project-create':
     ensure_idle();result=create_project(d)
    elif route=='/bridge/permissions':
     ensure_idle();result=save_permissions(project(),d)
     if d.get('search_key') or d.get('clear_search_key'):
      CREDENTIALS.update('brave-search','https://api.search.brave.com',d.get('search_key'),bool(d.get('clear_search_key')));KEYS['brave-search']=CREDENTIALS.get('brave-search','https://api.search.brave.com')
    elif route=='/bridge/agent':
     ensure_idle();result=save_agent(d)
    elif route=='/bridge/release':
     ensure_idle();root=project()
     if not permissions(root)['release']:raise PermissionError('Разреши подготовку публикации в разделе «Доступы»')
     lock=root_lock(root)
     try:result=prepare_release(root,d.get('directory','.'),RELEASES)
     finally:lock.close()
    elif route=='/bridge/project':
     ensure_idle();raw=d.get('path','')
     if not Path(raw).is_absolute():raise ValueError('Нужен полный путь к папке')
     root=check_project(Path(raw).resolve())
     if not root.is_dir() or root==Path.home() or root==Path('/') or root==HERE or root==DATA:raise ValueError('Выбери отдельную папку проекта')
     register_project(root);result={'ok':True}
    elif route=='/bridge/profile':
     ensure_idle();p=validate_profile(d);old=next((x for x in profiles() if x['id']==p['id']),None)
     CREDENTIALS.update(p['id'],p['base_url'],d.get('key'),bool(d.get('clear_key')))
     items=[x for x in profiles() if x['kind']!='local' and x['id']!=p['id']];items.append(p);persist(DATA/'profiles.json',items)
     KEYS[p['id']]=CREDENTIALS.get(p['id'],p['base_url'])
     result={**p,'has_key':bool(os.environ.get('RANT_MANAGED_URL') or KEYS.get(p['id']))}
    elif route=='/bridge/probe':
     ensure_idle();p=getprofile(d.get('id'))
     if p['kind']=='local':
      LOCAL.ensure_available();result={'message':'Файлы модели и MLX найдены. Загрузка проверяется при запуске задачи.'}
     else:
      response=request_model(p,[{'role':'user','content':'Ответь только: OK'}],max_tokens=1024);result={'message':'API ответил: '+response['content'][:120]+'. Вызовы инструментов этим запросом не проверялись.'}
    elif route=='/bridge/file':
     ensure_idle();root=project();lock=root_lock(root)
     try:
      id=uuid.uuid4().hex;p=RUNS/id;p.mkdir();w=Workspace(p,root);name=d['path'];previous=d.get('previous')
      current=w.path(name).read_text() if w.path(name).exists() else None
      if previous!=current:raise Conflict('Файл изменился. Обнови его перед сохранением.')
      result=w.write(name,d['content'],previous)
      persist(p/'meta.json',{'id':id,'task':'Ручная правка: '+name,'profile':'Редактор','root':str(root),'mode':'manual','created':time.time()})
      persist(p/'report.json',{'status':'model_finished','final':'Файл сохранён в редакторе.'})
     finally:lock.close()
    elif route=='/bridge/undo':
     ensure_idle();p=run_path(d.get('id'));root=Path(load(p/'meta.json',{})['root'])
     if root!=project():raise ValueError('Сначала открой папку этой задачи')
     if(p/'undone.txt').exists():raise ValueError('Эта задача уже отменена')
     lock=root_lock(root)
     try:result={'files':undo(p,root)}
     finally:lock.close()
    else:return self.send_json({'error':'Не найдено'},404)
   self.send_json(result)
  except AuthError as e:self.send_json({'error':str(e)},e.status)
  except PermissionError as e:self.send_json({'error':str(e)},403)
  except Conflict as e:self.send_json({'error':str(e)},409)
  except (ValueError,KeyError,OSError,TypeError) as e:self.send_json({'error':str(e)},400)

class PreviewHandler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  try:
   if self.headers.get('Host') not in {f'127.0.0.1:{PREVIEW_PORT}',f'localhost:{PREVIEW_PORT}'}:raise PermissionError()
   root=project();raw=unquote(urlsplit(self.path).path).lstrip('/') or 'index.html';relative=Path(raw)
   if relative.is_absolute() or any(part.startswith('.') for part in relative.parts):raise PermissionError()
   target=root/relative
   for component in [target,*target.parents]:
    if component==root:break
    if component.is_symlink():raise PermissionError()
   target=target.resolve()
   if not target.is_relative_to(root):raise PermissionError()
   if target.is_dir():target=target/'index.html'
   if target.suffix.lower() not in {'.html','.css','.js','.svg','.png','.jpg','.jpeg','.webp','.gif','.ico','.woff','.woff2','.ttf','.mp4','.webm'}:raise PermissionError()
   if not target.is_file():self.send_error(404,'File not found');return
   if target.stat().st_size>25_000_000:raise PermissionError()
   content=target.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(target)[0] or 'application/octet-stream');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
  except PermissionError:self.send_error(403,'Forbidden')
  except (OSError,ValueError):self.send_error(404,'File not found')


def main():
 global PORT
 for profile in profiles():
  if profile['kind']!='local':KEYS[profile['id']]=CREDENTIALS.get(profile['id'],profile['base_url'])
 KEYS['brave-search']=CREDENTIALS.get('brave-search','https://api.search.brave.com')
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=4311);p.add_argument('--open',action='store_true');p.add_argument('--no-browser',action='store_true');args=p.parse_args();PORT=args.port
 PROJECT_HOME.mkdir(parents=True,exist_ok=True)
 demo=PROJECT_HOME/('Личные чаты' if CLOUD else 'demo')
 if CLOUD:demo.mkdir(exist_ok=True)
 elif not demo.exists():
  if SITE.is_dir():shutil.copytree(SITE,demo,ignore=shutil.ignore_patterns('.agent.lock'))
  else:demo.mkdir()
 lock=(DATA/'server.lock').open('a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit('IDE уже запущена')
 try:
  if not CLOUD and not args.no_browser:ensure_bridge()
 except ValueError as e:print(str(e),flush=True)
 server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler);print(f'Rant Agent: http://127.0.0.1:{PORT}',flush=True)
 preview=ThreadingHTTPServer(('127.0.0.1',PREVIEW_PORT),PreviewHandler)
 threading.Thread(target=preview.serve_forever,daemon=True).start()
 if args.open:
  import webbrowser
  webbrowser.open(f'http://127.0.0.1:{PORT}/')
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:
  DEVICES.stop('local')
  if ACTIVE and ACTIVE['process'].poll() is None:
   proc=ACTIVE['process'];os.killpg(proc.pid,signal.SIGINT)
   if os.environ.get('RANT_MANAGED_URL'):
    try:desktop_request('cancel')
    except (ValueError,OSError):pass
   try:proc.wait(timeout=8)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
  LOCAL.close();preview.shutdown();preview.server_close();server.server_close()
if __name__=='__main__':main()
