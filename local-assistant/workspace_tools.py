"""Constrained text-file tools. No shell, network or arbitrary code execution."""
import difflib
import json
import os
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from site_validation import validate

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'sever-ide/projects/demo'
ALLOWED = {'.html', '.css', '.js', '.json', '.txt'}

class References(HTMLParser):
    def __init__(self):
        super().__init__(); self.refs=[]; self.ids=set(); self.titles=0; self.h1=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if 'id' in attrs: self.ids.add(attrs['id'])
        if tag=='title': self.titles+=1
        if tag=='h1': self.h1+=1
        for key in ('href','src'):
            if attrs.get(key): self.refs.append(attrs[key])

class Workspace:
    def __init__(self, run_dir, root=SITE):
        self.root=Path(root).resolve(); self.run=Path(run_dir); self.run.mkdir(parents=True,exist_ok=True)
        self.changes=[]; self.read_versions={}
    def path(self, name):
        if not isinstance(name,str) or not name or len(name)>240: raise ValueError('Invalid path')
        relative=Path(name)
        if relative.is_absolute() or any(p.startswith('.') for p in relative.parts): raise ValueError('Only relative paths inside the site are allowed')
        candidate=self.root/relative
        for p in [candidate,*candidate.parents]:
            if p==self.root: break
            if p.is_symlink(): raise ValueError('Symlinks are not allowed')
        if not candidate.resolve().is_relative_to(self.root): raise ValueError('Outside site')
        if candidate.suffix not in ALLOWED: raise ValueError('Allowed extensions: html css js json txt')
        return candidate
    def files(self):
        return sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix in ALLOWED and not any(x.startswith('.') for x in p.relative_to(self.root).parts))[:100]
    def read(self,name):
        p=self.path(name)
        if p.stat().st_size>24000: raise ValueError('File too large (24 KB maximum)')
        content=p.read_text(); self.read_versions[name]=content
        return content
    def write(self,name,content,previous):
        if not isinstance(content,str) or len(content.encode())>24000: raise ValueError('File too large')
        p=self.path(name)
        current=p.read_text() if p.exists() else None
        if current!=previous: raise ValueError('File changed; read it again before editing')
        if current is None and len(self.files())>=100: raise ValueError('Maximum file count reached')
        if current==content: return {'changed':False,'path':name}
        problems=validate(name,content)
        if problems: raise ValueError('Write rejected; file unchanged: '+ '; '.join(problems))
        # Persist recovery data before mutation.
        change={'path':name,'before':current,'after':content}
        self.changes.append(change)
        (self.run/'changes.json').write_text(json.dumps(self.changes,ensure_ascii=False,indent=2))
        p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content)
        self.read_versions[name]=content
        diff=''.join(difflib.unified_diff((current or '').splitlines(True),content.splitlines(True),fromfile=name,tofile=name))
        (self.run/f'change-{len(self.changes):02d}.diff').write_text(diff)
        return {'changed':True,'path':name,'diff':diff[:5000]}
    def check(self):
        errors=[]; pages=[]; external_resources=[]; sources={}; linked=set()
        for name in self.files():
            content=self.path(name).read_text()
            sources[name]=content
            errors.extend(f'{name}: {e}' for e in validate(name,content))
            if not name.endswith('.html'): continue
            p=self.path(name); parser=References(); parser.feed(p.read_text()); pages.append(name)
            if parser.titles!=1: errors.append(f'{name}: expected one title')
            if parser.h1!=1: errors.append(f'{name}: expected one h1')
            for ref in parser.refs:
                u=urlsplit(ref)
                if u.scheme or u.netloc:
                    external_resources.append({'page':name,'url':ref});continue
                if not u.path:continue
                target=(p.parent/unquote(u.path)).resolve()
                linked.add(target)
                if not target.is_relative_to(self.root): errors.append(f'{name}: link outside site: {ref}')
                elif not target.exists():
                    candidates=[f for f in self.files() if Path(f).name==Path(u.path).name]
                    suggestion=('; correct relative path: '+os.path.relpath(self.root/candidates[0],p.parent)) if len(candidates)==1 else ''
                    errors.append(f'{name}: broken local link: {ref}'+suggestion)
        warnings=[]
        for name in sources:
            if Path(name).suffix not in {'.js','.css'} or self.path(name) in linked: continue
            # Advisory only: modules and dynamically loaded assets may not have HTML links.
            if any(Path(name).name in content for other,content in sources.items() if other!=name): continue
            warnings.append(f'{name}: no reference found in other site files; check whether this asset should be connected to a page (heuristic, not a runtime test)')
        return {'pages':pages,'errors':errors,'warnings':warnings,'external_urls_not_checked':external_resources,'scope':'HTML tag nesting; JS syntax only (not runtime); local links, title, h1; unreferenced CSS/JS heuristic. No visual, CSS runtime, external URL or PHP checks.'}
    def call(self, action):
        tool=action.get('tool'); a=action.get('args',{})
        if tool=='list_files': return self.files()
        if tool=='read_file': return self.read(a['path'])
        if tool=='check_site': return self.check()
        if tool=='replace_text':
            name=a['path']; old=a['old']; new=a['new']
            if name not in self.read_versions: raise ValueError('Read the file before editing')
            content=self.read_versions[name]
            if not old or content.count(old)==0: raise ValueError('old was not found; read the file again')
            if content.count(old)>1 and len(new)>max(128,len(old)*8): raise ValueError('Unsafe broad replacement: use a unique full-line or block anchor, not a short repeated substring')
            if content.count(old)>1 and a.get('all') is not True: raise ValueError('old matches more than once; use a larger unique fragment or set all=true to replace every occurrence')
            return self.write(name,content.replace(old,new) if a.get('all') is True else content.replace(old,new,1),content)
        if tool=='write_file':
            name=a['path']; p=self.path(name)
            if p.exists(): raise ValueError('write_file creates new files only; read the existing file and use a targeted replace_text')
            return self.write(name,a['content'],self.read_versions.get(name))
        raise ValueError('Unknown tool')

def undo(run_dir, root=SITE):
    w=Workspace(run_dir,root); changes=json.loads((Path(run_dir)/'changes.json').read_text())
    expected={}; original={}
    for c in changes:
        original.setdefault(c['path'],c['before']); expected[c['path']]=c['after']
    for name,after in expected.items():
        p=w.path(name)
        if not p.exists() or p.read_text()!=after: raise ValueError(f'{name} changed since this run; undo cancelled')
    for name,before in original.items():
        p=w.path(name)
        if before is None: p.unlink()
        else: p.write_text(before)
    (Path(run_dir)/'undone.txt').write_text('Changes reverted.\n')
    return list(original)
