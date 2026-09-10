"""Install the base dependencies, build when needed, and run the loopback app."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'sever-ide'


def run(args, cwd=ROOT):
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def fingerprint(paths):
    digest = hashlib.sha256()
    for path in sorted(paths):
        if path.is_file():
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def port_free(port):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


def main():
    parser = argparse.ArgumentParser(description='Rant Agent local launcher (macOS / Linux).')
    parser.add_argument('--port', type=int, default=int(os.environ.get('RANT_PORT', '4311')))
    parser.add_argument('--preview-port', type=int, default=int(os.environ.get('RANT_PREVIEW_PORT', '4312')))
    parser.add_argument('--no-open', action='store_true', help='Do not open a browser window.')
    parser.add_argument('--no-browser', action='store_true', help='Run without the Chrome extension bridge.')
    parser.add_argument('--rebuild', action='store_true', help='Force a frontend rebuild.')
    parser.add_argument('--check', action='store_true', help='Check prerequisites without installing or starting.')
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.exit(1, 'Python 3.12+ is required. See docs/INSTALL_RU.md.\n')
    if sys.platform not in {'darwin', 'linux'}:
        parser.exit(1, 'This alpha supports macOS and Linux. Native Windows is not supported.\n')
    node, npm = shutil.which('node'), shutil.which('npm')
    if not node or not npm:
        parser.exit(1, 'Install Node.js 22.13+ (including npm) from https://nodejs.org/\n')
    version = subprocess.check_output([node, '-p', 'process.versions.node'], text=True).strip()
    if tuple(map(int, version.split('.')[:2])) < (22, 13):
        parser.exit(1, 'Node.js 22.13+ is required.\n')
    if any(not 1024 <= port <= 65535 for port in (args.port, args.preview_port)) or args.port == args.preview_port:
        parser.exit(1, 'Choose two different ports between 1024 and 65535.\n')
    print(f'Python {sys.version.split()[0]} · Node {version}', flush=True)
    for port in (args.port, args.preview_port):
        if not port_free(port):
            parser.exit(1, f'Port {port} is in use. Try ./start.sh --port 4321 --preview-port 4322\n')
    if args.check:
        print('Prerequisites and application ports are ready. Model runtimes are optional.')
        return
    python = ROOT / '.venv/bin/python'
    if not python.exists():
        print('Creating the Python environment…', flush=True)
        run([sys.executable, '-m', 'venv', ROOT / '.venv'])
    local = APP / '.local'
    local.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = local / 'setup.json'
    try:
        saved = json.loads(stamp.read_text())
    except (OSError, ValueError):
        saved = {}
    python_hash = fingerprint([ROOT / 'requirements.txt', ROOT / '.venv/pyvenv.cfg'])
    if saved.get('python') != python_hash:
        print('Installing base Python dependencies (no model downloads)…', flush=True)
        run([python, '-m', 'pip', 'install', '-r', ROOT / 'requirements.txt'])
    npm_hash = fingerprint([APP / 'package.json', APP / 'package-lock.json'])
    if saved.get('npm') != npm_hash or not (APP / 'node_modules/.bin/vinext').exists():
        print('Installing frontend dependencies…', flush=True)
        run([npm, 'ci'], APP)
    source = [APP / name for name in ['package.json', 'package-lock.json', 'vite.config.ts', 'tsconfig.json']]
    for directory in ['app', 'components', 'hooks', 'lib', 'public', 'scripts']:
        source.extend((APP / directory).rglob('*'))
    source.extend((ROOT / 'docs').rglob('*.md'))
    build_hash = fingerprint(source)
    if args.rebuild or saved.get('build') != build_hash or not (APP / 'dist/client/index.html').exists():
        print('Building the interface…', flush=True)
        run([npm, 'run', 'build'], APP)
    stamp.write_text(json.dumps({'python': python_hash, 'npm': npm_hash, 'build': build_hash}))
    env = {**os.environ, 'RANT_PREVIEW_PORT': str(args.preview_port)}
    command = [str(python), '-u', str(APP / 'backend/server.py'), '--port', str(args.port)]
    if not args.no_open:
        command.append('--open')
    if args.no_browser:
        command.append('--no-browser')
    print(f'Opening http://127.0.0.1:{args.port} — press Ctrl+C here to stop.', flush=True)
    os.chdir(APP)
    os.execve(python, command, env)


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.CalledProcessError) as error:
        print(f'Startup failed: {error}. See docs/INSTALL_RU.md.', file=sys.stderr)
        sys.exit(1)
