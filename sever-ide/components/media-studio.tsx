'use client';
import { useEffect, useRef, useState } from 'react';
import { ImagePlus, Video, Download, Loader2, Plus, Settings2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';

type Kind = 'image' | 'video';
type Profile = { id: string; name: string; kind: Kind; adapter: string; model: string; base_url: string; has_key?: boolean };
type Job = { id: string; kind: Kind; model: string; prompt: string; status: string; error: string; file?: string; provider_id?: string };
type Api = <T>(path: string, data?: unknown) => Promise<T>;
const statusLabel: Record<string, string> = { queued: 'В очереди', running: 'Создаётся…', done: 'Готово', uncertain: 'Нужно проверить результат' };

function Result({ job, token }: { job: Job; token: string }) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    if (!job.file || !token) return;
    let active = true, objectUrl = '';
    const controller = new AbortController();
    fetch('/bridge/media-file?id=' + job.id, { headers: { 'X-Sever-Token': token }, signal: controller.signal })
      .then(r => { if (!r.ok) throw Error('Не удалось открыть файл'); return r.blob(); })
      .then(blob => { if (active) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); } })
      .catch(e => { if (active) setError(String(e.message)); });
    return () => { active = false; controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [job.id, job.file, token]);
  return <article className="media-result">
    {url ? (job.kind === 'video' ? <video src={url} controls preload="metadata" /> : <img src={url} alt={job.prompt} loading="lazy" />) : <div className="media-placeholder">{['queued', 'running'].includes(job.status) && <Loader2 className="animate-spin" />}{statusLabel[job.status] || job.status}</div>}
    <div><p>{job.prompt}</p><small>{job.model} · {statusLabel[job.status]}</small>{job.provider_id && <small>ID задачи: {job.provider_id}</small>}
      {(job.error || error) && <p role="alert" className="media-error">{job.error || error}</p>}
      {url && <a href={url} download={'rant-' + job.id + '.' + job.file?.split('.').pop()}><Download size={15} /> Скачать</a>}
    </div>
  </article>;
}

