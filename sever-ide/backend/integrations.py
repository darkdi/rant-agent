"""Explicitly enabled, per-account MCP tools over Streamable HTTP.
No shell/stdio on the hosted service. Credentials stay outside project files.
Tool grants are tied to a hash of the server's declared schema and description.
"""
import hashlib,http.client,json,os,re,socket,ssl,uuid
from pathlib import Path
from urllib.parse import urlsplit
from capabilities import public_endpoint
from credentials import CredentialStore

VERSION='2025-11-25'
ROOT=Path(os.environ.get('RANT_DATA_DIR',str(Path(__file__).resolve().parents[1]/'.local')))

def signature(tool):return hashlib.sha256(json.dumps(tool,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def validate_url(url):
 if not isinstance(url,str):raise ValueError('Укажи адрес MCP.')
 u=urlsplit(url)
 if u.query:raise ValueError('Адрес MCP должен быть без секретов в строке запроса. Используй поле токена.')
 return public_endpoint(url)

class MCP:
 def __init__(self,url,key=''):self.url=url;self.key=key;self.session=None;self.version=VERSION;self.counter=0
 def rpc(self,method,params=None,notification=False):
  self.counter+=1;rid=self.counter;payload={'jsonrpc':'2.0','method':method,'params':params or {}}
  if not notification:payload['id']=rid
  u,ip=validate_url(self.url)
  class Pinned(http.client.HTTPSConnection):
   def connect(inner):
    sock=socket.create_connection((ip,443),timeout=25)
    try:inner.sock=inner._context.wrap_socket(sock,server_hostname=u.hostname)
    except BaseException:sock.close();raise
  conn=Pinned(u.hostname,timeout=25,context=ssl.create_default_context())
  headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','MCP-Protocol-Version':self.version}
  if self.key:headers['Authorization']='Bearer '+self.key
  if self.session:headers['MCP-Session-Id']=self.session
  try:
   conn.request('POST',u.path or '/',json.dumps(payload,ensure_ascii=False).encode(),headers);res=conn.getresponse()
   if res.status not in {200,202,204}:raise ValueError(f'MCP вернул HTTP {res.status}. Запрос автоматически не повторялся.')
   sid=res.getheader('MCP-Session-Id')
   if sid:
    if len(sid)>256 or not all(33<=ord(c)<=126 for c in sid):raise ValueError('Некорректная сессия MCP.')
    self.session=sid
   if notification:return {}
   if 'text/event-stream' in res.getheader('Content-Type',''):
    total=0;frame=[];data=None
    while True:
     line=res.readline(131073);total+=len(line)
     if not line or total>1000000 or len(line)>131072:raise ValueError('MCP не завершил ответ. Действие могло выполниться; не повторяй его без проверки.')
     line=line.decode().rstrip('\r\n')
     if line.startswith('data:'):frame.append(line[5:].lstrip())
     elif not line and frame:
      text='\n'.join(frame);frame=[]
      if not text.strip():continue
      item=json.loads(text)
      if item.get('id')==rid and ('result' in item or 'error' in item):data=item;break
      if 'method' in item and 'id' in item:raise ValueError('Этот MCP требует неподдерживаемого интерактивного обмена.')
   else:
    raw=res.read(1000001)
    if len(raw)>1000000:raise ValueError('Ответ MCP слишком большой.')
    data=json.loads(raw)
   if not isinstance(data,dict) or data.get('id')!=rid:raise ValueError('MCP вернул ответ на другой запрос.')
   if data.get('error'):raise ValueError('MCP сообщил об ошибке выполнения. Проверь настройки сервиса; автоматического повтора нет.')
   result=data.get('result')
   if not isinstance(result,dict):raise ValueError('Неверный ответ MCP.')
   return result
  finally:conn.close()
 def start(self):
  result=self.rpc('initialize',{'protocolVersion':VERSION,'capabilities':{},'clientInfo':{'name':'Rant Agent','version':'0.3.0'}})
  if result.get('protocolVersion') not in {'2025-11-25','2025-06-18','2025-03-26'}:raise ValueError('Версия MCP пока не поддерживается.')
  self.version=result['protocolVersion'];self.rpc('notifications/initialized',notification=True)
 def tools(self):
  result=self.rpc('tools/list');tools=result.get('tools',[])
  if result.get('nextCursor'):raise ValueError('В MCP слишком много инструментов. Подключи сервер с небольшим набором действий.')
  if not isinstance(tools,list) or len(tools)>100:raise ValueError('MCP: допустимо до 100 доступных инструментов.')
  clean=[]
  for t in tools:
   if not isinstance(t,dict) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}',t.get('name','')):raise ValueError('Некорректное имя инструмента MCP.')
   schema=t.get('inputSchema',{})
   if not isinstance(schema,dict) or schema.get('type')!='object' or len(json.dumps(schema))>16000:raise ValueError('Неподдерживаемая схема инструмента MCP.')
   clean.append({'name':t['name'],'description':str(t.get('description',''))[:2000],'inputSchema':schema})
  if len({t['name'] for t in clean})!=len(clean):raise ValueError('MCP содержит повторяющиеся имена.')
  return clean
 def call(self,name,arguments):
  result=self.rpc('tools/call',{'name':name,'arguments':arguments})
  # Return bounded text only; binary/image MCP outputs require a vision adapter.
  blocks=result.get('content',[]);texts=[str(b.get('text','')) for b in blocks if isinstance(b,dict) and b.get('type')=='text']
  value={'text':'\n'.join(texts)[:18000],'isError':bool(result.get('isError')),'untrusted_content':True}
  if 'structuredContent' in result:value['structuredContent']=result['structuredContent']
  if len(json.dumps(value))>24000:value.pop('structuredContent',None);value['truncated']=True
  if any(isinstance(b,dict) and b.get('type')!='text' for b in blocks):value['note']='Этот ответ содержит нетекстовые данные; текущий MCP-клиент передаёт модели только текст.'
  return value

class Connections:
 def __init__(self,root=ROOT):
  self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700);self.path=self.root/'integrations.json';self.keys=CredentialStore(self.root/'integration-credentials')
 def load(self):return json.loads(self.path.read_text()) if self.path.exists() else []
 def write(self,items):
  tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(items,ensure_ascii=False,indent=2));tmp.chmod(0o600);tmp.replace(self.path)
 def public(self):return [{k:v for k,v in x.items() if k!='grants'}|{'has_key':bool(self.keys.get(x['id'],x['url'])),'allowed':list(x.get('grants',{}))} for x in self.load()]
 def change(self,data):
  items=self.load();action=data.get('action');id=data.get('id')
  old=next((x for x in items if x['id']==id),None)
  if action=='delete':
   if not old:raise ValueError('Подключение не найдено.')
   self.keys.update(id,old['url'],clear=True);self.write([x for x in items if x['id']!=id]);return self.public()
  if action=='grant':
   if not old:raise ValueError('Сначала проверь подключение.')
   selected=data.get('allowed',[])
   if not isinstance(selected,list) or len(selected)>20 or any(not isinstance(x,str) for x in selected):raise ValueError('Выбери до 20 действий.')
   known={t['name']:signature(t) for t in old['tools']}
   if any(x not in known for x in selected):raise ValueError('Неизвестный инструмент.')
   if sum(len(x.get('grants',{})) for x in items if x['id']!=id)+len(selected)>30:raise ValueError('Разреши до 30 действий суммарно, чтобы не перегружать модель.')
   old['grants']={x:known[x] for x in selected};self.write(items);return self.public()
  if action!='connect':raise ValueError('Неизвестное действие.')
  url=data.get('url','').strip();validate_url(url);name=data.get('name','').strip()
  if not name or len(name)>60:raise ValueError('Название подключения: от 1 до 60 символов.')
  if id and not old:raise ValueError('Подключение не найдено.')
  if not old and len(items)>=5:raise ValueError('Можно подключить до пяти MCP-сервисов.')
  id=id or uuid.uuid4().hex;key=data.get('key','')
  if not isinstance(key,str) or len(key)>16384 or '\n' in key or '\r' in key:raise ValueError('Неверный токен.')
  key='' if data.get('clear_key') else key or self.keys.get(id,url)
  client=MCP(url,key);client.start();tools=client.tools()
  self.keys.update(id,url,key,clear=bool(data.get('clear_key')))
  value={'id':id,'name':name,'url':url,'tools':tools,'grants':{}}
  # Rechecking deliberately requires reselecting grants; never trust changed tools.
  self.write([x for x in items if x['id']!=id]+[value]);return self.public()
 def runtime(self):return Runtime(self)

