"""Launch installed Google Chrome independently so finishing a task cannot close it."""
import json,re,subprocess,time
from pathlib import Path

CHROME=Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')

def owned_endpoint(profile):
 profile=Path(profile).resolve()
 try:
  meta=json.loads((profile/'.sever-chrome.json').read_text());pid=int(meta['pid'])
  command=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True,timeout=3).stdout
  if str(CHROME) not in command or '--user-data-dir='+str(profile) not in command:return None
  lines=(profile/'DevToolsActivePort').read_text().splitlines();port=int(lines[0]);path=lines[1]
  if not 1<=port<=65535 or not re.fullmatch(r'/devtools/browser/[a-zA-Z0-9-]+',path):return None
  return f'ws://127.0.0.1:{port}{path}'
 except (OSError,ValueError,KeyError,IndexError,subprocess.TimeoutExpired):return None

def chrome_endpoint(profile,headless=False):
 profile=Path(profile).resolve();profile.mkdir(parents=True,exist_ok=True,mode=0o700)
 endpoint=owned_endpoint(profile)
 if endpoint:return endpoint
 if not CHROME.is_file():raise ValueError('Установи Google Chrome в папку «Программы».')
 active=profile/'DevToolsActivePort';active.unlink(missing_ok=True)
 args=[str(CHROME),'--user-data-dir='+str(profile),'--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--no-first-run','--no-default-browser-check']
 if headless:args.append('--headless=new')
 args.append('about:blank')
 with (profile/'.sever-chrome.log').open('a') as log:
  process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 metadata=profile/'.sever-chrome.json';metadata.write_text(json.dumps({'pid':process.pid}));metadata.chmod(0o600)
 for _ in range(100):
  if process.poll() is not None:raise ValueError('Chrome не запустился. Закрой прежнее окно профиля агента и попробуй снова.')
  endpoint=owned_endpoint(profile)
  if endpoint:return endpoint
  time.sleep(.1)
 raise ValueError('Chrome запускается дольше обычного. Попробуй задачу ещё раз; открытое окно сохранится.')
