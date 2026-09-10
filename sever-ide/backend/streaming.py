"""SSE assembly for model providers and a private, resumable public-text buffer."""
import json,os,time
from pathlib import Path

class LiveOutput:
 def __init__(self,run):
  self.path=Path(run)/'live.json';self.text='';self.step=0;self.last=0
 def reset(self):
  self.step+=1;self.text='';self.flush()
 def add(self,text):
  if not isinstance(text,str):return
  self.text+=text
  if time.monotonic()-self.last>=.04:self.flush()
 def flush(self):
  data={'text':self.text,'step':self.step};tmp=self.path.with_suffix('.tmp')
  tmp.write_text(json.dumps(data,ensure_ascii=False));tmp.chmod(0o600);os.replace(tmp,self.path);self.last=time.monotonic()

def events(response):
 """Read complete SSE frames; line boundaries never split a UTF-8 character."""
 total=0;data=[]
 while True:
  raw=response.readline(1_000_001);total+=len(raw)
  if len(raw)>1_000_000 or total>16_000_000:raise ValueError('Поток ответа превышает лимит')
  if not raw:
   if data:raise ValueError('Соединение оборвалось посреди события ответа')
   return
  line=raw.decode('utf-8').rstrip('\r\n')
  if not line:
   if data:
    payload='\n'.join(data);data=[]
    if payload=='[DONE]':yield None;return
    event=json.loads(payload)
    if not isinstance(event,dict):raise ValueError('Некорректное событие API')
    if event.get('error') or event.get('type')=='error':raise ValueError('Сервис прервал поток ответа. Частичный текст сохранён; действия не повторялись.')
    yield event
  elif line.startswith('data:'):data.append(line[5:].lstrip(' '))

def read_stream(response,kind,on_text):
 if kind=='responses':
  for event in events(response):
   if event is None:break
   t=event.get('type')
   if t in {'response.output_text.delta','response.refusal.delta'}:on_text(event.get('delta',''))
   elif t in {'response.completed','response.incomplete','response.failed'}:
    result=event.get('response')
    if not isinstance(result,dict):raise ValueError('API не прислал итог ответа')
    return result
  raise ValueError('Поток оборвался до подтверждения ответа. Частичный текст сохранён.')
 if kind=='anthropic':
  result={};blocks={};pending=set();started=False;has_stop=False
  for event in events(response):
   if event is None:break
   t=event.get('type');index=event.get('index')
   if t=='message_start':result=event['message'];started=True
   elif t=='content_block_start':
    blocks[index]=dict(event['content_block']);pending.add(index)
    if blocks[index].get('type')=='text':on_text(blocks[index].get('text',''))
   elif t=='content_block_delta':
    if index not in pending:raise ValueError('Нарушен порядок фрагментов ответа')
    block=blocks[index];delta=event['delta'];dt=delta.get('type')
    if dt=='text_delta':block['text']=block.get('text','')+delta['text'];on_text(delta['text'])
    elif dt=='input_json_delta':block['_json']=block.get('_json','')+delta['partial_json']
    elif dt=='thinking_delta':block['thinking']=block.get('thinking','')+delta['thinking']
    elif dt=='signature_delta':block['signature']=block.get('signature','')+delta['signature']
   elif t=='content_block_stop':
    block=blocks[index]
    if '_json' in block:block['input']=json.loads(block.pop('_json') or '{}')
    pending.discard(index)
   elif t=='message_delta':result.update(event.get('delta',{}));has_stop=bool(result.get('stop_reason'))
   elif t=='message_stop':
    if not started or pending or not has_stop:raise ValueError('Модель не завершила все части ответа')
    result['content']=[blocks[k] for k in sorted(blocks)];return result
  raise ValueError('Поток оборвался до завершения ответа. Частичный текст сохранён.')
 text='';calls={};finish=None
 for event in events(response):
  if event is None:break
  choices=event.get('choices',[])
  for choice in choices:
   if choice.get('index',0)!=0:continue
   delta=choice.get('delta',{});part=delta.get('content') or delta.get('refusal') or ''
   if isinstance(part,str):text+=part;on_text(part)
   for chunk in delta.get('tool_calls',[]):
    index=chunk['index'];call=calls.setdefault(index,{'id':'','type':'function','function':{'name':'','arguments':''}})
    call['id']+=chunk.get('id') or '';fn=chunk.get('function',{})
    for key in ('name','arguments'):call['function'][key]+=fn.get(key) or ''
   if choice.get('finish_reason'):finish=choice['finish_reason']
 if not finish:raise ValueError('Поток оборвался до завершения ответа. Частичный текст сохранён.')
 ordered=[calls[k] for k in sorted(calls)]
 for call in ordered:
  if not call['id'] or not call['function']['name']:raise ValueError('API вернул незавершённое действие')
  if not isinstance(json.loads(call['function']['arguments'] or '{}'),dict):raise ValueError('Некорректные аргументы действия')
 return {'choices':[{'finish_reason':finish,'message':{'role':'assistant','content':text,**({'tool_calls':ordered} if ordered else {})}}]}