class Runtime:
 def __init__(self,store):self.store=store;self.clients={};self.mapping={};self.specs=[]
 def prepare(self):
  for item in self.store.load():
   grants=item.get('grants',{})
   if not grants:continue
   client=MCP(item['url'],self.store.keys.get(item['id'],item['url']));client.start();tools=client.tools()
   for tool in tools:
    name=tool['name']
    if name not in grants:continue
    if signature(tool)!=grants[name]:raise ValueError(f'В подключении «{item["name"]}» изменились действия. Проверь их в «Инструментах» и разреши заново.')
    alias='mcp_'+item['id'][:12]+'_'+hashlib.sha256(name.encode()).hexdigest()[:12]
    self.mapping[alias]=(client,name,item['id'],grants[name]);self.specs.append({'type':'function','function':{'name':alias,'description':('Подключение '+item['name']+', действие '+name+'. '+tool['description'])[:2300],'parameters':tool['inputSchema']}})
   if set(grants)-{t['name'] for t in tools}:raise ValueError('Разрешённый MCP-инструмент исчез. Обнови подключение.')
  return self.specs
 def call(self,alias,args):
  client,name,id,grant=self.mapping[alias]
  current=next((x for x in self.store.load() if x['id']==id),None)
  if not current or current.get('grants',{}).get(name)!=grant:raise ValueError('Доступ к этому инструменту отозван.')
  if not isinstance(args,dict) or len(json.dumps(args))>50000:raise ValueError('Некорректные аргументы MCP.')
  try:return client.call(name,args)
  except (OSError,ValueError):
   from browser_errors import BrowserUnavailable
   raise BrowserUnavailable('MCP не подтвердил результат действия. Оно могло выполниться; проверь внешний сервис перед повтором.') from None