export default function MediaStudio({ kind, onClose, initialPrompt, api, token }: { kind: Kind | null; onClose: () => void; initialPrompt: string; api: Api; token: string }) {
  const [profiles, setProfiles] = useState<Profile[]>([]), [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState(''), [prompt, setPrompt] = useState('');
  const [settings, setSettings] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [adapter, setAdapter] = useState('images'), [name, setName] = useState(''), [base, setBase] = useState('https://api.openai.com/v1');
  const [model, setModel] = useState(''), [key, setKey] = useState(''), [options, setOptions] = useState('{}'), [workflow, setWorkflow] = useState('');
  const nonce = useRef('');
  useEffect(() => {
    if (!kind) return;
    setPrompt(initialPrompt); setError(''); setKey(''); nonce.current = '';
    preset(kind === 'video' ? 'replicate' : 'images');
    let alive = true;
    async function refresh() {
      try {
        const [connections, results] = await Promise.all([api<Profile[]>('media-profiles'), api<Job[]>('media-jobs')]);
        if (!alive) return;
        setProfiles(connections); setJobs(results);
        setSelected(old => connections.some(p => p.id === old && p.kind === kind) ? old : connections.find(p => p.kind === kind)?.id || '');
      } catch (e) { if (alive) setError((e as Error).message); }
    }
    void refresh(); const timer = setInterval(() => void refresh(), 4000);
    return () => { alive = false; clearInterval(timer); };
  }, [kind, api]);
  function preset(value: string) {
    setAdapter(value); setKey(''); setModel(''); setOptions('{}');
    setBase(value === 'comfyui' ? 'http://127.0.0.1:8188' : value === 'replicate' ? 'https://api.replicate.com/v1' : 'https://api.openai.com/v1');
  }
  async function save() {
    setBusy(true); setError('');
    try {
      const profile = await api<Profile>('media-profile', { name, kind, adapter, model, base_url: base, key, options: JSON.parse(options || '{}'), workflow: adapter === 'comfyui' ? JSON.parse(workflow) : {} });
      setProfiles(await api<Profile[]>('media-profiles')); setSelected(profile.id); setSettings(false); setKey(''); setName('');
    } catch (e) { setError(e instanceof SyntaxError ? 'Проверь JSON параметров и workflow.' : (e as Error).message); }
    finally { setBusy(false); }
  }
  async function create() {
    setBusy(true); setError('');
    if (!nonce.current) nonce.current = crypto.randomUUID();
    try {
      await api<Job>('media-create', { profile_id: selected, prompt, nonce: nonce.current });
      nonce.current = ''; setJobs(await api<Job[]>('media-jobs'));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const available = profiles.filter(p => p.kind === kind), active = jobs.some(j => ['queued', 'running'].includes(j.status));
  const showSettings = settings || !available.length;
  return <Dialog open={!!kind} onOpenChange={open => { if (!open) { setKey(''); setSettings(false); onClose(); } }}>
    <DialogContent className="settings-dialog media-studio"><DialogHeader><DialogTitle>{kind === 'video' ? <><Video size={23} /> Создать видео</> : <><ImagePlus size={23} /> Создать картинку</>}</DialogTitle><DialogDescription>Твой API или локальный движок. Готовые файлы сохраняются на этом компьютере.</DialogDescription></DialogHeader>
      <div className="media-tabs"><button className={!showSettings ? 'selected' : ''} disabled={!available.length} onClick={() => setSettings(false)}>Генерация</button><button className={showSettings ? 'selected' : ''} onClick={() => { preset(kind === 'video' ? 'replicate' : 'images'); setSettings(true); }}><Settings2 size={15} /> Добавить подключение</button><a href="/help.html#media" target="_blank" rel="noreferrer">Как настроить →</a></div>
      {showSettings ? <div className="media-form"><p className="form-help">Добавь отдельное подключение для {kind === 'video' ? 'видео' : 'изображений'}. Ключ чат-модели не подключает генерацию автоматически.</p>
        <label>Сервис<select value={kind === 'video' && adapter === 'images' ? '' : adapter} onChange={e => preset(e.target.value)}><option value="" disabled>Выбери сервис</option>{kind !== 'video' && <option value="images">Images API · OpenAI-совместимый</option>}<option value="replicate">Replicate · изображения и видео по API</option><option value="comfyui">ComfyUI · на этом компьютере</option></select></label>
        <label>Название<input value={name} onChange={e => setName(e.target.value)} placeholder="Например, локальный FLUX или видео через API" maxLength={80} /></label>
        <label>Адрес сервера<input value={base} onChange={e => setBase(e.target.value)} /></label>
        <label>API-ключ {adapter === 'comfyui' && '(необязательно)'}<input type="password" value={key} onChange={e => setKey(e.target.value)} autoComplete="off" placeholder="Хранится на этом компьютере" /></label>
        {adapter !== 'comfyui' && <label>Модель<input value={model} onChange={e => setModel(e.target.value)} placeholder={adapter === 'replicate' ? 'owner/model или owner/model:version' : 'Точный ID из документации провайдера'} /></label>}
        {adapter === 'comfyui' ? <><p className="form-help">В ComfyUI экспортируй рабочую схему в API-формате. Замени положительный промпт на __PROMPT__ и вставь JSON. Для видео схема должна сохранять MP4 или WebM.</p><label>Workflow JSON<textarea value={workflow} onChange={e => setWorkflow(e.target.value)} rows={7} placeholder='{"1":{"class_type":"…","inputs":{…}}}' /></label></> : <details><summary>Параметры модели</summary><p className="form-help">JSON из документации выбранной модели: размер, длительность, формат. Поле prompt заполняется описанием ниже.</p><textarea aria-label="Параметры модели JSON" value={options} onChange={e => setOptions(e.target.value)} rows={4} /></details>}
        <button className="media-primary" disabled={busy || !name.trim() || (kind === 'video' && adapter === 'images')} onClick={() => void save()}><Plus size={16} /> Сохранить подключение</button>
        <p className="form-help">Сохранение не запускает генерацию и не списывает деньги. Совместимость проверяется первым запросом.</p>
      </div> : <div className="media-form"><label>Подключение<select value={selected} onChange={e => { setSelected(e.target.value); nonce.current = ''; }}>{available.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Что создаём?<textarea value={prompt} maxLength={4000} rows={4} onChange={e => { setPrompt(e.target.value); nonce.current = ''; }} placeholder={kind === 'video' ? 'Опиши сцену, движение и настроение…' : 'Опиши сюжет, стиль и свет…'} /></label><button className="media-primary" disabled={busy || active || !selected || !prompt.trim()} onClick={() => void create()}>{busy || active ? <Loader2 className="animate-spin" size={17} /> : kind === 'video' ? <Video size={17} /> : <ImagePlus size={17} />}{active ? 'Генерация выполняется' : kind === 'video' ? 'Создать видео' : 'Создать картинку'}</button><p className="form-help">API оплачивается по тарифу твоего провайдера. ComfyUI использует ресурсы компьютера; внешние узлы workflow могут обращаться к API. Окно можно закрыть — задача продолжится, пока работает Rant.</p></div>}
      {error && <p className="message error" role="alert">{error}</p>}
      <div className="media-gallery">{jobs.filter(j => j.kind === kind).map(job => <Result key={job.id} job={job} token={token} />)}</div>
    </DialogContent>
  </Dialog>;
}
