"""Reversible chat/project library operations. Never delete working directories."""
import time, uuid
from pathlib import Path

def title(value):
 if not isinstance(value,str) or not value.strip() or len(value.strip())>120:raise ValueError('Название: от 1 до 120 символов')
 return value.strip()

def change(s,action,data):
 s.ensure_idle();root=s.project();key=str(root)
 index=s.load(s.DATA/'chat-index.json',{});current=s.conversation_id(root)
 if action.startswith('conversation-'):
  id=data.get('id');items=s.chat_list(s.RUNS,root,current,index);available={x['id']:x for x in items}
  old=index.get(key,{}).get(id,{})
  if action=='conversation-restore':
   if not old.get('deleted_at'):raise ValueError('Удалённый чат не найден в этом проекте')
   old.pop('deleted_at');index[key][id]=old
  else:
   if id not in available:raise ValueError('Чат не найден в этом проекте')
   record={**available[id],**old};record.pop('id',None);record.pop('count',None)
   if action=='conversation-rename':record.update(title=title(data.get('title')),renamed=True)
   elif action=='conversation-delete':record['deleted_at']=time.time()
   else:raise ValueError('Неизвестное действие')
   index.setdefault(key,{})[id]=record
  s.persist(s.DATA/'chat-index.json',index)
  if action=='conversation-delete' and id==current:
   others=[c for c in items if c['id']!=id];next_id=others[0]['id'] if others else uuid.uuid4().hex
   selected=s.load(s.DATA/'conversations.json',{});selected[key]=next_id;s.persist(s.DATA/'conversations.json',selected)
  return {'ok':True,'id':id,'kind':'conversation','root':key}
 path=data.get('path');projects=s.registered_projects();deleted=s.load(s.DATA/'deleted-projects.json',{})
 if not isinstance(path,str):raise ValueError('Нужен путь проекта')
 if action=='project-restore':
  if path not in deleted:raise ValueError('Удалённый проект не найден')
  item=deleted[path]
  if not Path(path).is_dir():raise ValueError('Папка проекта больше не существует')
  item.pop('deleted_at',None);projects=[x for x in projects if x['path']!=path]+[item];del deleted[path]
 else:
  item=next((x for x in projects if x['path']==path),None)
  if not item:raise ValueError('Проект не найден')
  if action=='project-rename':item['name']=title(data.get('title'))
  elif action=='project-delete':
   deleted[path]={**item,'deleted_at':time.time()};projects=[x for x in projects if x['path']!=path]
   if key==path:
    if not projects:
     folder=(s.PROJECT_HOME if getattr(s,'CLOUD',False) else s.DATA/'workspaces')/uuid.uuid4().hex;folder.mkdir(parents=True)
     projects=[{'path':str(folder),'name':'Личные чаты'}]
    s.persist(s.DATA/'settings.json',{**s.settings(),'project':projects[0]['path']})
  else:raise ValueError('Неизвестное действие')
 s.persist(s.DATA/'projects.json',projects);s.persist(s.DATA/'deleted-projects.json',deleted)
 return {'ok':True,'path':path,'kind':'project'}

def trash(s):
 key=str(s.project());index=s.load(s.DATA/'chat-index.json',{}).get(key,{})
 return {'items':sorted([{'id':id,'kind':'conversation','title':c['title'],'deleted_at':c['deleted_at']} for id,c in index.items() if c.get('deleted_at')]+[{'path':p,'kind':'project','title':c['name'],'deleted_at':c['deleted_at']} for p,c in s.load(s.DATA/'deleted-projects.json',{}).items()],key=lambda x:x['deleted_at'],reverse=True)}
