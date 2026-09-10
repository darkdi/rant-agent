"""Local media studio: user-owned connections and files; no hosted billing.
Generation POSTs are never retried automatically. Only status GETs are polled.
"""
import base64
import copy
import hashlib
import http.client
import io
import ipaddress
import json
from pathlib import Path
import re
import socket
import ssl
import threading
import time
from urllib.parse import urlencode, urlsplit
import uuid
from PIL import Image
from credentials import CredentialStore

LIMIT = 100 * 1024 * 1024


def write(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    tmp.chmod(0o600)
    tmp.replace(path)


def endpoint(value, local_only=False):
    u = urlsplit(value)
    local = u.hostname in {'127.0.0.1', 'localhost', '::1'}
    if not u.hostname or u.username or u.password or u.query or u.fragment or u.scheme not in {'http', 'https'}:
        raise ValueError('Укажи адрес без логина, пароля, параметров и фрагмента.')
    if (local_only and not local) or (not local and u.scheme != 'https'):
        raise ValueError('ComfyUI должен быть локальным; удалённые API требуют HTTPS.')
    return value.rstrip('/')


def request(url, body=None, key='', limit=32*1024*1024, local_allowed=False):
    u = urlsplit(url)
    local = u.hostname in {'127.0.0.1', 'localhost', '::1'}
    if u.username or u.password or not u.hostname or u.fragment or u.scheme not in {'http', 'https'}:
        raise ValueError('Недопустимый адрес результата.')
    if local and not local_allowed or not local and u.scheme != 'https':
        raise ValueError('Недопустимый адрес результата.')
    port = u.port or (443 if u.scheme == 'https' else 80)
    addresses = [item[4][0] for item in socket.getaddrinfo(u.hostname, port, type=socket.SOCK_STREAM)]
    if not addresses or any(not (ipaddress.ip_address(ip).is_loopback if local else ipaddress.ip_address(ip).is_global) for ip in addresses):
        raise ValueError('Адрес не соответствует выбранному локальному или публичному серверу.')
    address = addresses[0]
    parent = http.client.HTTPSConnection if u.scheme == 'https' else http.client.HTTPConnection
    class Pinned(parent):
        def connect(self):
            sock = socket.create_connection((address, port), timeout=180)
            if u.scheme == 'https':
                try: sock = ssl.create_default_context().wrap_socket(sock, server_hostname=u.hostname)
                except BaseException: sock.close(); raise
            self.sock = sock
    conn = Pinned(u.hostname, port, timeout=180)
    try:
        headers = {'Accept-Encoding': 'identity'}
        if key: headers['Authorization'] = 'Bearer ' + key
        payload = json.dumps(body).encode() if body is not None else None
        if payload is not None: headers['Content-Type'] = 'application/json'
        conn.request('POST' if payload is not None else 'GET', (u.path or '/') + ('?' + u.query if u.query else ''), payload, headers)
        response = conn.getresponse()
        if not 200 <= response.status < 300:
            raise ValueError(f'Сервис вернул HTTP {response.status}. Проверь адрес, модель, ключ и параметры в кабинете сервиса.')
        raw = response.read(limit + 1)
        if len(raw) > limit: raise ValueError('Результат превышает допустимый размер.')
        return raw, response.getheader('Content-Type', '')
    finally:
        conn.close()


def json_request(url, body=None, key='', local_allowed=False):
    return json.loads(request(url, body, key, local_allowed=local_allowed)[0])


class MediaStudio:
    def __init__(self, data):
        self.root = Path(data) / 'media'
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.keys = CredentialStore(Path(data) / 'media-credentials')
        self.lock = threading.RLock()
        for path in self.root.glob('*/job.json'):
            job = json.loads(path.read_text())
            if job['status'] in {'queued', 'running'}:
                job.update(status='uncertain', error='Приложение перезапустилось. Проверь задачу у провайдера; повторной отправки не было.')
                write(path, job)

    def profiles(self):
        path = self.root / 'profiles.json'
        return json.loads(path.read_text()) if path.exists() else []

    def catalog(self):
        return [{**{k:v for k,v in p.items() if k != 'workflow'}, 'has_workflow':bool(p.get('workflow')), 'has_key':bool(self.keys.get(p['id'], p['base_url']))} for p in self.profiles()]

    def save_profile(self, d):
        with self.lock:
            name = str(d.get('name', '')).strip()
            adapter, kind = d.get('adapter'), d.get('kind')
            if adapter not in {'images', 'replicate', 'comfyui'} or kind not in {'image', 'video'} or not 1 <= len(name) <= 80:
                raise ValueError('Укажи название, тип результата и поддерживаемый сервис.')
            if adapter == 'images' and kind != 'image': raise ValueError('Images API создаёт только изображения. Для видео выбери Replicate или ComfyUI.')
            base = endpoint(str(d.get('base_url', '')), adapter == 'comfyui')
            if adapter == 'replicate' and base != 'https://api.replicate.com/v1': raise ValueError('Для Replicate используй https://api.replicate.com/v1.')
            model = str(d.get('model', '')).strip()
            if adapter != 'comfyui' and not 1 <= len(model) <= 200: raise ValueError('Укажи модель.')
            if adapter == 'replicate' and not re.fullmatch(r'[\w.-]+/[\w.-]+(?::[a-f0-9]{64})?', model): raise ValueError('Модель Replicate: owner/model или owner/model:version.')
            options = d.get('options', {})
            if not isinstance(options, dict) or len(json.dumps(options)) > 16000: raise ValueError('Параметры должны быть JSON-объектом до 16 КБ.')
            workflow = d.get('workflow', {})
            if adapter == 'comfyui' and (not isinstance(workflow, dict) or not workflow or '__PROMPT__' not in json.dumps(workflow) or len(json.dumps(workflow)) > 100000): raise ValueError('Вставь ComfyUI workflow в API-формате с __PROMPT__ в положительном промпте.')
            pid = d.get('id') or uuid.uuid4().hex
            if not re.fullmatch('[a-f0-9]{32}', pid): raise ValueError('Некорректный номер подключения.')
            item = dict(id=pid, name=name, adapter=adapter, kind=kind, base_url=base, model=model, options=options, workflow=workflow if adapter == 'comfyui' else {})
            self.keys.update(pid, base, d.get('key'), bool(d.get('clear_key')))
            profiles = [p for p in self.profiles() if p['id'] != pid] + [item]
            write(self.root / 'profiles.json', profiles)
            return next(p for p in self.catalog() if p['id'] == pid)

    def jobs(self):
        with self.lock:
            return sorted([json.loads(p.read_text()) for p in self.root.glob('*/job.json')], key=lambda j:j['created'], reverse=True)[:60]

    def create(self, data):
        prompt = str(data.get('prompt', '')).strip()
        nonce = str(data.get('nonce', ''))
        if not 1 <= len(prompt) <= 4000 or not re.fullmatch('[a-zA-Z0-9-]{16,80}', nonce): raise ValueError('Напиши описание до 4000 символов.')
        with self.lock:
            profiles = self.profiles()
            profile = next((p for p in profiles if p['id'] == data.get('profile_id')), None)
            if not profile: raise ValueError('Добавь и выбери подключение для генерации.')
            fingerprint = hashlib.sha256(json.dumps([profile['id'], prompt]).encode()).hexdigest()
            jobs = self.jobs()
            for job in jobs:
                if job['nonce'] == nonce:
                    if job['fingerprint'] != fingerprint: raise ValueError('Этот запрос уже использован для другой генерации.')
                    return job
            if any(j['status'] in {'queued', 'running'} for j in jobs): raise ValueError('Дождись текущей генерации.')
            if len(jobs) >= 60: raise ValueError('В галерее 60 работ. Сохрани нужные файлы и очисти .local/media при остановленном приложении.')
            if sum(p.stat().st_size for p in self.root.glob('*/result.*')) > 1024**3: raise ValueError('Галерея достигла 1 ГБ. Освободи локальное хранилище.')
            jid = uuid.uuid4().hex
            folder = self.root / jid
            folder.mkdir(mode=0o700)
            job = dict(id=jid, nonce=nonce, fingerprint=fingerprint, profile_id=profile['id'], model=profile['name'], prompt=prompt, kind=profile['kind'], created=time.time(), status='queued', error='', file=None)
            write(folder / 'job.json', job)
            threading.Thread(target=self.run, args=(job, copy.deepcopy(profile)), daemon=True).start()
            return job

    def update(self, job, **changes):
        with self.lock:
            job.update(changes)
            write(self.root / job['id'] / 'job.json', job)

    def download(self, url, profile):
        # Provider credentials are never forwarded to generated output URLs.
        base = urlsplit(profile['base_url'])
        result = urlsplit(url)
        same = (base.scheme, base.hostname, base.port) == (result.scheme, result.hostname, result.port)
        return request(url, limit=LIMIT, local_allowed=same)[0]

    def run(self, job, profile):
        self.update(job, status='running')
        try:
            base, adapter = profile['base_url'], profile['adapter']
            key = self.keys.get(profile['id'], base)
            local = urlsplit(base).hostname in {'127.0.0.1', 'localhost', '::1'}
            if adapter == 'images':
                body = {**profile['options'], 'model':profile['model'], 'prompt':job['prompt'], 'n':1}
                data = json_request(base + '/images/generations', body, key, local_allowed=local)['data'][0]
                raw = base64.b64decode(data['b64_json'], validate=True) if data.get('b64_json') else self.download(data['url'], profile)
            elif adapter == 'replicate':
                model = profile['model']
                body = {'input':{**profile['options'], 'prompt':job['prompt']}}
                if ':' in model:
                    body['version'] = model.split(':', 1)[1]
                    path = '/predictions'
                else: path = '/models/' + model + '/predictions'
                result = json_request(base + path, body, key)
                pid = result['id']
                if not re.fullmatch('[a-zA-Z0-9_-]+', pid): raise ValueError('Сервис вернул некорректный ID задачи.')
                self.update(job, provider_id=pid)
                for _ in range(240):
                    if result['status'] in {'succeeded', 'failed', 'canceled'}: break
                    time.sleep(5)
                    result = json_request(base + '/predictions/' + pid, key=key)
                if result['status'] != 'succeeded': raise ValueError('Генерация не завершена успешно. Проверь ID задачи в Replicate; повторной отправки не было.')
                output = result['output']
                url = output[0] if isinstance(output, list) and output else output
                if not isinstance(url, str): raise ValueError('Модель должна возвращать URL изображения или видео.')
                raw = self.download(url, profile)
            else:
                def replace(value):
                    if isinstance(value, str): return value.replace('__PROMPT__', job['prompt'])
                    if isinstance(value, list): return [replace(x) for x in value]
                    if isinstance(value, dict): return {k:replace(v) for k,v in value.items()}
                    return value
                result = json_request(base + '/prompt', {'prompt':replace(profile['workflow']), 'client_id':job['id']}, key, local_allowed=True)
                pid = result['prompt_id']
                if not re.fullmatch('[a-zA-Z0-9_-]+', pid): raise ValueError('ComfyUI вернул некорректный ID.')
                self.update(job, provider_id=pid)
                history = {}
                for _ in range(240):
                    history = json_request(base + '/history/' + pid, key=key, local_allowed=True).get(pid, {})
                    if history.get('outputs') or history.get('status', {}).get('completed') or history.get('status', {}).get('status_str') == 'error': break
                    time.sleep(5)
                candidates = [entry for output in history.get('outputs', {}).values() for category in ('images', 'gifs', 'videos') for entry in output.get(category, []) if isinstance(entry, dict)]
                extensions = {'.mp4', '.webm'} if job['kind'] == 'video' else {'.png', '.jpg', '.jpeg', '.webp'}
                file = next((entry for entry in candidates if Path(entry.get('filename','')).suffix.lower() in extensions), None)
                if not file: raise ValueError('Workflow не сохранил подходящий результат. Для видео нужен выход MP4/WebM, для картинки — PNG/JPEG/WebP.')
                query = {k:file.get(k,'') for k in ('filename','subfolder','type')}
                raw = request(base + '/view?' + urlencode(query), key=key, limit=LIMIT, local_allowed=True)[0]
            if len(raw) > LIMIT: raise ValueError('Результат больше 100 МБ.')
            if job['kind'] == 'image':
                with Image.open(io.BytesIO(raw)) as image:
                    if image.width * image.height > 32_000_000: raise ValueError('Изображение больше 32 мегапикселей.')
                    image.load(); buffer = io.BytesIO(); image.convert('RGB').save(buffer, 'PNG'); raw = buffer.getvalue()
                suffix = '.png'
            else:
                if raw[4:8] == b'ftyp': suffix = '.mp4'
                elif raw[:4] == b'\x1aE\xdf\xa3': suffix = '.webm'
                else: raise ValueError('Результат не является MP4 или WebM.')
            path = self.root / job['id'] / ('result' + suffix)
            path.write_bytes(raw); path.chmod(0o600)
            self.update(job, status='done', file=path.name)
        except Exception as error:
            message = str(error)
            key = self.keys.get(profile['id'], profile['base_url'])
            if key: message = message.replace(key, '[ключ скрыт]')
            self.update(job, status='uncertain', error=message[:600] + ' Автоматического повторного запроса не было; перед повтором проверь сервис.')

    def file(self, jid):
        if not re.fullmatch('[a-f0-9]{32}', jid): raise ValueError('Работа не найдена.')
        job = json.loads((self.root / jid / 'job.json').read_text())
        if job['status'] != 'done' or job.get('file') not in {'result.png', 'result.mp4', 'result.webm'}: raise ValueError('Результат ещё не готов.')
        return self.root / jid / job['file']
