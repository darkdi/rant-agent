'use client';
import { useState } from 'react';
import {
  Settings2,
  FolderOpen,
  FolderPlus,
  ShieldCheck,
  Bot,
  Rocket,
  Download,
  Plus,
  Check,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu';
import { Switch } from '@/components/ui/switch';
export type Access = {
  files: 'none' | 'read' | 'write';
  web: boolean;
  release: boolean;
  browser: boolean;
  browser_auto?: boolean;
};
export type Agent = {
  id: string;
  name: string;
  mode: string;
  instruction: string;
};
type Release = {
  id: string;
  files: { path: string; bytes: number; sha256: string }[];
  bytes: number;
  published: boolean;
};
export type WorkspaceInfo = {
  projects?: { name: string; path: string }[];
  project_home?: string;
  permissions?: Access;
  search_has_key?: boolean;
  agents?: Agent[];
  releases?: Release[];
};
type Api = <T>(path: string, data?: unknown) => Promise<T>;
export default function WorkspaceControls({
  api,
  state,
  token,
  disabled,
  onProjectChanged,
  onRefresh,
  selectedAgent,
  onSelectAgent,
}: {
  api: Api;
  state: WorkspaceInfo & { project: string };
  token: string;
  disabled: boolean;
  onProjectChanged: () => Promise<void>;
  onRefresh: () => Promise<unknown>;
  selectedAgent: string;
  onSelectAgent: (a: Agent) => void;
}) {
  const [panel, setPanel] = useState(''),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState('');
  const [access, setAccess] = useState<Access>({
      files: 'write',
      web: false,
      release: false,
      browser: false,
    }),
    [searchKey, setSearchKey] = useState('');
  const [name, setName] = useState(''),
    [parent, setParent] = useState(''),
    [existing, setExisting] = useState('');
  const [agent, setAgent] = useState<Agent>({
      id: '',
      name: 'Мой агент',
      mode: 'read',
      instruction: '',
    }),
    [directory, setDirectory] = useState('.');
  const safely = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка');
    } finally {
      setBusy(false);
    }
  };
  function show(p: string) {
    setError('');
    setNotice('');
    setPanel(p);
    if (p === 'access')
      setAccess(
        state.permissions || {
          files: 'write',
          web: false,
          release: false,
          browser: false,
        },
      );
    if (p === 'projects') {
      setParent(state.project_home || '');
      setExisting(state.project);
    }
  }
  async function download(id: string) {
    const response = await fetch('/bridge/release-download?id=' + id, {
      headers: { 'X-Sever-Token': token },
    });
    if (!response.ok) throw Error('Не удалось скачать архив');
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'site-' + id.slice(0, 8) + '.zip';
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <>
      <div className="workspace-controls">
        <DropdownMenu>
          <DropdownMenuTrigger disabled={disabled} className="settings-entry">
            <Settings2 size={17} />
            Настройки и возможности
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" className="workspace-menu">
            <DropdownMenuItem onClick={() => show('access')}>
              <ShieldCheck size={16} />
              Доступы
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => show('projects')}>
              <FolderOpen size={16} />
              Папки проектов
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => show('agents')}>
              <Bot size={16} />
              Профили агентов
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => show('release')}>
              <Rocket size={16} />
              Подготовить публикацию
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <Dialog
        open={!!panel}
        onOpenChange={(open) => {
          if (!open) setPanel('');
        }}
      >
        <DialogContent className="settings-dialog tools-dialog">
          <DialogHeader>
            <DialogTitle>
              {{
                projects: 'Проекты',
                access: 'Доступы агента',
                agents: 'Профили агентов',
                release: 'Подготовить публикацию',
              }[panel] || ''}
            </DialogTitle>
            <DialogDescription>
              {panel === 'access'
                ? 'Доступ к файлам относится к этой папке. Доступ к Chrome сохраняется для всех проектов и чатов.'
                : panel === 'projects'
                  ? 'Создай отдельный проект или открой существующую папку.'
                  : panel === 'agents'
                    ? 'Роль, инструкции и режим работы. Агенты выполняются по одному.'
                    : 'Собери статический сайт в архив и проверь состав перед отправкой на сервер.'}
            </DialogDescription>
          </DialogHeader>
          {error && (
            <p className="message error" role="alert">
              {error}
            </p>
          )}
          {notice && <output className="message notice">{notice}</output>}
          {panel === 'projects' && (
            <>
              <div className="project-list">
                {state.projects?.map((p) => (
                  <button
                    key={p.path}
                    disabled={busy}
                    onClick={() =>
                      safely(async () => {
                        await api('project', { path: p.path });
                        await onProjectChanged();
                        setPanel('');
                      })
                    }
                  >
                    <FolderOpen size={15} />
                    <span>
                      <b>{p.name}</b>
                      <small>{p.path}</small>
                    </span>
                    {p.path === state.project && <Check size={13} />}
                  </button>
                ))}
              </div>
              <h3>Новый проект</h3>
              <div className="form-row">
                <label>
                  Название папки
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Мой проект"
                  />
                </label>
                <label>
                  Создать внутри
                  <input
                    value={parent}
                    onChange={(e) => setParent(e.target.value)}
                  />
                </label>
              </div>
              <p className="form-help">
                Проект создаётся пустым. Агент добавит нужные файлы по твоей
                задаче; для браузера файлы не нужны.
              </p>
              <Button
                disabled={busy || !name.trim()}
                onClick={() =>
                  safely(async () => {
                    await api('project-create', { name, parent });
                    await onProjectChanged();
                    setName('');
                    setPanel('');
                  })
                }
              >
                <FolderPlus size={14} />
                Создать и открыть
              </Button>
              <div className="section-divider" />
              <label>
                Открыть существующую папку
                <input
                  value={existing}
                  onChange={(e) => setExisting(e.target.value)}
                  placeholder="/Users/…/project"
                />
              </label>
              <Button
                variant="outline"
                disabled={busy}
                onClick={() =>
                  safely(async () => {
                    await api('project', { path: existing });
                    await onProjectChanged();
                    setPanel('');
                  })
                }
              >
                Открыть папку
              </Button>
            </>
          )}
          {panel === 'access' && (
            <>
              <code className="allowed-path">{state.project}</code>
              <p className="field-label">Файлы выбранного проекта</p>
              <Tabs
                value={access.files}
                onValueChange={(v) =>
                  setAccess({
                    ...access,
                    files: v as Access['files'],
                    release: v === 'none' ? false : access.release,
                  })
                }
              >
                <TabsList>
                  <TabsTrigger value="none">Нет доступа</TabsTrigger>
                  <TabsTrigger value="read">Только читать</TabsTrigger>
                  <TabsTrigger value="write">Читать и править</TabsTrigger>
                </TabsList>
              </Tabs>
              <div className="permission-row">
                <div>
                  <b>Поиск и чтение URL</b>
                  <small>
                    Чтение публичных HTTPS-страниц и поиск. Запросы уходят в
                    сеть.
                  </small>
                </div>
                <Switch
                  aria-label="Разрешить интернет"
                  checked={access.web}
                  onCheckedChange={(checked) =>
                    setAccess({ ...access, web: checked })
                  }
                />
              </div>
              <label>
                Ключ Brave Search API
                <input
                  type="password"
                  autoComplete="off"
                  value={searchKey}
                  onChange={(e) => setSearchKey(e.target.value)}
                  placeholder={
                    state.search_has_key
                      ? 'Ключ сохранён'
                      : 'Для поиска, необязателен для чтения URL'
                  }
                />
              </label>
              <p className="form-help">
                Ключ сохраняется после закрытия IDE. Получить его можно в{' '}
                <a
                  href="https://api-dashboard.search.brave.com/"
                  target="_blank"
                  rel="noreferrer"
                >
                  Brave Search API
                </a>
                . Без ключа можно читать известные URL.
              </p>
              <div className="permission-row">
                <div>
                  <b>Подготовка публикации</b>
                  <small>
                    Создать ZIP и перечень файлов. Ничего не отправляет на
                    сервер.
                  </small>
                </div>
                <Switch
                  aria-label="Разрешить подготовку публикации"
                  checked={access.release}
                  disabled={access.files === 'none'}
                  onCheckedChange={(checked) =>
                    setAccess({ ...access, release: checked })
                  }
                />
              </div>
              <div className="permission-row">
                <div>
                  <b>Браузерный агент</b>
                  <small>
                    Сам открывает сайты и вкладки, нажимает и заполняет формы по
                    твоим поручениям. Разрешение действует во всех проектах
                    после перезапуска.
                  </small>
                </div>
                <Switch
                  aria-label="Разрешить браузер"
                  checked={access.browser}
                  onCheckedChange={(checked) =>
                    setAccess({
                      ...access,
                      browser: checked,
                      browser_auto: checked,
                    })
                  }
                />
              </div>
              <p className="form-help">
                Один раз открой значок Rant Agent в Chrome и нажми «Разрешить
                Chrome». После этого сайты и вкладки агент открывает сам. При
                выборе API текст страниц получает выбранная модель. Пароли и
                коды вводи в браузере.
              </p>
              <div className="capability-note">
                <b>Терминал и SSH</b>
                <p>
                  Пока не подключены. Публикация готовит архив для проверки.
                </p>
              </div>
              <Button
                disabled={busy}
                onClick={() =>
                  safely(async () => {
                    await api('permissions', {
                      ...access,
                      search_key: searchKey,
                    });
                    setSearchKey('');
                    await onRefresh();
                    setNotice(
                      'Разрешения сохранены. Выбери подходящий режим под полем задачи.',
                    );
                  })
                }
              >
                Сохранить разрешения
              </Button>
            </>
          )}
          {panel === 'agents' && (
            <>
              <div className="project-list">
                {state.agents?.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => {
                      onSelectAgent(a);
                      setNotice('Выбран агент: ' + a.name);
                    }}
                  >
                    <Bot size={15} />
                    <span>
                      <b>{a.name}</b>
                      <small>
                        {a.mode === 'browser'
                          ? 'Работа в браузере'
                          : a.mode === 'edit'
                            ? 'Редактирование'
                            : a.mode === 'read'
                              ? 'Чтение и инструменты'
                              : 'Обсуждение'}
                      </small>
                    </span>
                    {selectedAgent === a.id && <Check size={14} />}
                  </button>
                ))}
              </div>
              <h3>Создать своего агента</h3>
              <label>
                Название
                <input
                  value={agent.name}
                  onChange={(e) => setAgent({ ...agent, name: e.target.value })}
                />
              </label>
              <label>
                Инструкции
                <textarea
                  value={agent.instruction}
                  onChange={(e) =>
                    setAgent({ ...agent, instruction: e.target.value })
                  }
                  placeholder="Например: проверяй доступность интерфейса, указывай файл и конкретную проблему…"
                />
              </label>
              <Tabs
                value={agent.mode}
                onValueChange={(v) => setAgent({ ...agent, mode: String(v) })}
              >
                <TabsList>
                  <TabsTrigger value="read">Чтение</TabsTrigger>
                  <TabsTrigger value="edit">Редактирование</TabsTrigger>
                  <TabsTrigger value="chat">Обсуждение</TabsTrigger>
                  <TabsTrigger value="browser">Браузер</TabsTrigger>
                </TabsList>
              </Tabs>
              <p className="form-help">
                Инструкции не расширяют права. Для сети включи интернет в
                «Доступах»; для правок — запись в папку.
              </p>
              <Button
                disabled={busy || !agent.name.trim()}
                onClick={() =>
                  safely(async () => {
                    const saved = await api<Agent>('agent', agent);
                    await onRefresh();
                    onSelectAgent(saved);
                    setAgent({
                      id: '',
                      name: 'Мой агент',
                      instruction: '',
                      mode: 'read',
                    });
                    setNotice('Агент сохранён и выбран');
                  })
                }
              >
                <Plus size={14} />
                Создать агента
              </Button>
            </>
          )}
          {panel === 'release' && (
            <>
              <p className="capability-note">
                Сервер назначения ещё не настроен. Архив можно скачать;
                автоматической отправки по SSH пока нет.
              </p>
              <label>
                Папка готового статического сайта
                <input
                  value={directory}
                  onChange={(e) => setDirectory(e.target.value)}
                  placeholder=". или dist"
                />
              </label>
              <p className="form-help">
                Нужен index.html. Упаковываются HTML, CSS, JS и медиа. Исходники
                Python/PHP, скрытые файлы и конфигурации не включаются.
              </p>
              <Button
                disabled={busy || !state.permissions?.release}
                onClick={() =>
                  safely(async () => {
                    await api('release', { directory });
                    await onRefresh();
                    setNotice('Архив подготовлен. Ничего не опубликовано.');
                  })
                }
              >
                <Rocket size={14} />
                Подготовить архив
              </Button>
              {!state.permissions?.release && (
                <button className="text-button" onClick={() => show('access')}>
                  Разрешить подготовку в «Доступах»
                </button>
              )}
              <div className="release-list">
                {state.releases?.map((r) => (
                  <details key={r.id}>
                    <summary>
                      Сборка {r.id.slice(0, 8)} · {r.files.length} файлов ·{' '}
                      {(r.bytes / 1024).toFixed(1)} КБ
                    </summary>
                    <ul>
                      {r.files.map((f) => (
                        <li key={f.path}>
                          {f.path} <small>{f.bytes} Б</small>
                        </li>
                      ))}
                    </ul>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => safely(() => download(r.id))}
                    >
                      <Download size={13} />
                      Скачать ZIP
                    </Button>
                  </details>
                ))}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
