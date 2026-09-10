'use client';
import { BrandLogo } from '@/components/brand-logo';
import { useState, type ReactNode } from 'react';
import { useAccount } from '@/components/account-gate';
import {
  Plus,
  Search,
  FolderOpen,
  MessageCircle,
  MoreHorizontal,
  Pencil,
  Trash2,
  RotateCcw,
  PanelLeftClose,
  X,
  FolderPlus,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
type Item = {
  kind: 'conversation' | 'project';
  id?: string;
  path?: string;
  title: string;
  root?: string;
};
type Props = {
  api: <T>(path: string, data?: unknown) => Promise<T>;
  onBusy: (busy: boolean) => void;
  project: string;
  projects: { name: string; path: string }[];
  chats: { id: string; title: string; count: number }[];
  current?: string;
  disabled: boolean;
  open: boolean;
  close: () => void;
  choose: (id?: string) => void;
  reload: () => Promise<void>;
  children: ReactNode;
};
export default function ChatSidebar(p: Props) {
  const account = useAccount();
  const [query, setQuery] = useState(''),
    [edit, setEdit] = useState<Item | null>(null),
    [name, setName] = useState(''),
    [create, setCreate] = useState(false),
    [trash, setTrash] = useState<Item[] | null>(null),
    [undo, setUndo] = useState<Item | null>(null),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  async function safe(fn: () => Promise<void>) {
    setBusy(true);
    p.onBusy(true);
    setError('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось сохранить');
    } finally {
      setBusy(false);
      p.onBusy(false);
    }
  }
  async function remove(item: Item) {
    await safe(async () => {
      await p.api(item.kind + '-delete', item);
      setUndo({ ...item, root: p.project });
      await p.reload();
    });
  }
  async function restore(item: Item) {
    if (item.kind === 'conversation' && item.root && item.root !== p.project)
      await p.api('project', { path: item.root });
    await p.api(item.kind + '-restore', item);
    setUndo(null);
    await p.reload();
    if (trash) setTrash((await p.api<{ items: Item[] }>('trash')).items);
  }
  function menu(item: Item) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger
          className="row-menu"
          aria-label={'Меню: ' + item.title}
          disabled={p.disabled || busy}
        >
          <MoreHorizontal size={17} />
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="start"
          side="right"
          className="library-menu"
        >
          <DropdownMenuItem
            onClick={() => {
              setEdit(item);
              setName(item.title);
              setError('');
            }}
          >
            <Pencil size={15} />
            Переименовать
          </DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onClick={() => remove(item)}>
            <Trash2 size={15} />
            Удалить
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }
  function closeMobile() {
    if (window.innerWidth <= 900) p.close();
  }
  const matches = (s: string) =>
    s.toLocaleLowerCase().includes(query.toLocaleLowerCase());
  return (
    <>
      {p.open && (
        <button
          className="sidebar-scrim"
          aria-label="Закрыть боковую панель"
          onClick={p.close}
        />
      )}
      <aside
        className={'library-sidebar' + (p.open ? ' is-open' : '')}
        aria-label="Навигация"
      >
        <div className="library-brand">
          <BrandLogo />
          <button
            className="icon-button"
            aria-label="Свернуть меню"
            onClick={p.close}
          >
            <PanelLeftClose size={18} />
          </button>
        </div>
        <button
          className="nav-new"
          disabled={p.disabled || busy}
          onClick={() => {
            p.choose();
            closeMobile();
          }}
        >
          <Plus size={20} />
          Новый чат<span>⌘ K</span>
        </button>
        <label className="nav-search">
          <Search size={16} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск чатов и проектов"
            aria-label="Поиск чатов и проектов"
          />
          {query && (
            <button aria-label="Очистить поиск" onClick={() => setQuery('')}>
              <X size={13} />
            </button>
          )}
        </label>
        <div className="library-scroll">
          <div className="nav-label">
            Проекты
            <button
              className="icon-button"
              aria-label="Создать проект"
              disabled={p.disabled || busy}
              onClick={() => {
                setCreate(true);
                setName('');
                setError('');
              }}
            >
              <Plus size={15} />
            </button>
          </div>
          <div className="library-projects">
            {p.projects
              .filter((x) => matches(x.name))
              .map((x) => (
                <div
                  className={
                    'nav-row' + (x.path === p.project ? ' current-project' : '')
                  }
                  key={x.path}
                >
                  <button
                    className="nav-item"
                    disabled={p.disabled || busy}
                    title={x.path}
                    onClick={() =>
                      void safe(async () => {
                        await p.api('project', { path: x.path });
                        await p.reload();
                        closeMobile();
                      })
                    }
                  >
                    <FolderOpen size={17} />
                    <span>{x.name}</span>
                  </button>
                  {menu({ kind: 'project', path: x.path, title: x.name })}
                </div>
              ))}
          </div>
          <div className="nav-label">
            Чаты{' '}
            <span className="nav-context">
              {p.projects.find((x) => x.path === p.project)?.name}
            </span>
          </div>
          <div className="library-chats">
            {p.chats
              .filter((x) => matches(x.title))
              .map((x) => (
                <div
                  className={
                    'nav-row' + (x.id === p.current ? ' current-chat' : '')
                  }
                  key={x.id}
                >
                  <button
                    className="nav-item"
                    disabled={p.disabled || busy}
                    title={x.title}
                    onClick={() => {
                      p.choose(x.id);
                      closeMobile();
                    }}
                  >
                    <MessageCircle size={15} />
                    <span>{x.title}</span>
                  </button>
                  {menu({ kind: 'conversation', id: x.id, title: x.title })}
                </div>
              ))}
            {query && !p.chats.some((x) => matches(x.title)) && (
              <p className="nav-empty">Чатов с таким названием нет</p>
            )}
          </div>
        </div>
        <div className="library-footer">
          {error && !edit && !create && (
            <div className="message error" role="alert">
              {error}
            </div>
          )}
          {undo && (
            <output className="undo-toast">
              <span>Перемещено в корзину</span>
              <button
                disabled={busy || p.disabled}
                onClick={() => safe(() => restore(undo))}
              >
                Отменить
              </button>
              <button aria-label="Закрыть" onClick={() => setUndo(null)}>
                <X size={13} />
              </button>
            </output>
          )}
          {p.children}
          <button
            className="nav-trash"
            disabled={p.disabled || busy}
            onClick={() =>
              safe(async () =>
                setTrash((await p.api<{ items: Item[] }>('trash')).items),
              )
            }
          >
            <Trash2 size={16} />
            Корзина
          </button>
          <div className="local-identity" hidden={account.cloud}>
            <span className="user-avatar">R</span>
            <span>
              Твоё пространство<small>История сохраняется локально</small>
            </span>
            <span className="connected-dot" />
          </div>
        </div>
      </aside>
      <Dialog
        open={!!edit || create}
        onOpenChange={(open) => {
          if (!open) {
            setEdit(null);
            setCreate(false);
          }
        }}
      >
        <DialogContent className="settings-dialog library-dialog">
          <DialogHeader>
            <DialogTitle>
              {create
                ? 'Новый проект'
                : edit?.kind === 'project'
                  ? 'Название проекта'
                  : 'Название чата'}
            </DialogTitle>
            <DialogDescription>
              {create
                ? 'Отдельное пространство для разговоров, материалов и задач. Начнём с пустой папки.'
                : edit?.kind === 'project'
                  ? 'Название в списке. Папка с файлами останется на месте.'
                  : 'Название поможет быстро найти разговор.'}
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void safe(async () => {
                if (create) await p.api('project-create', { name });
                else if (edit)
                  await p.api(edit.kind + '-rename', { ...edit, title: name });
                await p.reload();
                setEdit(null);
                setCreate(false);
              });
            }}
          >
            <label>
              Название
              <input
                aria-label="Название"
                value={name}
                maxLength={create ? 80 : 120}
                onChange={(e) => setName(e.target.value)}
                placeholder={
                  create ? 'Например, идеи для бизнеса' : 'Название чата'
                }
              />
            </label>
            {error && (
              <p className="message error" role="alert">
                {error}
              </p>
            )}
            <div className="dialog-actions">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setEdit(null);
                  setCreate(false);
                }}
              >
                Отмена
              </Button>
              <Button
                disabled={busy || p.disabled || !name.trim()}
                type="submit"
              >
                {busy ? (
                  'Сохраняю…'
                ) : create ? (
                  <>
                    <FolderPlus size={15} />
                    Создать проект
                  </>
                ) : (
                  'Сохранить'
                )}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog
        open={trash !== null}
        onOpenChange={(open) => {
          if (!open) setTrash(null);
        }}
      >
        <DialogContent className="settings-dialog">
          <DialogHeader>
            <DialogTitle>Корзина</DialogTitle>
            <DialogDescription>
              Удалённые чаты этого проекта и удалённые проекты. Рабочие файлы
              остаются на компьютере.
            </DialogDescription>
          </DialogHeader>
          {error && (
            <p className="message error" role="alert">
              {error}
            </p>
          )}
          {!trash?.length ? (
            <div className="trash-empty">
              <Trash2 size={32} />
              <p>Здесь пока пусто</p>
            </div>
          ) : (
            <div className="trash-list">
              {trash.map((x) => (
                <div key={x.id || x.path}>
                  {x.kind === 'project' ? (
                    <FolderOpen size={18} />
                  ) : (
                    <MessageCircle size={18} />
                  )}
                  <span>
                    {x.title}
                    <small>{x.kind === 'project' ? 'Проект' : 'Чат'}</small>
                  </span>
                  <button
                    disabled={busy || p.disabled}
                    aria-label={'Восстановить ' + x.title}
                    onClick={() => safe(() => restore(x))}
                  >
                    <RotateCcw size={16} />
                    Восстановить
                  </button>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
