"""Persistent app credentials, outside projects and served files. Values never enter UI state."""
from pathlib import Path
from urllib.parse import urlsplit
import json,os,tempfile


def origin(url):
 parsed=urlsplit(url)
 return parsed.scheme.lower()+'://'+parsed.netloc.lower()

class CredentialStore:
 def __init__(self,directory):
  self.directory=Path(directory)
  if self.directory.is_symlink():raise ValueError('Недопустимая папка ключей')
  self.directory.mkdir(parents=True,exist_ok=True,mode=0o700);self.directory.chmod(0o700)
  self.path=self.directory/'keys.json'
 def read(self):
  if self.path.is_symlink():raise ValueError('Недопустимый файл ключей')
  if not self.path.exists():return {}
  self.path.chmod(0o600)
  try:
   data=json.loads(self.path.read_text())
   if not isinstance(data,dict) or any(not isinstance(k,str) or not isinstance(v,dict) or not isinstance(v.get('value'),str) or not isinstance(v.get('origin'),str) for k,v in data.items()):raise ValueError()
   return data
  except (ValueError,UnicodeError):raise ValueError('Не удалось прочитать сохранённые ключи. Файл не перезаписан.') from None
 def get(self,id,url):
  item=self.read().get(id,{})
  return item.get('value','') if item.get('origin')==origin(url) else ''
 def update(self,id,url,key=None,clear=False):
  if not isinstance(id,str) or not id or len(id)>100:raise ValueError('Некорректное подключение')
  data=self.read();destination=origin(url)
  if data.get(id,{}).get('origin')!=destination:data.pop(id,None)
  if clear:data.pop(id,None)
  elif key:
   if not isinstance(key,str) or len(key)>16384 or '\n' in key or '\r' in key:raise ValueError('Некорректный API-ключ')
   key=key.strip()
   if not key:raise ValueError('API-ключ пустой')
   data[id]={'origin':destination,'value':key}
  with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.directory,delete=False) as f:
   tmp=Path(f.name)
   try:
    os.chmod(tmp,0o600);json.dump(data,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
   except BaseException:tmp.unlink(missing_ok=True);raise
  try:os.replace(tmp,self.path)
  finally:tmp.unlink(missing_ok=True)
