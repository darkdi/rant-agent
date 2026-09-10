"""Internal project-scoped working notes. No service files in user projects."""
from pathlib import Path
import os,tempfile
import hashlib,shutil
STORAGE=Path(os.environ.get('RANT_DATA_DIR',str(Path(__file__).resolve().parents[1]/'.local')))/'agent-context'
FILES={'user':'CONTEXT.md','project':'PROJECT.md','notes':'DECISIONS.md'}

def directory(root):
 root=Path(root).resolve();STORAGE.mkdir(parents=True,exist_ok=True,mode=0o700)
 folder=STORAGE/hashlib.sha256(str(root).encode()).hexdigest()[:24]
 if folder.is_symlink():raise ValueError('Недопустимая папка контекста')
 folder.mkdir(exist_ok=True,mode=0o700)
 old=root/'.rant-agent'
 if old.is_dir() and not old.is_symlink():
  for source,name in [('USER.md','CONTEXT.md'),('PROJECT.md','PROJECT.md'),('NOTES.md','DECISIONS.md'),('CHAT.md','CHAT.md')]:
   src=old/source;dst=folder/name
   if src.is_file() and not src.is_symlink():
    if not dst.exists():shutil.copy2(src,dst);dst.chmod(0o600)
    if not dst.is_symlink() and dst.read_bytes()==src.read_bytes():src.unlink()
  if (old/'chats').is_dir() and not (old/'chats').is_symlink() and not (folder/'chats').exists():shutil.move(str(old/'chats'),str(folder/'chats'))
  try:old.rmdir()
  except OSError:pass
 return folder

def memory_path(root,key):
 if key not in FILES:raise ValueError('Неизвестный раздел памяти')
 p=directory(root)/FILES[key]
 if p.is_symlink():raise ValueError('Файл памяти не должен быть символической ссылкой')
 return p

def get_memory(root):
 documents={}
 defaults={'user':'# Рабочий контекст\n\nСохраняй только подтверждённые пользователем сведения, нужные для выполнения задач.\n','project':'# Проект\n\nЦель и требования проекта. Выполняй текущее задание пользователя и проверяй результат инструментами.\n','notes':'# Решения и правила\n\nРаботай в одной подключённой вкладке. Не считай прежний ответ доказательством выполненного действия.\n'}
 for key in FILES:
  p=memory_path(root,key)
  if not p.exists():
   try:
    with p.open('x',encoding='utf-8') as f:f.write(defaults[key])
    p.chmod(0o600)
   except FileExistsError:pass
  documents[key]=p.read_text()[:8000] if p.exists() else ''
 return {'documents':documents,'folder':str(directory(root)),'note':'Память передаётся выбранной модели. Полный чат хранится отдельно; старые действия нужно проверять заново.'}

def save_memory(root,key,content):
 if not isinstance(content,str) or len(content)>8000:raise ValueError('Раздел памяти: максимум 8000 символов')
 p=memory_path(root,key)
 with tempfile.NamedTemporaryFile(mode='w',dir=p.parent,delete=False,encoding='utf-8') as f:
  f.write(content);tmp=Path(f.name)
 try:tmp.chmod(0o600);os.replace(tmp,p)
 finally:tmp.unlink(missing_ok=True)
 return get_memory(root)

def memory_context(root,budget=3500):
 docs=get_memory(root)['documents'];parts=[]
 for key,limit in [('user',budget//3),('project',budget//3),('notes',budget//3)]:
  if docs[key].strip():parts.append(FILES[key]+':\n'+docs[key][:limit])
 return '\n\n'.join(parts)[:budget]


def search_memory(root,query):
 import re
 words=set(re.findall(r'[\w]{3,}',str(query).lower()));matches=[]
 for key,text in get_memory(root)['documents'].items():
  for paragraph in text.split('\n\n'):
   score=sum(w in paragraph.lower() for w in words)
   if score:matches.append((score,{'file':FILES[key],'text':paragraph[:1200]}))
 return [x[1] for x in sorted(matches,key=lambda x:x[0],reverse=True)[:4]]
