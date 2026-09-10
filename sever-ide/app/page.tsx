'use client';
import { isLocalEndpoint, needsApiKey } from '@/lib/model-connection';
import MediaStudio from '@/components/media-studio';
import { ImagePlus, Video } from 'lucide-react';
import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  MessageCircle,
  ChevronDown,
  PanelLeftOpen,
  ArrowDown,
  Copy,
  Pencil,
  Lightbulb,
  Sparkles,
  FolderOpen,
  FileCode2,
  Plus,
  ArrowUp,
  Square,
  Undo2,
  Check,
  ChevronRight,
  Code2,
  GitCompare,
  Activity,
  Globe,
  RefreshCw,
  Save,
  Loader2,
} from 'lucide-react';
import CodeMirror from '@uiw/react-codemirror';
import { html } from '@codemirror/lang-html';
import { javascript } from '@codemirror/lang-javascript';
import { css } from '@codemirror/lang-css';
import { python } from '@codemirror/lang-python';
import ChatSidebar from '@/components/chat-sidebar';
import { AccountMenu, RantCharacter, ThemeSwitch, useAccount, useRantTheme } from '@/components/account-gate';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu';
import ModelSettings from '@/components/model-settings';
import { CloudModels, CloudSubscription } from '@/components/cloud-service';
import IntegrationsPanel from '@/components/integrations-panel';
import ModelAnswer from '@/components/model-answer';
import {
  AttachmentPicker,
  AttachmentCards,
  type Attachment,
} from '@/components/chat-attachments';
import WorkspaceControls, {
  type WorkspaceInfo,
  type Agent,
} from '@/components/workspace-controls';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  SidebarProvider,
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarFooter,
} from '@/components/ui/sidebar';

