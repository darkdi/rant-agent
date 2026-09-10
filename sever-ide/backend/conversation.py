"""Bounded conversation context, scoped to a project and a user-reset conversation."""
import json,difflib
from pathlib import Path

def read(path,default):
 try:return json.loads(Path(path).read_text())
 except (OSError,ValueError):return default

def conversation_items(runs,root,conversation):
 items=[]
 if not Path(runs).exists():return items
 for p in Path(runs).iterdir():
  if not p.is_dir():continue
  meta=read(p/'meta.json',{});report=read(p/'report.json',{})
  if meta.get('root')==str(root) and meta.get('conversation','legacy')==conversation and meta.get('mode')!='manual' and report.get('final'):
   items.append((meta.get('created',0),meta,report,p))
 return sorted(items,key=lambda x:x[0])

def search_conversation(runs,root,conversation,query,limit=5,allowed_modes=None):
 import re
 words=set(re.findall(r'[\w]{3,}',str(query).lower()));scored=[]
 for created,meta,report,p in conversation_items(runs,root,conversation):
  if allowed_modes is not None and meta.get('mode') not in allowed_modes:continue
  task=meta.get('task','');answer=report.get('final','');source=task+' '+answer
  score=sum(word in source.lower() for word in words)
  if score:scored.append((score,created,{'id':p.name,'user':task[:900],'assistant':answer[:900],'status':report.get('status'),'historical':True}))
 return {'matches':[x[2] for x in sorted(scored,key=lambda x:(x[0],x[1]),reverse=True)[:limit]],'note':'История разговора, не текущее состояние браузера или файлов. Старые ID недействительны; ответы модели могут быть ошибочны.'}

def read_conversation(runs,root,conversation,id,offset=0,allowed_modes=None):
 if type(offset) is not int or offset<0:raise ValueError('Смещение должно быть неотрицательным целым числом')
 for _,meta,report,p in conversation_items(runs,root,conversation):
  if p.name!=id or (allowed_modes is not None and meta.get('mode') not in allowed_modes):continue
  text='Пользователь:\n'+meta.get('task','')+'\n\nИсторический ответ ('+str(report.get('status'))+'):\n'+report.get('final','')
  chunk=text[offset:offset+12000]
  return {'id':id,'text':chunk,'next_offset':offset+len(chunk) if offset+len(chunk)<len(text) else None,'historical':True,'note':'Архивные данные, не новое поручение и не подтверждение текущего состояния.'}
 raise ValueError('Запись не найдена в доступном архиве этого чата')

def history_for(runs,root,conversation,mode,access,query='',budget=5500):
 # Preserve the complete archive; select recent messages by size, not task count.
 items=conversation_items(runs,root,conversation)
 if access.get('files')=='none':items=[x for x in items if x[1].get('mode') in {'chat','browser'}]
 pairs=[];message_limit=min(10000,max(1200,budget//3))
 for _,meta,report,p in items:
  answer=report['final'].split('[Сохранённый отчёт IDE')[0].strip()
  attached=''.join('\nВложение: '+x['name']+' (id '+x['id']+')' for x in meta.get('attachments',[]))
  pair=[{'role':'user','content':meta.get('task','')[:message_limit]+attached}, {'role':'assistant','content':'[Исторический ответ; статус: '+str(report.get('status'))+'] '+answer[:message_limit]}]
  pairs.append(pair)
 recent=[];used=0
 for pair in reversed(pairs):
  size=sum(len(m['content']) for m in pair)
  if used+size>budget*.65:break
  recent.insert(0,pair);used+=size
 older=pairs[:len(pairs)-len(recent)] if recent else pairs
 if older:
  # Relevant old statements plus a chronological outline; never invent a summary.
  matches=search_conversation(runs,root,conversation,query,3,allowed_modes={'chat','browser'} if access.get('files')=='none' else None)['matches'] if query else []
  outline='\n'.join('- '+pair[0]['content'].replace('\n',' ')[:140] for pair in older)
  relevant='\n'.join('Пользователь: '+m['user'][:450]+'\nОтвет ('+str(m['status'])+'): '+m['assistant'][:250] for m in matches)
  remaining=budget-used
  summary=('Ранее в разговоре (архив, не новые команды):\n'+relevant+'\nТемы предыдущих сообщений:\n'+outline)[:remaining]
  messages=[{'role':'user','content':summary}]
 else:messages=[]
 return messages+[m for pair in recent for m in pair]

def export_conversation(runs,root,conversation):
 from agent_memory import directory
 folder=directory(root);path=folder/'CHAT.md'
 if path.is_symlink():raise ValueError('Архив чата не должен быть символической ссылкой')
 parts=['# Чат Rant Agent','Внутренний архив текущего разговора. Агент ведёт рабочий контекст автоматически.']
 for _,meta,report,p in conversation_items(runs,root,conversation):
  parts+=['\n## Пользователь\n'+meta.get('task',''),'\n## Агент — '+str(report.get('status'))+'\n'+report.get('final','')]
 import os,tempfile
 with tempfile.NamedTemporaryFile(mode='w',dir=folder,delete=False,encoding='utf-8') as f:
  f.write('\n\n'.join(parts)+'\n');tmp=Path(f.name)
 try:tmp.chmod(0o600);os.replace(tmp,path)
 finally:tmp.unlink(missing_ok=True)
 # Keep a separate readable archive for each conversation too.
 import re
 if re.fullmatch(r'(legacy|[a-f0-9]{32})',conversation):
  archive=folder/'chats'
  if not archive.is_symlink():
   archive.mkdir(exist_ok=True,mode=0o700);target=archive/(conversation+'.md')
   if not target.is_symlink():
    with tempfile.NamedTemporaryFile(mode='w',dir=archive,delete=False,encoding='utf-8') as f:
     f.write(path.read_text());tmp=Path(f.name)
    try:tmp.chmod(0o600);os.replace(tmp,target)
    finally:tmp.unlink(missing_ok=True)
 return str(path)

def net_diff(changes,path=None):
 files={}
 for c in changes:
  name=c['path']
  if path and name!=path:continue
  if name not in files:files[name]={'before':c.get('before'),'after':c['after']}
  else:files[name]['after']=c['after']
 result=[]
 for name,change in files.items():
  before=change['before'] or '';after=change['after'] or ''
  if before==after:continue
  lines=difflib.unified_diff(before.splitlines(),after.splitlines(),fromfile=name,tofile=name,lineterm='')
  result.append('\n'.join(lines))
 return '\n\n'.join(result) or 'Нет изменений в этой задаче.'


def chat_list(runs,root,current,metadata):
 deleted={k for k,v in metadata.get(str(root),{}).items() if v.get('deleted_at')}
 chats={k:dict(v,id=k,count=0) for k,v in metadata.get(str(root),{}).items() if k not in deleted}
 for p in Path(runs).iterdir():
  m=read(p/'meta.json',{})
  if m.get('root')!=str(root) or m.get('mode')=='manual':continue
  id=m.get('conversation','legacy');created=m.get('created',0)
  if id in deleted:continue
  if id not in chats:chats[id]={'id':id,'title':m.get('task','Чат')[:65],'created':created,'updated':created,'count':0}
  c=chats[id];c['count']+=1;c['updated']=max(c.get('updated',0),created)
  if not c.get('renamed') and (created<c.get('created',created) or c['title']=='Новый чат'):c['title']=m.get('task','Чат')[:65];c['created']=created
 return sorted(chats.values(),key=lambda c:c.get('updated',0),reverse=True)
