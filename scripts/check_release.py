"""Inspect tracked source paths and likely credentials without printing secrets."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
forbidden = {'.local', '.venv', 'node_modules', 'projects', 'work', '.git'}
patterns = [rb'gh[pousr]_[A-Za-z0-9]{30,}', rb'sk-(?:proj-)?[A-Za-z0-9_-]{32,}', rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----', rb'/Users/[^/\s]+/(?:Documents|Desktop)/']
issues = []
for name in filter(None, paths):
    path = Path(name)
    if forbidden.intersection(path.parts) or path.name in {'PROJECT_CONTEXT.md', 'config.js', 'keys.json'} or path.suffix in {'.safetensors', '.gguf'} or (path.name.startswith('.env') and path.name != '.env.example'):
        issues.append((name, 'private or generated path'))
    raw = (ROOT / path).read_bytes()
    if len(raw) > 10 * 1024 * 1024: issues.append((name, 'unexpectedly large file'))
    if b'\0' not in raw and any(re.search(pattern, raw) for pattern in patterns):
        issues.append((name, 'potential credential or personal absolute path'))
for name, reason in issues: print(f'{name}: {reason}')
print(f'Inspected {len(list(filter(None, paths)))} tracked files; {len(issues)} issue(s).')
sys.exit(bool(issues))