type Profile = {
  id: string;
  name: string;
  kind: string;
  model: string;
  base_url: string;
  has_key?: boolean;
};
type Pending = {
  id: string;
  action: string;
  url: string;
  target?: string;
  text?: string;
  reason?: string;
  href?: string;
};
type Run = {
  attachments?: Attachment[];
  checks?: { errors?: string[]; warnings?: string[] };
  context?: { history_tasks: number; active_file: string };
  pending?: Pending;
  id: string;
  task: string;
  status: string;
  profile: string;
  final?: string;
  partial?: string;
  log?: string;
  changes?: string[];
  mode?: string;
};
type BrowserConnection = {
  connected: boolean;
  reason?: string;
  version?: string;
  capabilities?: { tabs?: boolean; all_sites?: boolean };
  tab?: { title?: string; url?: string };
  command?: { action?: string; stage?: string };
};
type State = WorkspaceInfo & {
  chats?: { id: string; title: string; count: number }[];
  browser?: BrowserConnection;
  conversation?: string;
  local_model?: { status: string; model: string; resident: boolean; reason?: string };
  project: string;
  files: string[];
  profiles: Profile[];
  runs: Run[];
  active: string | null;
  preview_url?: string;
};
const initial: State = {
  project: '',
  files: [],
  profiles: [],
  runs: [],
  active: null,
};
export default function Home() {
  const account = useAccount();
  const theme = useRantTheme();
  const modelStorageKey = 'rant-model:' + (account.user?.id || 'local');
  const [state, setState] = useState<State>(initial),
    [token, setToken] = useState(''),
    [error, setError] = useState(''),
    [notice, setNotice] = useState('');
  const [path, setPath] = useState(''),
    [content, setContent] = useState(''),
    [original, setOriginal] = useState(''),
    [task, setTask] = useState('');
  const [selected, setSelected] = useState('local-9b'),
    [view, setView] = useState('code'),
    [diff, setDiff] = useState(''),
    [busy, setBusy] = useState(false);
  const [mediaKind, setMediaKind] = useState<'image'|'video'|null>(null);
  const [dialog, setDialog] = useState(''),
    [project, setProject] = useState(''),
    [newPath, setNewPath] = useState('');
  const [decisionId, setDecisionId] = useState(''),
    [questionAnswer, setQuestionAnswer] = useState('');
  const [attached, setAttached] = useState<Attachment[]>([]),
    [uploading, setUploading] = useState(false);
  useEffect(() => {
    setAttached([]);
  }, [state.project, state.conversation]);
  const [agentId, setAgentId] = useState('assistant');
  const [sidebarOpen, setSidebarOpen] = useState(true),
    [follow, setFollow] = useState(true);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const [mode, setMode] = useState('chat'),
    [showFiles, setShowFiles] = useState(false),
    [run, setRun] = useState<Run | null>(null);
  useEffect(() => {
    setQuestionAnswer('');
  }, [run?.pending?.id]);
  const draftKey =
    state.project && state.conversation
      ? 'rant-draft:' + state.project + ':' + state.conversation
      : '';
  useEffect(() => {
    if (!draftKey) return;
    try {
      setTask(localStorage.getItem(draftKey) || '');
    } catch {
      setTask('');
    }
  }, [draftKey]);
  function updateDraft(value: string) {
    setTask(value);
    if (draftKey)
      try {
        if (value) localStorage.setItem(draftKey, value);
        else localStorage.removeItem(draftKey);
      } catch {}
  }
  const end = useRef<HTMLDivElement>(null);
  const dirty = content !== original;
  const api = useCallback(
    async <T,>(url: string, data?: unknown): Promise<T> => {
      const r = await fetch('/bridge/' + url, {
        method: data === undefined ? 'GET' : 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Sever-Token': token },
        body: data === undefined ? undefined : JSON.stringify(data),
      });
      if (r.status === 401 && account.cloud) window.dispatchEvent(new Event('rant-session-expired'));
      const j = await r.json();
      if (!r.ok)
        throw new Error(
          (j as { error?: string }).error || 'Не удалось выполнить действие',
        );
      return j as T;
    },
    [token, account.cloud],
  );
  const refresh = useCallback(async () => {
    const s = await api<State>('state');
    setState(s);
    return s;
  }, [api]);
  const safe = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка');
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    fetch('/bridge/session')
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json() as Promise<{ token: string }>;
      })
      .then((j) => setToken(j.token))
      .catch(() =>
        setError(account.cloud ? 'Соединение прервалось. Обнови страницу.' : 'Локальный сервер не запущен. Запусти start.sh или Start-Rant.command.'),
      );
  }, []);
  useEffect(() => {
    const context = (
      document as unknown as {
        modelContext?: {
          registerTool: (tool: unknown, options: unknown) => Promise<void>;
        };
      }
    ).modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();
    Promise.resolve(
      context.registerTool(
        {
          name: 'stage_agent_task',
          title: 'Подготовить задачу',
          description:
            'Заполняет поле задачи в IDE. Не отправляет запрос модели и не меняет файлы.',
          inputSchema: {
            type: 'object',
            properties: { task: { type: 'string' } },
            required: ['task'],
            additionalProperties: false,
          },
          annotations: { readOnlyHint: false },
          execute: async (input: unknown) => {
            const task = (input as { task?: unknown })?.task;
            if (typeof task !== 'string' || !task.trim() || task.length > 12000)
              throw Error('Нужен текст задачи до 12000 символов');
            setTask(task);
            return { staged: true, submitted: false };
          },
        },
        { signal: lifecycle.signal },
      ),
    ).catch(() => {});
    return () => lifecycle.abort();
  }, []);
  useEffect(() => {
    if (token)
      refresh()
        .then(async (s) => {
          if (!run && s.runs.length)
            setRun(await api<Run>('run?id=' + s.runs.at(-1)!.id));
        })
        .catch((e) => setError(e.message));
  }, [token, refresh]);
  useEffect(() => {
    try {
      if (localStorage.getItem('rant-chat-ui') === '2') {
        const remembered = localStorage.getItem('rant-mode');
        if (
          remembered &&
          ['edit', 'read', 'chat', 'browser'].includes(remembered)
        ) {
          setMode(remembered);
          setAgentId(
            remembered === 'chat'
              ? 'assistant'
              : remembered === 'browser'
                ? 'browser'
                : 'developer',
          );
        }
      } else {
        localStorage.setItem('rant-chat-ui', '2');
        localStorage.setItem('rant-mode', 'chat');
      }
      if (window.innerWidth < 900) setSidebarOpen(false);
      const saved = localStorage.getItem(modelStorageKey) || (!account.cloud ? localStorage.getItem('sever-model') : null);
      if (saved) setSelected(saved);
    } catch {}
  }, []);
  useEffect(() => {
    if (token)
      try {
        localStorage.setItem(modelStorageKey, selected);
      } catch {}
  }, [selected, token]);
  useEffect(() => {
    if (state.profiles.length && !state.profiles.some(p => p.id === selected)) setSelected(state.profiles[0].id);
  }, [state.profiles, selected]);
  useEffect(() => {
    if (!state.active || !token) return;
    const id = state.active;
    const controller = new AbortController();
    let finished = false;
    let poll: ReturnType<typeof setTimeout> | undefined;
    async function update(j: Run) {
      if (controller.signal.aborted || finished) return;
      setRun(j);
      if (j.status !== 'running') {
        finished = true;
        await refresh();
        if (j.changes?.length) {
          await showDiff(j.id);
          if (path && !dirty) {
            const f = await api<{ content: string }>(
              'file?path=' + encodeURIComponent(path),
            );
            setContent(f.content);
            setOriginal(f.content);
          }
        }
      }
    }
    async function fallback() {
      if (controller.signal.aborted || finished) return;
      try {
        await update(await api<Run>('run?id=' + encodeURIComponent(id)));
      } catch {}
      if (!finished && !controller.signal.aborted)
        poll = setTimeout(fallback, 1200);
    }
    void (async () => {
      try {
        const response = await fetch(
          '/bridge/run-stream?id=' + encodeURIComponent(id),
          { headers: { 'X-Sever-Token': token }, signal: controller.signal },
        );
        if (!response.ok || !response.body) throw Error('stream');
        const reader = response.body.getReader(),
          decoder = new TextDecoder();
        let buffer = '';
        while (!finished) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let boundary;
          while ((boundary = buffer.indexOf('\n\n')) >= 0) {
            const frame = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            const data = frame
              .split('\n')
              .filter((l) => l.startsWith('data: '))
              .map((l) => l.slice(6))
              .join('\n');
            if (data) await update(JSON.parse(data) as Run);
          }
        }
        await reader.cancel();
        if (!finished && !controller.signal.aborted) void fallback();
      } catch {
        if (!controller.signal.aborted) void fallback();
      }
    })();
    return () => {
      controller.abort();
      if (poll) clearTimeout(poll);
    };
  }, [state.active, token, api, refresh, path, dirty]);
  useEffect(() => {
    if (mode !== 'browser' || !token) return;
    const timer = setInterval(
      () =>
        api<BrowserConnection>('browser-status')
          .then((browser) => setState((s) => ({ ...s, browser })))
          .catch(() => {}),
      2000,
    );
    return () => clearInterval(timer);
  }, [mode, token, api]);
  useEffect(() => {
    if (follow) end.current?.scrollIntoView({ block: 'nearest' });
  }, [run?.log, run?.final, run?.partial, run?.pending?.id, follow]);
  useEffect(() => {
    if (showFiles && state.files.length && !path)
      void openFile(
        state.files.includes('index.html') ? 'index.html' : state.files[0],
      );
  }, [state.files, path, showFiles]);
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        document.getElementById('save-file')?.click();
      }
    };
    window.addEventListener('keydown', f);
    return () => window.removeEventListener('keydown', f);
  }, []);
  async function openFile(name: string) {
    if (activeProfile?.kind === 'local' && state.local_model?.status === 'unavailable') {
      setDialog('models');
      return;
    }
    if (dirty) {
      setError(
        'Сначала сохрани открытый файл или нажми «Обновить», чтобы сбросить правки.',
      );
      return;
    }
    await safe(async () => {
      const f = await api<{ content: string }>(
        'file?path=' + encodeURIComponent(name),
      );
      setPath(name);
      setContent(f.content);
      setOriginal(f.content);
      setView('code');
    });
  }
  async function showDiff(id: string, file?: string) {
    const result = await api<{ diff: string }>(
      'diff?id=' +
        encodeURIComponent(id) +
        (file ? '&path=' + encodeURIComponent(file) : ''),
    );
    setDiff(result.diff);
    setView('diff');
  }
  async function start() {
    if (!task.trim() || uploading || busy || state.active) return;
    if (needsApiKey(activeProfile)) {
      setDialog('models');
      setNotice(
        account.cloud ? 'Выбери модель из каталога.' : 'Введи API-ключ в настройках подключения. Он сохранится и будет подхватываться после перезапуска.',
      );
      return;
    }
    if (dirty) {
      setError('Сохрани файл перед запуском агента.');
      return;
    }
    await safe(async () => {
      const j = await api<Run>('run', {
        task,
        attachments: attached.map((a) => a.id),
        profile_id: selected,
        mode,
        agent_id: agentId,
        active_file: path,
        view,
      });
      setRun(j);
      setDiff('');
      updateDraft('');
      setAttached([]);
      setNotice('');
      setFollow(true);
      if (composerRef.current) composerRef.current.style.height = 'auto';
      await refresh();
    });
  }
  useEffect(() => {
    if (token)
      try {
        localStorage.setItem('rant-mode', mode);
      } catch {}
  }, [mode, token]);
  useEffect(() => {
    if (token)
      try {
        localStorage.setItem('rant-show-files', String(showFiles));
      } catch {}
  }, [showFiles, token]);
  const extensions = useMemo(() => {
    const ext = path.split('.').pop();
    return ext === 'html'
      ? [html()]
      : ['js', 'jsx', 'ts', 'tsx'].includes(ext || '')
        ? [javascript({ jsx: true, typescript: ext === 'ts' || ext === 'tsx' })]
        : ext === 'css'
          ? [css()]
          : ext === 'py'
            ? [python()]
            : [];
  }, [path]);
  async function reloadLibrary() {
    const next = await refresh();
    if (next.project !== state.project) {
      setPath('');
      setContent('');
      setOriginal('');
      setDiff('');
    }
    if (
      next.project !== state.project ||
      next.conversation !== state.conversation
    ) {
      setTask('');
      setAttached([]);
      setFollow(true);
    }
    setRun(
      next.runs.length
        ? await api<Run>('run?id=' + next.runs.at(-1)!.id)
        : null,
    );
  }
  async function chooseChat(id?: string) {
    if (id === state.conversation) return;
    await safe(async () => {
      await api(
        id ? 'conversation-select' : 'conversation-new',
        id ? { id } : {},
      );
      setRun(null);
      setDiff('');
      setNotice('');
      setTask('');
      setFollow(true);
      if (!id) {
        setMode('chat');
        setAgentId('assistant');
        setShowFiles(false);
      }
      const next = await refresh();
      if (next.runs.length)
        setRun(await api<Run>('run?id=' + next.runs.at(-1)!.id));
    });
  }
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (!state.active && !busy && !dirty) void chooseChat();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [state.active, busy, dirty, api]);
  const activeProfile = state.profiles.find((p) => p.id === selected);
  const displayRuns = state.runs.filter((r) => r.id !== run?.id);
  return (
    <div
      className={
        'ide rant-chat-layout' +
        (showFiles ? ' files-open' : '') +
        (sidebarOpen ? ' sidebar-open' : ' sidebar-closed')
      }
    >
      <ChatSidebar
        api={api}
        onBusy={setBusy}
        project={state.project}
        projects={state.projects || []}
        chats={state.chats || []}
        current={state.conversation}
        disabled={busy || uploading || !!state.active || dirty}
        open={sidebarOpen}
        close={() => setSidebarOpen(false)}
        choose={chooseChat}
        reload={reloadLibrary}
      >
        <WorkspaceControls
          api={api}
          state={state}
          token={token}
          disabled={busy || uploading || !!state.active || dirty}
          onProjectChanged={reloadLibrary}
          onRefresh={refresh}
          selectedAgent={agentId}
          onSelectAgent={(agent: Agent) => {
            setAgentId(agent.id);
            setMode(agent.mode);
          }}
        />
        <IntegrationsPanel api={api} />
        <div className="media-nav"><button onClick={() => setMediaKind('image')}><ImagePlus size={17}/> Картинки</button><button onClick={() => setMediaKind('video')}><Video size={17}/> Видео</button></div>
        {account.cloud && <CloudSubscription />}
        <AccountMenu />
      </ChatSidebar>
      <header className="topbar">
        <div className="header-start">
          {!sidebarOpen && (
            <button
              className="icon-button"
              aria-label="Показать меню"
              onClick={() => setSidebarOpen(true)}
            >
              <PanelLeftOpen size={21} />
            </button>
          )}
          <button
            className="profile-switch"
            onClick={() => setDialog('models')}
          >
            <span>{activeProfile?.model || 'Выбрать модель'}</span>
            <ChevronDown size={16} />
          </button>
          <span className="model-location">
            {account.cloud ? 'Rant' : activeProfile?.kind === 'local' || isLocalEndpoint(activeProfile?.base_url) ? 'На компьютере' : 'API'}
          </span>
        </div>
        <div className="header-tools">
          <ThemeSwitch />
          {state.active && (
            <span className="header-working">
              <span className="connected-dot" />В работе
            </span>
          )}
          <button
            className={'files-toggle' + (showFiles ? ' selected' : '')}
            aria-label="Файлы и код"
            aria-pressed={showFiles}
            onClick={() => setShowFiles(!showFiles)}
          >
            <Code2 size={17} />
            <span>{showFiles ? 'Закрыть файлы' : 'Файлы'}</span>
          </button>
        </div>
      </header>
      <div className="workbench">
        {showFiles && (
          <SidebarProvider className="file-provider">
            <Sidebar collapsible="none" className="file-sidebar">
              <SidebarHeader>
                <div className="section-heading">
                  ПРОЕКТ
                  <button
                    aria-label="Открыть папку"
                    title="Открыть папку"
                    onClick={() => {
                      setProject(state.project);
                      setDialog('project');
                    }}
                  >
                    <FolderOpen size={15} />
                  </button>
                  <button
                    aria-label="Создать файл"
                    title="Создать файл"
                    disabled={!!state.active}
                    onClick={() => setDialog('new')}
                  >
                    <Plus size={15} />
                  </button>
                </div>
                <div className="folder-name" title={state.project}>
                  <ChevronRight size={13} />
                  <FolderOpen size={15} />
                  {state.project.split('/').pop() || 'Загрузка…'}
                </div>
              </SidebarHeader>
              <SidebarContent>
                <nav className="file-tree" aria-label="Файлы проекта">
                  <FileTree
                    files={state.files}
                    selected={path}
                    open={openFile}
                  />
                </nav>
              </SidebarContent>
              <SidebarFooter>
                <div className="local-note">
                  <span className="status-dot" />
                  Папка на твоём компьютере
                </div>
                <small className="muted">HTML → сайт · «Код» → редактор</small>
                <small className="muted">
                  {state.files.length} файлов · изменения с откатом
                </small>
              </SidebarFooter>
            </Sidebar>
          </SidebarProvider>
        )}
        {showFiles && (
          <main className="editor">
            <div className="editor-heading">
              <span>
                <FileCode2 size={14} />
                {path || 'Открой файл'}
                {dirty && <i className="dirty-dot" />}
              </span>
              <div>
                <button
                  title="Обновить с диска и сбросить несохранённые правки"
                  aria-label="Обновить файл"
                  disabled={!path || busy || !!state.active}
                  onClick={() =>
                    safe(async () => {
                      const f = await api<{ content: string }>(
                        'file?path=' + encodeURIComponent(path),
                      );
                      setContent(f.content);
                      setOriginal(f.content);
                    })
                  }
                >
                  <RefreshCw size={14} />
                </button>
                <Button
                  id="save-file"
                  size="sm"
                  disabled={!dirty || busy || !!state.active}
                  onClick={() =>
                    safe(async () => {
                      await api<{ content: string }>('file', {
                        path,
                        content,
                        previous: original,
                      });
                      setOriginal(content);
                      setNotice('Файл сохранён');
                      await refresh();
                    })
                  }
                >
                  <Save size={13} />
                  Сохранить
                </Button>
              </div>
            </div>
            <Tabs
              value={view}
              onValueChange={(v) => setView(String(v))}
              className="editor-tabs"
            >
              <div className="editor-subbar">
                <TabsList variant="line">
                  <TabsTrigger value="code">
                    <Code2 size={13} />
                    Код
                  </TabsTrigger>
                  <TabsTrigger
                    value="diff"
                    onClick={() =>
                      safe(async () => {
                        const id = run?.id || state.runs.at(-1)?.id;
                        if (id) await showDiff(id);
                        else setDiff('Пока нет изменений.');
                      })
                    }
                  >
                    <GitCompare size={13} />
                    Изменения
                  </TabsTrigger>
                  <TabsTrigger value="log">
                    <Activity size={13} />
                    Журнал
                  </TabsTrigger>
                </TabsList>
                <span className="language">
                  {path.split('.').pop()?.toUpperCase() || 'TEXT'}
                </span>
              </div>
              <TabsContent value="code" className="code-pane">
                {!state.files.length ? (
                  <div className="empty-project">
                    <FolderOpen size={32} />
                    <h2>В этом проекте пока нет файлов</h2>
                    <p>
                      Создай файл или открой другой проект через кнопку
                      «Проекты» сверху.
                    </p>
                    <Button
                      disabled={!!state.active || busy}
                      onClick={() => setDialog('new')}
                    >
                      <Plus size={15} />
                      Создать файл
                    </Button>
                    <small>{state.project}</small>
                  </div>
                ) : (
                  <CodeMirror
                    aria-label="Редактор кода"
                    value={content}
                    height="100%"
                    theme={theme}
                    extensions={extensions}
                    editable={!!path && !state.active}
                    onChange={(value) => setContent(value)}
                    basicSetup={{
                      lineNumbers: true,
                      foldGutter: true,
                      highlightActiveLine: true,
                      autocompletion: true,
                      searchKeymap: true,
                    }}
                  />
                )}
              </TabsContent>
              <TabsContent value="diff" className="output-pane">
                <div className="diff-title">
                  <b>Изменения этой задачи</b>
                  <span>{run?.task || 'Выбери задачу'}</span>
                </div>
                <pre>
                  {diff.split('\n').map((line, i) => (
                    <div
                      key={i}
                      className={
                        line.startsWith('+')
                          ? 'diff-add'
                          : line.startsWith('-')
                            ? 'diff-remove'
                            : ''
                      }
                    >
                      {line || ' '}
                    </div>
                  ))}
                </pre>
              </TabsContent>
              <TabsContent value="log" className="output-pane">
                <pre>
                  {run?.log ||
                    'Действия агента появятся здесь после запуска задачи.'}
                </pre>
              </TabsContent>
            </Tabs>
            <div className="editor-footer">
              <span>
                {dirty ? '● Есть несохранённые правки' : '✓ Сохранено на диске'}
              </span>
              <span>UTF-8 · {content.split('\n').length} строк</span>
            </div>
          </main>
        )}
        <section className="agent-panel">
          <div className="agent-heading">
            <span>
              {state.chats?.find((c) => c.id === state.conversation)?.title ||
                'Новый чат'}
            </span>
            {state.preview_url && (
              <a
                href={state.preview_url}
                target="_blank"
                rel="noreferrer"
                className="preview-link"
              >
                Открыть сайт ↗
              </a>
            )}
          </div>
          <div
            className="conversation"
            onScroll={(e) => {
              const node = e.currentTarget;
              setFollow(
                node.scrollHeight - node.scrollTop - node.clientHeight < 120,
              );
            }}
          >
            {!state.runs.length && !run && (
              <div className="chat-welcome">
                <div className="welcome-symbol"><RantCharacter /><span className="welcome-spark" aria-hidden="true">✦</span></div>
                <h1>Что сделаем <span>сегодня?</span></h1>
                <p className="intro">
                  Твои идеи. Любые вопросы. Давай разберёмся вместе.
                </p>
                {(!state.profiles.some(p => p.kind !== 'local') && state.local_model?.status === 'unavailable') && <div className="first-connection"><b>Выбери, где будет работать модель</b><p>Ollama или LM Studio на твоём компьютере, встроенная Qwen на Mac либо API со своим ключом.</p><button onClick={() => setDialog('models')}>Подключить первую модель</button><a href="/help.html" target="_blank" rel="noreferrer">Инструкция по установке</a></div>}
                <div className="welcome-suggestions">
                  <button onClick={() => setMediaKind('image')}><ImagePlus size={18}/><span>Создать картинку</span></button>
                  <button onClick={() => setMediaKind('video')}><Video size={18}/><span>Создать видео</span></button>
                  {[
                    {
                      icon: Lightbulb,
                      title: 'Придумать идею',
                      text: 'Помоги придумать идею для нового проекта. Давай начнём с моих интересов.',
                    },
                    {
                      icon: Pencil,
                      title: 'Написать текст',
                      text: 'Помоги написать текст. Сначала уточни для кого и с какой целью.',
                    },
                    {
                      icon: Sparkles,
                      title: 'Разобраться в теме',
                      text: 'Помоги разобраться в сложной теме простыми словами.',
                    },
                    {
                      icon: Globe,
                      title: 'Поручить браузеру',
                      text: 'Помоги выполнить задачу в браузере.',
                    },
                  ].map((item, i) => (
                    <button
                      key={item.title}
                      onClick={() => {
                        setTask(item.text);
                        if (i === 3) {
                          setMode('browser');
                          setAgentId('browser');
                        }
                        composerRef.current?.focus();
                      }}
                    >
                      <item.icon size={18} />
                      {item.title}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {!!displayRuns.length && (
              <div className="conversation-history" aria-label="Сообщения чата">
                {displayRuns.map((r) => (
                  <div className="past-run" key={r.id}>
                    <div className="user-message">
                      {r.task}
                      {!!r.attachments?.length && (
                        <AttachmentCards items={r.attachments} token={token} />
                      )}
                    </div>
                    <ModelAnswer
                      text={r.final || 'Задача сохранена в журнале.'}
                    />
                    <div className="answer-actions">
                      <CopyAnswer text={r.final || ''} />
                      <button
                        aria-label="Изменить запрос"
                        title="Изменить и отправить как новое сообщение"
                        onClick={() => {
                          setTask(r.task);
                          composerRef.current?.focus();
                        }}
                      >
                        <Pencil size={15} />
                      </button>
                    </div>
                    {!!r.changes?.length && (
                      <button
                        className="text-button"
                        onClick={() =>
                          safe(async () => {
                            await showDiff(r.id);
                            setShowFiles(true);
                            setMode('read');
                          })
                        }
                      >
                        Изменённые файлы <ChevronRight size={12} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
            {run && (
              <div className="current-run">
                <div className="user-message">
                  {run.task}
                  {!!run.attachments?.length && (
                    <AttachmentCards items={run.attachments} token={token} />
                  )}
                </div>
                <div className="run-status">
                  {run.status === 'running' ? (
                    <Loader2 size={14} className="spin" />
                  ) : (
                    <Check size={14} />
                  )}{' '}
                  {run.status === 'running'
                    ? run.pending
                      ? 'Нужно твоё действие'
                      : run.partial
                        ? 'Пишет ответ…'
                        : run.mode === 'chat'
                          ? 'Готовлю ответ…'
                          : run.mode === 'browser'
                            ? 'Работаю в браузере…'
                            : 'Работаю с файлами…'
                    : run.status === 'model_finished'
                      ? run.checks?.warnings?.length
                        ? 'Есть предупреждения'
                        : 'Готово'
                      : run.status === 'validation_warnings'
                        ? 'Есть предупреждения'
                        : run.status === 'validation_failed'
                          ? 'Проверка выявила ошибки'
                          : run.status === 'connection_error'
                            ? 'Нет связи с Chrome'
                            : run.status === 'needs_user'
                              ? 'Нужно твоё действие'
                              : run.status === 'incomplete'
                                ? 'Выполнение не подтверждено'
                                : run.status === 'error'
                                  ? 'Не удалось завершить'
                                  : run.status === 'undone'
                                    ? 'Правки отменены'
                                    : 'Остановлено — проверь результат'}
                </div>
                {run.log && (
                  <details className="activity-details">
                    <summary>Действия агента</summary>
                    <pre className="live-log">{run.log}</pre>
                  </details>
                )}
                {run.partial &&
                  (!run.final ||
                    ![
                      'model_finished',
                      'validation_warnings',
                      'validation_failed',
                    ].includes(run.status)) && (
                    <div className="streaming-answer">
                      <ModelAnswer text={run.partial} />
                      {run.status === 'running' && (
                        <span className="stream-cursor" />
                      )}
                    </div>
                  )}
                {run.status === 'running' && run.pending && (
                  <section
                    className="browser-approval"
                    aria-label="Подтверждение действия"
                  >
                    <b>
                      {run.pending.action === 'question'
                        ? 'Вопрос по задаче'
                        : run.pending.action === 'manual'
                          ? 'Нужен ручной ввод в браузере'
                          : {
                              click: 'Нажать на элемент',
                              type: 'Ввести текст',
                              select: 'Выбрать вариант',
                            }[run.pending.action] || 'Действие браузера'}
                    </b>
                    <small>{run.pending.url}</small>
                    {run.pending.reason && <p>{run.pending.reason}</p>}
                    {run.pending.action === 'question' && (
                      <textarea
                        className="question-answer"
                        aria-label="Ответ агенту"
                        value={questionAnswer}
                        maxLength={4000}
                        onChange={(e) => setQuestionAnswer(e.target.value)}
                        placeholder="Ответь здесь — агент продолжит сам"
                      />
                    )}
                    {run.pending.target && <p>Элемент: {run.pending.target}</p>}
                    {run.pending.href && (
                      <small>Ссылка: {run.pending.href}</small>
                    )}
                    {run.pending.text !== undefined && (
                      <pre>{run.pending.text}</pre>
                    )}
                    {!['manual', 'question'].includes(run.pending.action) && (
                      <small>
                        «Всегда разрешать» сохраняет доступ для всех проектов,
                        включая отправку форм по твоему поручению. Отключить
                        можно в «Доступах».
                      </small>
                    )}
                    <div>
                      <Button
                        disabled={
                          busy ||
                          decisionId === run.pending.id ||
                          (run.pending.action === 'question' &&
                            !questionAnswer.trim())
                        }
                        onClick={() =>
                          safe(async () => {
                            const id = run.pending!.id;
                            await api('browser-decision', {
                              run_id: run.id,
                              id,
                              decision: 'approve',
                              response: questionAnswer,
                            });
                            setDecisionId(id);
                            setRun(await api<Run>('run?id=' + run.id));
                          })
                        }
                      >
                        {decisionId === run.pending.id
                          ? 'Решение принято'
                          : run.pending.action === 'question'
                            ? 'Ответить и продолжить'
                            : run.pending.action === 'manual'
                              ? 'Готово, продолжай'
                              : 'Выполнить'}
                      </Button>
                      {!['manual', 'question'].includes(run.pending.action) && (
                        <Button
                          variant="outline"
                          disabled={busy || decisionId === run.pending.id}
                          onClick={() =>
                            safe(async () => {
                              const id = run.pending!.id;
                              await api('browser-decision', {
                                run_id: run.id,
                                id,
                                decision: 'approve_project',
                              });
                              setDecisionId(id);
                            })
                          }
                        >
                          Всегда разрешать
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        disabled={busy || decisionId === run.pending.id}
                        onClick={() =>
                          safe(async () => {
                            const id = run.pending!.id;
                            await api('browser-decision', {
                              run_id: run.id,
                              id,
                              decision: 'reject',
                            });
                            setDecisionId(id);
                          })
                        }
                      >
                        Отклонить
                      </Button>
                    </div>
                  </section>
                )}
                {run.final && (
                  <>
                    <ModelAnswer text={run.final} />
                    <div className="answer-actions">
                      <CopyAnswer text={run.final} />
                      <button
                        aria-label="Изменить запрос"
                        title="Изменить и отправить как новое сообщение"
                        disabled={!!state.active}
                        onClick={() => {
                          setTask(run.task);
                          composerRef.current?.focus();
                        }}
                      >
                        <Pencil size={15} />
                      </button>
                    </div>
                  </>
                )}
                {!!run.changes?.length && (
                  <div className="changed-list">
                    {run.changes.map((f) =>
                      /\.html?$/i.test(f) ? (
                        <div className="changed-file-row" key={f}>
                          <a
                            className="changed-file"
                            href={previewFileUrl(f)}
                            target="_blank"
                            rel="noreferrer"
                            title="Открыть локальную страницу"
                          >
                            <Globe size={12} />
                            {f} ↗
                          </a>
                          <button
                            aria-label={'Изменения ' + f}
                            title="Посмотреть изменения"
                            onClick={() =>
                              safe(async () => {
                                await showDiff(run.id, f);
                                setShowFiles(true);
                              })
                            }
                          >
                            <GitCompare size={13} />
                          </button>
                        </div>
                      ) : (
                        <button
                          key={f}
                          className="changed-file"
                          onClick={() =>
                            safe(async () => {
                              await showDiff(run.id, f);
                              setShowFiles(true);
                            })
                          }
                        >
                          <FileCode2 size={12} />
                          {f}
                          <GitCompare size={12} />
                        </button>
                      ),
                    )}
                  </div>
                )}
                {run.status !== 'running' &&
                  run.mode !== 'browser' &&
                  run.mode !== 'chat' &&
                  run.checks && (
                    <div className="check-evidence">
                      <b>Проверка IDE</b>
                      {run.checks.errors?.map((x, i) => (
                        <p className="check-error" key={'e' + i}>
                          {x}
                        </p>
                      ))}
                      {run.checks.warnings?.map((x, i) => (
                        <p className="check-warning" key={'w' + i}>
                          {x}
                        </p>
                      ))}
                      {run.checks.errors &&
                        !run.checks.errors.length &&
                        !run.checks.warnings?.length && (
                          <p>Статические проверки пройдены.</p>
                        )}
                      {run.mode !== 'browser' && run.mode !== 'chat' && (
                        <small>
                          Работа кнопок и внешний вид автоматически не
                          проверялись.
                        </small>
                      )}
                    </div>
                  )}
                {run.status !== 'running' && !!run.changes?.length && (
                  <button
                    className="text-button"
                    disabled={busy || !!state.active}
                    onClick={() =>
                      safe(async () => {
                        await api('undo', { id: run.id });
                        setNotice('Правки этой задачи отменены');
                        setRun(null);
                        await refresh();
                        if (path) {
                          const f = await api<{ content: string }>(
                            'file?path=' + encodeURIComponent(path),
                          );
                          setContent(f.content);
                          setOriginal(f.content);
                        }
                      })
                    }
                  >
                    <Undo2 size={13} />
                    Откатить эту задачу
                  </button>
                )}
              </div>
            )}
            <div ref={end} />
          </div>
          {!follow && (
            <button
              className="scroll-bottom"
              aria-label="К последнему сообщению"
              onClick={() => {
                setFollow(true);
                end.current?.scrollIntoView({
                  behavior: 'smooth',
                  block: 'nearest',
                });
              }}
            >
              <ArrowDown size={18} />
            </button>
          )}
          <div className="composer-area">
            {mode === 'browser' && (
              <div className="browser-inline-status">
                <Globe size={14} />
                <b>
                  {state.browser?.connected
                    ? 'Chrome подключён'
                    : 'Подключи Chrome через расширение'}
                </b>
                <span>{state.browser?.tab?.title}</span>
                <button
                  onClick={() =>
                    safe(async () => {
                      await api('browser-reconnect', {});
                      await refresh();
                    })
                  }
                >
                  Проверить
                </button>
              </div>
            )}
            <>
              {mode === 'browser' &&
                state.browser?.connected &&
                !state.browser.capabilities?.all_sites && (
                  <p className="message notice">
                    {state.browser.capabilities?.tabs
                      ? 'В расширении Rant Agent нажми «Разрешить Chrome» один раз. Затем сайты и вкладки агент открывает сам.'
                      : 'Открой значок расширения в Chrome → «Обновить расширение». Затем снова открой его и нажми «Разрешить Chrome».'}
                  </p>
                )}
            </>
            <div className="context-bar" hidden>
              <span title="Агент сам ведёт внутренние рабочие заметки. Свежая страница и текущая цель имеют приоритет.">
                Контекст обновляется автоматически
                {path && mode !== 'browser' ? ' · ' + path : ''}
              </span>
            </div>
            <div className="access-caption" hidden>
              {mode === 'browser'
                ? state.permissions?.browser
                  ? state.permissions.browser_auto
                    ? 'Браузер · постоянное разрешение включено'
                    : 'Браузер · действия с подтверждением'
                  : 'Включи браузер в разделе «Доступы»'
                : mode === 'edit'
                  ? 'Доступ: чтение и правка папки проекта'
                  : mode === 'read'
                    ? 'Доступ: только чтение папки проекта'
                    : 'Без доступа к файлам · выбери «Читать» или «Править файлы»'}
            </div>
            {error && (
              <div className="message error" role="alert">
                {error}
                <button
                  aria-label="Закрыть ошибку"
                  onClick={() => setError('')}
                >
                  ×
                </button>
              </div>
            )}
            {notice && (
              <output className="message notice">
                {notice}
                <button
                  aria-label="Закрыть уведомление"
                  onClick={() => setNotice('')}
                >
                  ×
                </button>
              </output>
            )}
            <div className="composer">
              {!!attached.length && (
                <AttachmentCards
                  items={attached}
                  token={token}
                  onRemove={(id) =>
                    setAttached((a) => a.filter((x) => x.id !== id))
                  }
                />
              )}
              <textarea
                ref={composerRef}
                aria-label="Сообщение"
                placeholder={
                  mode === 'browser'
                    ? 'Что сделать в браузере?'
                    : mode === 'edit'
                      ? 'Что сделать с файлами?'
                      : mode === 'read'
                        ? 'Что изучить в проекте?'
                        : 'Спроси или поручи задачу…'
                }
                value={task}
                rows={1}
                onChange={(e) => {
                  updateDraft(e.target.value);
                  e.target.style.height = 'auto';
                  e.target.style.height =
                    Math.min(220, e.target.scrollHeight) + 'px';
                }}
                onKeyDown={(e) => {
                  if (
                    e.key === 'Enter' &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing
                  ) {
                    e.preventDefault();
                    void start();
                  }
                }}
              />
              <div className="composer-controls">
                <AttachmentPicker
                  items={attached}
                  onChange={setAttached}
                  api={api}
                  onError={setError}
                  onBusy={setUploading}
                  disabled={busy || !!state.active}
                />
                <DropdownMenu>
                  <DropdownMenuTrigger
                    className="mode-picker"
                    disabled={!!state.active}
                  >
                    <span>
                      {
                        {
                          chat: 'Чат',
                          browser: 'Браузер',
                          edit: 'Работа с файлами',
                          read: 'Изучить файлы',
                        }[mode]
                      }
                    </span>
                    <ChevronDown size={14} />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent side="top" className="mode-menu">
                    {[
                      {
                        id: 'chat',
                        title: 'Чат',
                        note: 'Вопросы, тексты, идеи и анализ',
                        icon: MessageCircle,
                      },
                      {
                        id: 'browser',
                        title: 'Браузер',
                        note: 'Действия на сайтах через Chrome',
                        icon: Globe,
                      },
                      {
                        id: 'edit',
                        title: 'Работа с файлами',
                        note: 'Создание и редактирование в проекте',
                        icon: Code2,
                      },
                      {
                        id: 'read',
                        title: 'Изучить файлы',
                        note: 'Чтение проекта без изменений',
                        icon: FolderOpen,
                      },
                    ].map((item) => (
                      <DropdownMenuItem
                        key={item.id}
                        onClick={() => {
                          setMode(item.id);
                          setAgentId(
                            item.id === 'chat'
                              ? 'assistant'
                              : item.id === 'browser'
                                ? 'browser'
                                : item.id === 'read'
                                  ? 'reviewer'
                                  : 'developer',
                          );
                        }}
                      >
                        <item.icon size={18} />
                        <span>
                          {item.title}
                          <small>{item.note}</small>
                        </span>
                        {mode === item.id && <Check size={15} />}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
                {state.active ? (
                  <button
                    className="send stop"
                    aria-label="Остановить агента"
                    onClick={() =>
                      safe(async () => {
                        await api('stop', { id: state.active });
                        setNotice('Останавливаю задачу…');
                      })
                    }
                  >
                    <Square size={16} />
                  </button>
                ) : (
                  <button
                    className="send"
                    aria-label="Отправить задачу"
                    disabled={!task.trim() || busy || uploading || !token}
                    onClick={start}
                  >
                    <ArrowUp size={20} />
                  </button>
                )}
              </div>
            </div>
            <div className="composer-foot">
              <span>
                {needsApiKey(activeProfile) ? (
                  <>{account.cloud ? 'Выбери модель, чтобы начать' : 'Добавь API-ключ в «Подключениях»'}</>
                ) : activeProfile?.kind === 'local' ? (
                  <>
                    <span className="status-dot" style={{background:state.local_model?.status==='unavailable'||state.local_model?.status==='error'?'var(--rant-soft)':undefined}} />
                    {state.local_model?.status === 'ready'
                      ? 'Qwen в памяти'
                      : state.local_model?.status === 'loading'
                        ? 'Qwen загружается'
                        : state.local_model?.status === 'unavailable'
                          ? 'Qwen требует настройки'
                          : state.local_model?.status === 'error'
                            ? 'Ошибка загрузки Qwen · открой настройки модели'
                            : 'Qwen загрузится при первом сообщении'}
                  </>
                ) : (
                  <>
                    <Globe size={11} />
                    {isLocalEndpoint(activeProfile?.base_url) ? 'Локальный сервер · API-ключ не обязателен' : 'Данные задачи получает выбранный API'}
                  </>
                )}
              </span>
              <span>Enter — отправить · Shift Enter — строка</span>
            </div>
          </div>
        </section>
      </div>
      <MediaStudio kind={mediaKind} onClose={() => setMediaKind(null)} initialPrompt={task} api={api} token={token} />
      {account.cloud ? <CloudModels open={dialog === 'models'} onClose={() => setDialog('')} profiles={state.profiles} selected={selected} onSelect={setSelected} disabled={!!state.active || busy} /> : <ModelSettings
        open={dialog === 'models'}
        onClose={() => setDialog('')}
        profiles={state.profiles}
        selected={selected}
        onSelect={setSelected}
        api={api}
        refresh={refresh}
        disabled={!!state.active || busy}
        localStatus={state.local_model?.status}
        localReason={state.local_model?.reason}
      />}
      <Dialog
        open={!!dialog && dialog !== 'models'}
        onOpenChange={(open) => {
          if (!open) setDialog('');
        }}
      >
        <DialogContent className="settings-dialog">
          <DialogHeader>
            <DialogTitle>
              {dialog === 'models'
                ? 'Модели и подключения'
                : dialog === 'project'
                  ? 'Открыть папку проекта'
                  : 'Новый файл'}
            </DialogTitle>
            <DialogDescription>
              {dialog === 'models'
                ? 'Локальная модель или твой API. Переключай без перенастройки проекта.'
                : dialog === 'project'
                  ? 'Агент сможет читать и изменять файлы внутри выбранной папки.'
                  : 'Вложенные папки создадутся автоматически.'}
            </DialogDescription>
          </DialogHeader>
          {error && (
            <div className="message error" role="alert">
              {error}
            </div>
          )}
          {notice && <output className="message notice">{notice}</output>}
          {dialog === 'project' ? (
            <>
              <label>
                Полный путь к папке
                <input
                  value={project}
                  onChange={(e) => setProject(e.target.value)}
                  placeholder="/Users/…/my-project"
                />
              </label>
              <Button
                disabled={busy || uploading || !!state.active || dirty}
                onClick={() =>
                  safe(async () => {
                    await api('project', { path: project });
                    setPath('');
                    setContent('');
                    setOriginal('');
                    setRun(null);
                    await refresh();
                    setDialog('');
                  })
                }
              >
                Открыть папку
              </Button>
            </>
          ) : (
            <>
              <label>
                Путь внутри проекта
                <input
                  value={newPath}
                  onChange={(e) => setNewPath(e.target.value)}
                  placeholder="assets/js/app.js"
                />
              </label>
              <Button
                disabled={busy || uploading || !!state.active || dirty}
                onClick={() =>
                  safe(async () => {
                    await api<{ content: string }>('file', {
                      path: newPath,
                      content: '',
                      previous: null,
                    });
                    await refresh();
                    setPath(newPath);
                    setContent('');
                    setOriginal('');
                    setNewPath('');
                    setDialog('');
                  })
                }
              >
                Создать файл
              </Button>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function previewFileUrl(path: string) {
  return (
    (typeof location !== 'undefined' && (!['localhost', '127.0.0.1'].includes(location.hostname) || location.port === '4320') ? '/preview/' : 'http://127.0.0.1:4312/') + path.split('/').map(encodeURIComponent).join('/')
  );
}
function FileTree({
  files,
  selected,
  open,
  prefix = '',
}: {
  files: string[];
  selected: string;
  open: (path: string) => void;
  prefix?: string;
}) {
  const children = Array.from(
    new Set(
      files
        .filter((f) => f.startsWith(prefix))
        .map((f) => f.slice(prefix.length).split('/')[0]),
    ),
  ).sort((a, b) => {
    const ad = files.some((f) => f.startsWith(prefix + a + '/')),
      bd = files.some((f) => f.startsWith(prefix + b + '/'));
    return Number(bd) - Number(ad) || a.localeCompare(b);
  });
  return (
    <>
      {children.map((name) => {
        const full = prefix + name,
          folder = files.some((f) => f.startsWith(full + '/'));
        if (folder)
          return (
            <details key={full} open className="tree-folder">
              <summary>
                <FolderOpen size={13} />
                {name}
              </summary>
              <FileTree
                files={files}
                selected={selected}
                open={open}
                prefix={full + '/'}
              />
            </details>
          );
        if (/\.html?$/i.test(full))
          return (
            <div
              key={full}
              className={
                'file-preview-row' + (selected === full ? ' active-file' : '')
              }
            >
              <a
                className="file"
                href={previewFileUrl(full)}
                target="_blank"
                rel="noreferrer"
                title={'Открыть локальную страницу ' + full}
              >
                <Globe size={14} />
                <span>{name}</span>
              </a>
              <button
                className="file-code-button"
                aria-label={'Редактировать код ' + full}
                title="Редактировать код"
                onClick={() => open(full)}
              >
                <Code2 size={13} />
                <span>Код</span>
              </button>
            </div>
          );
        return (
          <button
            key={full}
            className={selected === full ? 'file active-file' : 'file'}
            onClick={() => open(full)}
            title={full}
          >
            <FileCode2 size={14} />
            <span>{name}</span>
          </button>
        );
      })}
    </>
  );
}

function CopyAnswer({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      aria-label={copied ? 'Скопировано' : 'Скопировать ответ'}
      title={copied ? 'Скопировано' : 'Скопировать ответ'}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1800);
        } catch {
          setCopied(false);
        }
      }}
    >
      {copied ? <Check size={15} /> : <Copy size={15} />}
    </button>
  );
}
