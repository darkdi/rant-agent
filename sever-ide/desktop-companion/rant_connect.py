"""Visible, opt-in outbound desktop companion. No inbound port, shell or background install."""
import base64,io,json,os,platform,queue,threading,time,urllib.request,urllib.error,sys,traceback
from pathlib import Path
import hashlib
from urllib.parse import urlsplit
import tkinter as tk
from tkinter import messagebox

def local_origin(value):
 u=urlsplit(value)
 if u.scheme!='http' or u.hostname not in {'127.0.0.1','localhost','::1'} or not u.port or u.username or u.password or u.path not in {'','/'} or u.query or u.fragment:
  raise ValueError('Для Rant Connect Local нужен адрес локального приложения, например http://127.0.0.1:4311')
 return value.rstrip('/')
settings=Path(__file__).with_name('server.json')
ORIGIN=local_origin(os.environ.get('RANT_LOCAL_URL') or (json.loads(settings.read_text())['url'] if settings.exists() else 'http://127.0.0.1:4311'))
STORE=Path.home()/'.rant-connect-local'/hashlib.sha256(ORIGIN.encode()).hexdigest()[:16];CONFIG=STORE/'device.json'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k):raise ValueError('Перенаправление сервиса отклонено.')

def api(path,data,token=''):
 req=urllib.request.Request(ORIGIN+path,json.dumps(data,ensure_ascii=False).encode(),{'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
 with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect).open(req,timeout=15) as response:return json.load(response)

class Controller:
 def __init__(self,gui=None,clipboard=None):
  if gui is None:
   import pyautogui as gui
  if clipboard is None:
   import pyperclip as clipboard
  self.gui=gui;self.clipboard=clipboard;self.gui.FAILSAFE=True;self.gui.PAUSE=.15;self.screen=None;self.stamp=None
 def execute(self,action,args):
  g=self.gui
  if action=='desktop_screenshot':
   shot=g.screenshot();native=shot.size;shot.thumbnail((1400,1000));self.screen=(native,shot.size);self.stamp=time.monotonic();out=io.BytesIO();shot.convert('RGB').save(out,format='JPEG',quality=65)
   return {'image':'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode(),'width':shot.width,'height':shot.height,'platform':platform.system(),'note':'Координаты относятся к этому снимку.'}
  if action=='desktop_click':
   if not self.screen or self.stamp is None or time.monotonic()-self.stamp>60:raise ValueError('Сначала получи новый снимок экрана.')
   x,y=args.get('x'),args.get('y');native,size=self.screen
   if type(x) is not int or type(y) is not int or not(0<=x<size[0] and 0<=y<size[1]):raise ValueError('Точка вне снимка.')
   # PyAutoGUI coordinates are logical points (Retina differs from screenshot pixels).
   width,height=g.size();g.click(round(x*width/size[0]),round(y*height/size[1]),clicks=2 if args.get('double') is True else 1,interval=.12);self.stamp=None
  elif action=='desktop_type':
   text=args.get('text')
   if not isinstance(text,str) or len(text)>8000:raise ValueError('Текст слишком длинный.')
   old=self.clipboard.paste()
   try:
    self.clipboard.copy(text);g.hotkey('command' if platform.system()=='Darwin' else 'ctrl','v');time.sleep(.2)
   finally:self.clipboard.copy(old)
   self.stamp=None
  elif action=='desktop_hotkey':
   keys=args.get('keys')
   if not isinstance(keys,list) or not 1<=len(keys)<=3 or any(not isinstance(k,str) or k not in g.KEYBOARD_KEYS for k in keys):raise ValueError('Неизвестные клавиши.')
   g.hotkey(*keys);self.stamp=None
  elif action=='desktop_scroll':
   steps=args.get('steps')
   if type(steps) is not int or not -10<=steps<=10:raise ValueError('Некорректная прокрутка.')
   g.scroll(steps);self.stamp=None
  else:raise ValueError('Действие не поддерживается.')
  return {'performed':True,'note':'Действие отправлено системе. Проверь результат новым снимком.'}

class App:
 def __init__(self):
  self.root=tk.Tk();self.root.title('Rant Connect Local');self.root.geometry('530x510');self.root.configure(bg='#17191d')
  self.events=queue.Queue();self.armed=threading.Event();self.closed=threading.Event();self.token='';self.controller=None
  if CONFIG.exists():
   try:self.token=json.loads(CONFIG.read_text()).get('token','')
   except (OSError,ValueError):pass
  label=lambda text,**kw:tk.Label(self.root,text=text,bg='#17191d',fg='#f3f4f6',wraplength=470,**kw).pack(padx=24,pady=8)
  label('Rant Connect Local',font=('Arial',24,'bold'))
  label(ORIGIN,font=('Arial',14))
  label('Когда управление включено, агент может видеть экран, нажимать кнопки и вводить текст по твоим заданиям. Снимки получает локальное приложение и выбранная модель. Управление выключено при каждом запуске.',justify='left')
  self.code=tk.Entry(self.root,font=('Arial',18),justify='center');self.code.pack(padx=24,pady=8,fill='x');self.code.insert(0,'')
  tk.Button(self.root,text='Подключить одноразовым кодом',command=self.pair).pack(pady=5)
  self.control=tk.Button(self.root,text='Включить управление',command=self.toggle,bg='#2675ef',fg='white',font=('Arial',14,'bold'));self.control.pack(padx=24,pady=12,fill='x')
  self.status=tk.Label(self.root,text='Управление выключено',bg='#17191d',fg='#9da7b5',wraplength=470);self.status.pack(pady=6)
  label('Экстренная остановка: перемести мышь в верхний левый угол. Закрытие окна отключает агент. На Mac нужны разрешения «Запись экрана» и «Универсальный доступ».',font=('Arial',10))
  self.root.protocol('WM_DELETE_WINDOW',self.close);self.root.after(100,self.tick)
  threading.Thread(target=self.loop,daemon=True).start()
 def pair(self):
  code=self.code.get().strip().replace(' ','')
  def work():
   try:
    data=api('/device/connect',{'code':code,'name':platform.node() or platform.system()});STORE.mkdir(parents=True,mode=0o700,exist_ok=True);STORE.chmod(0o700);tmp=CONFIG.with_suffix('.tmp');tmp.write_text(json.dumps(data));tmp.chmod(0o600);tmp.replace(CONFIG);self.token=data['token'];self.events.put('Компьютер подключён. Управление выключено.')
   except Exception:self.events.put('Не удалось подключиться. Проверь код и запущено ли локальное приложение; код действует пять минут.')
  if self.armed.is_set():self.toggle()
  threading.Thread(target=work,daemon=True).start()
 def toggle(self):
  if self.armed.is_set():self.armed.clear();self.control.config(text='Включить управление');self.status.config(text='Управление выключено')
  elif not self.token:messagebox.showinfo('Rant Connect','Сначала создай код в Rant → Инструменты → Компьютеры и подключись.')
  else:self.armed.set();self.control.config(text='Остановить управление');self.status.config(text='Агент может управлять этим компьютером')
 def loop(self):
  while not self.closed.is_set():
   if not self.token:self.closed.wait(2);continue
   try:
    result=api('/device/poll',{'armed':self.armed.is_set()},self.token);command=result.get('command')
    if command:
     output={'error':'Управление выключено.'}
     if self.armed.is_set():
      try:
       if self.controller is None:self.controller=Controller()
       output=self.controller.execute(command['action'],command.get('arguments',{}));self.events.put('Последнее действие: '+command['action'].replace('desktop_',''))
      except Exception as e:
       output={'error':'Действие не выполнено: '+str(e)[:200]};self.armed.clear();self.events.put('Управление остановлено. Проверь разрешения ОС или экстренную остановку.')
     # Never repeat a received command; the local relay reports uncertain delivery.
     api('/device/result',{'id':command['id'],'result':output},self.token)
   except urllib.error.HTTPError as e:
    if e.code in {401,403}:self.armed.clear();self.token='';CONFIG.unlink(missing_ok=True);self.events.put('Подключение отозвано. Создай новый код.')
    e.close()
   except Exception:
    self.armed.clear();self.events.put('Связь потеряна. Управление выключено; включи его после восстановления связи.')
   self.closed.wait(2)
 def tick(self):
  while not self.events.empty():self.status.config(text=self.events.get())
  if not self.armed.is_set():self.control.config(text='Включить управление')
  self.root.after(100,self.tick)
 def close(self):
  self.armed.clear();self.closed.set()
  # Best-effort heartbeat; queued commands expire even if offline.
  if self.token:
   threading.Thread(target=lambda:api('/device/poll',{'armed':False},self.token),daemon=True).start()
  self.root.destroy()
 def run(self):self.root.mainloop()
if __name__=='__main__':
 if '--self-test' in sys.argv:
  import PIL,pyautogui,pyperclip
  print(json.dumps({'tk':tk.Tcl().eval('info patchlevel'),'pillow':PIL.__version__,'platform':platform.system(),'frozen':bool(getattr(sys,'frozen',False))}))
 else:
  try:App().run()
  except Exception:
   STORE.mkdir(parents=True,exist_ok=True);log=STORE/'startup.log';log.write_text(traceback.format_exc());log.chmod(0o600)
   try:messagebox.showerror('Rant Connect','Не удалось запустить приложение. Подробности: '+str(log))
   except Exception:pass
