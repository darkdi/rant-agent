"""Parse-only validation. Never execute website scripts."""
import shutil
import subprocess
from html.parser import HTMLParser

VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.errors=[];self.scripts=[];self.script=None;self.html_count=0
    def handle_starttag(self,tag,attrs):
        if tag=='html': self.html_count+=1
        if tag not in VOID:self.stack.append(tag)
        if tag=='script':
            a=dict(attrs);kind=a.get('type','').lower()
            self.script=[] if not a.get('src') and kind in ('','module','text/javascript','application/javascript') else None
    def handle_startendtag(self,tag,attrs):
        if tag not in VOID:self.errors.append(f'Use explicit closing tag for <{tag}>')
    def handle_endtag(self,tag):
        if tag=='script':
            if self.script is not None:self.scripts.append(''.join(self.script))
            self.script=None
        if tag in VOID:self.errors.append(f'Unexpected </{tag}>');return
        if not self.stack or self.stack[-1]!=tag:
            self.errors.append(f'Unexpected </{tag}>; check tag nesting')
            if tag in self.stack:self.stack=self.stack[:self.stack.index(tag)]
        else:self.stack.pop()
    def handle_data(self,data):
        if self.script is not None:self.script.append(data)

def js_errors(code):
    node=shutil.which('node')
    if not node:return ['JavaScript validation unavailable: node is missing']
    try:
        r=subprocess.run([node,'--check','--input-type=module'],input=code,text=True,capture_output=True,timeout=8)
    except subprocess.TimeoutExpired:return ['JavaScript syntax check timed out']
    if r.returncode:
        return ['JavaScript syntax error: '+r.stderr[:1000]]
    return []

def validate(name,content):
    if name.endswith('.js'):return js_errors(content)
    if not name.endswith('.html'):return []
    p=Document()
    try:p.feed(content);p.close()
    except Exception as e:return ['HTML parse error: '+str(e)]
    if p.html_count!=1:p.errors.append('Expected one complete HTML document')
    if p.stack:p.errors.append('Unclosed tags: '+', '.join(p.stack))
    for script in p.scripts:p.errors.extend(js_errors(script))
    return p.errors[:8]
