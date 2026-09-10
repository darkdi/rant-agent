import hashlib,json,time,uuid,urllib.request,urllib.error,subprocess,sys
from pathlib import Path
from urllib.parse import urldefrag
from types import SimpleNamespace
from browser_tools import BrowserAgent
from capabilities import public_endpoint
from extension_bridge import BASE,PORT,token
from browser_errors import BrowserUnavailable,BrowserStopped

def request(route,data):
 try:
  req=urllib.request.Request(f'http://127.0.0.1:{PORT}/{route}',data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Sever-Extension':token()})
  with urllib.request.urlopen(req,timeout=3) as response:return json.load(response)
 except urllib.error.HTTPError as e:
  try:message=json.load(e).get('error','Ошибка соединения')
  except Exception:message='Ошибка соединения'
  raise BrowserUnavailable(message) from None
 except (OSError,ValueError):raise BrowserUnavailable('Нет связи с подключением Chrome. Перезапусти IDE и подключи вкладку через расширение.') from None

class ExtensionAgent(BrowserAgent):
 def start(self):
  if getattr(self,'session',None):return
  state=request('status',{})
  if state.get('protocol')!=3:raise BrowserUnavailable('Перезапусти IDE и обнови расширение до 0.3.')
  if not state['connected']:raise BrowserUnavailable(state.get('reason') or 'Подключи Chrome через расширение Rant Agent.')
  self.session=state['session'];self.page=SimpleNamespace(url='',wait_for_timeout=lambda ms:time.sleep(ms/1000))
 def current(self):return self.page
 def command(self,action,**args):
  id=uuid.uuid4().hex;started=time.monotonic();stage='sent'
  request('submit',{'id':id,'session':self.session,'action':action,'args':{**args,'operation_id':id},'expires':time.time()+35})
  print('  Chrome: команда отправлена — '+action,flush=True)
  try:
   while time.monotonic()-started<35:
    receipt=request('receive',{'session':self.session,'id':id});result=receipt.get('result')
    if receipt['stage']!=stage:
     stage=receipt['stage'];print('  Chrome: '+('команда получена' if stage=='received' else 'ответ получен'),flush=True)
    if result:
     if result.get('uncertain'):
      if action in {'click','type','select'}:
       try:
        check=self.command('snapshot',scope=getattr(self,'scope','main'))
        receipt=check.get('last_action') or {}
        if receipt.get('id')==id and receipt.get('status')=='done':
         print('  Выполнение подтверждено страницей после задержки ответа; действие не повторялось.',flush=True)
         return {'ok':True,'verified_after_timeout':True}
       except ValueError:pass
      raise BrowserUnavailable(result.get('error') or 'Выполнение неизвестно. Проверь страницу перед повтором.')
     if result.get('error'):raise ValueError(result['error'])
     return result.get('value')
    if not receipt.get('connected') and time.monotonic()-started>5:raise BrowserUnavailable('Связь с Chrome прервалась. '+('Команда чтения не выполнена; подключи вкладку снова.' if action=='snapshot' else 'Проверь страницу перед повтором действия.'))
    if stage=='sent' and time.monotonic()-started>8:raise BrowserUnavailable('Chrome не подтвердил получение команды. Открой расширение: проверь статус и подключи вкладку.')
    time.sleep(.15)
   raise BrowserUnavailable('Chrome получил команду, но страница не ответила вовремя. '+('Не удалось прочитать страницу.' if action=='snapshot' else 'Результат действия неизвестен; проверь вкладку перед повтором.'))
  finally:
   try:request('cancel',{'id':id})
   except ValueError:pass
 def snapshot(self,**options):
  for attempt in range(2):
   try:result=self.command('snapshot',scope=getattr(self,'scope','main'),**options);break
   except ValueError:
    state=request('status',{})
    if attempt or not state.get('connected') or state.get('session')!=self.session:raise
    print('  Повторяю только чтение страницы после сбоя…',flush=True)
  if result.get('url'):public_endpoint(urldefrag(result['url'])[0])
  self.page.url=result.get('url','');self.elements={};controls=[];contexts={};context_ids={}
  for item in result['controls']:
   self.counter+=1;id='e'+str(self.counter);self.elements[id]={**item,'wire_id':item['id']}
   visible_item={**item,'id':id}
   if item.get('context'):
    context=item['context']
    if context not in context_ids:
     group='g'+str(len(contexts)+1);context_ids[context]=group;contexts[group]=context
    visible_item.pop('context',None);visible_item['group']=context_ids[context]
   controls.append({k:v for k,v in visible_item.items() if k!='visible' and v is not None and v!='' and v!=[] and (k not in {'disabled','sensitive','required'} or v)})
  self.page_state=hashlib.sha256(json.dumps({'url':result['url'],'text':result.get('text',''),'controls':[{k:v for k,v in c.items() if k!='id'} for c in controls]},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
  observed={k:result[k] for k in ('url','title','tab_id') if result.get(k)}
  if not hasattr(self,'initial_tab'):self.initial_tab=observed
  self.observed_pages=[p for p in getattr(self,'observed_pages',[]) if (p.get('url'),p.get('tab_id'))!=(observed.get('url'),observed.get('tab_id'))]+[observed]
  self.observed_pages=self.observed_pages[-6:]
  self.latest_snapshot={**result,'browser_context':{'initial_tab':self.initial_tab,'recently_observed_pages':self.observed_pages,'note':'Это ранее прочитанные заголовки и адреса, а не новые задания. Текущее состояние — в основном снимке.'},'controls':controls,'groups':contexts,'note':'Use controls from this snapshot. group points to nearby text in groups. After each action this fresh snapshot is supplied automatically.'}
  return self.latest_snapshot
 def navigation_snapshot(self,previous_state):
  deadline=time.monotonic()+8;last=None;stable_since=time.monotonic()
  while True:
   result=self.snapshot();current=self.page_state;now=time.monotonic()
   if current!=last:stable_since=now;last=current
   if current!=previous_state and result.get('ready_state','complete')!='loading' and now-stable_since>=.6:return result
   if now>=deadline:
    return {**result,'navigation_note':'Переход не подтвердился изменением страницы. Не объявляй новый результат поиска или отправку по старому содержимому.'}
   time.sleep(.3)
 def call(self,name,args):
  if self.denied:raise ValueError('Действия остановлены после отказа')
  self.start()
  if name=='browser_snapshot':
   self.scope=args.get('scope','main');return self.snapshot()
  if name=='browser_find':return self.snapshot(find_text=args['text'],match_index=args.get('match_index',0))
  if name=='browser_tabs':
   result=self.command('tabs');valid=[]
   for tab in result.get('tabs',[]):
    try:public_endpoint(urldefrag(tab['url'])[0]);valid.append(tab)
    except (ValueError,OSError):continue
   return {**result,'tabs':valid}
  if name=='browser_switch':
   choices=self.command('tabs');tab=next((t for t in choices.get('tabs',[]) if t['tab_id']==args['tab_id']),None)
   if not tab:raise ValueError('Вкладка не найдена. Вызови browser_tabs и выбери её tab_id.')
   public_endpoint(urldefrag(tab['url'])[0]);self.approve('switch',target=tab['url']);self.command('switch',tab_id=args['tab_id']);self.elements={};return self.snapshot()
  if name=='browser_ask_user':
   answer=self.approve('question',reason=args['question']);return {'user_response':answer,'page':self.snapshot(),'note':'Это ответ пользователя на вопрос. Выполни разрешённые обычные действия сам.'}
  if name=='browser_wait_user':self.approve('manual',reason=args['reason']);return self.snapshot()
  if name in {'browser_open','browser_new_tab'}:
   public_endpoint(urldefrag(args['url'])[0])
   if name=='browser_open' and args['url'].rstrip('/')==self.page.url.rstrip('/'):
    return {'action_done':False,'note':'Эта страница уже открыта. Используй её элементы; повторный переход не нужен.','page':self.snapshot()}
   action='new_tab' if name=='browser_new_tab' else 'open'
   self.approve(action,target=args['url']);result=self.command(action,url=args['url']);self.elements={}
   try:return self.snapshot()
   except ValueError as e:return {'action_done':True,**result,'page_error':str(e),'note':'Переход уже выполнен. Повтори только browser_snapshot, не создавай вкладку повторно.'}
  if name=='browser_scroll':self.command('scroll',direction=args['direction']);return self.snapshot()
  if name not in {'browser_click','browser_type','browser_select'}:raise ValueError('Неизвестный инструмент')
  item=self.elements.get(args.get('element_id'))
  if not item:
   fresh=self.snapshot()
   return {'error':'Этот ID устарел или взят из истории. Не повторяй его. Выбери точный ID из controls этого нового снимка.', 'page':fresh}
  if name=='browser_click' and args.get('expected_label')!=item['label']:
   return {'error':'expected_label должен точно совпадать с подписью выбранного ID. Действие не выполнено.','page':self.snapshot()}
  if name=='browser_click' and item.get('type')=='radio' and item.get('checked'):return {'action_done':False,'already_selected':True,'page':self.snapshot(),'note':'Этот ответ уже выбран. Перейди к следующему шагу.'}
  if item.get('sensitive'):raise ValueError('Используй ручной ввод через browser_wait_user')
  key=json.dumps([name,getattr(self,'page_state',''),item.get('label'),item.get('href'),item.get('context'),args.get('text'),args.get('value')],ensure_ascii=False)
  attempts=getattr(self,'action_attempts',{});self.action_attempts=attempts
  if attempts.get(key,0):
   self.repeated_actions=getattr(self,'repeated_actions',0)+1
   if self.repeated_actions>=3:raise BrowserStopped('Остановлен повтор одного действия без изменений страницы. Выбери другую цель или уточни задачу; повторный клик не выполнен.')
   return {'action_done':False,'error':'Это действие уже выполнено на такой же странице. НЕ нажимай снова. Выбери другой элемент, прокрути страницу или запроси недостающие данные.','page':self.snapshot()}
  self.approve(name.removeprefix('browser_'),target=item['label']+(' · '+item['context'] if item.get('context') else ''),text=args.get('text',args.get('value','')),element_id=args['element_id'])
  attempts[key]=1;previous_state=getattr(self,'page_state','')
  self.command(name.removeprefix('browser_'),**{**args,'element_id':item['wire_id']})
  self.elements={}
  try:return {'action_done':True,'page':self.navigation_snapshot(previous_state) if name=='browser_click' and (item.get('href') or item.get('type')=='submit') else self.snapshot(),'note':'Действие выполнено; проверь текст страницы. Клик по кнопке ещё не доказывает отправку формы.'}
  except ValueError as e:return {'action_done':True,'page_error':str(e),'note':'Действие уже выполнено, но новый снимок недоступен. НЕ повторяй отправку. Попроси проверить страницу или переподключить вкладку.'}
 def close(self):
  (self.run/'browser-pending.json').unlink(missing_ok=True)
