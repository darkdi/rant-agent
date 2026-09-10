"""One reusable model process; each job still has its own tools, context and journal."""
import importlib.util,json,os,platform,signal,subprocess,sys,time
from pathlib import Path

class ResidentJob:
 def __init__(self,process,run):self.process=process;self.run=Path(run);self.pid=process.pid
 def poll(self):return 0 if (self.run/'resident.done').exists() else self.process.poll()
 @property
 def returncode(self):return self.poll()
 def wait(self,timeout=None):
  started=time.monotonic()
  while self.poll() is None:
   if timeout is not None and time.monotonic()-started>=timeout:raise subprocess.TimeoutExpired('local model job',timeout)
   time.sleep(.05)
  return self.poll()
 def kill(self):os.killpg(self.pid,signal.SIGKILL)

class LocalRuntime:
 def __init__(self,data,worker):self.data=Path(data);self.worker=Path(worker);self.process=None;self.log=None;self.run=None
 def alive(self):return self.process is not None and self.process.poll() is None
 def installation_error(self):
  if platform.system()!='Darwin' or platform.machine()!='arm64':return 'Встроенная Qwen через MLX требует Mac с Apple Silicon. На этом компьютере подключи модель через API или свой сервер.'
  config_path=self.worker.parent.parent.parent/'local-assistant/model-9b.json'
  try:
   config=json.loads(config_path.read_text())
   path=config.get('path') if isinstance(config,dict) else None
   if not isinstance(path,str) or not path.strip():raise ValueError()
   model=Path(path).expanduser()
   if not model.is_absolute():raise ValueError()
  except FileNotFoundError:return 'Локальная Qwen ещё не настроена: укажи путь к скачанным весам в local-assistant/model-9b.json.'
  except (OSError,ValueError,TypeError):return 'Проверь local-assistant/model-9b.json: поле path должно содержать полный путь к папке модели.'
  if not (model/'config.json').is_file() or not any(model.glob('*.safetensors')):return 'Файлы Qwen не найдены в указанной папке. Проверь путь к скачанной модели.'
  if importlib.util.find_spec('mlx_lm') is None or importlib.util.find_spec('mlx') is None:return 'Для локальной Qwen нужно установить mlx-lm в окружение Python, из которого запущено приложение.'
  return ''
 def ensure_available(self):
  error=self.installation_error()
  if error:raise ValueError(error)
 def submit(self,config):
  self.ensure_available()
  if not self.alive():
   if self.log:self.log.close()
   (self.data/'model-ready.json').unlink(missing_ok=True)
   self.log=(self.data/'model-runtime.log').open('a')
   self.process=subprocess.Popen([sys.executable,'-u',str(self.worker),'--resident'],stdin=subprocess.PIPE,stdout=self.log,stderr=subprocess.STDOUT,text=True,start_new_session=True)
  self.run=Path(config['run'])
  config={**config,'runtime_state':str(self.data/'model-ready.json')}
  self.process.stdin.write(json.dumps(config)+'\n');self.process.stdin.flush()
  return ResidentJob(self.process,config['run'])
 def state(self):
  info={'model':'Qwen3.5-9B','resident':bool(self.alive())}
  error=self.installation_error()
  if error:return {**info,'status':'unavailable','reason':error}
  ready=self.alive() and (self.data/'model-ready.json').exists()
  if self.run and not ready:
   try:
    report=json.loads((self.run/'report.json').read_text())
    if report.get('status')=='error':return {**info,'status':'error','reason':report.get('final') or 'Не удалось загрузить Qwen. Попробуй отправить сообщение ещё раз.'}
   except (OSError,ValueError):pass
  if self.process is not None and not self.alive() and self.run and not (self.run/'resident.done').exists():return {**info,'status':'error','reason':'Процесс Qwen завершился до ответа. Попробуй отправить сообщение ещё раз.'}
  loading=self.alive() and self.run is not None and not (self.run/'resident.done').exists()
  return {**info,'status':'ready' if ready else 'loading' if loading else 'cold'}
 def close(self):
  if self.alive():
   os.killpg(self.process.pid,signal.SIGINT)
   try:self.process.wait(timeout=8)
   except subprocess.TimeoutExpired:os.killpg(self.process.pid,signal.SIGKILL);self.process.wait()
  if self.log:self.log.close();self.log=None
  self.process=None;self.run=None;(self.data/'model-ready.json').unlink(missing_ok=True)
