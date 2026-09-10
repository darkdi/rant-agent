"""Installation-specific browser ports; never reuse another installation's bridge."""
import fcntl
import json
import os
from pathlib import Path
import socket

BASE = Path(__file__).resolve().parents[1]


def available(http, websocket):
    sockets = []
    try:
        for port in (http, websocket):
            sock = socket.socket()
            sockets.append(sock)
            sock.bind(('127.0.0.1', port))
        return True
    except OSError:
        return False
    finally:
        for sock in sockets:
            sock.close()


def installation_ports():
    directory = BASE / '.local'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / 'browser-ports.json'
    with (directory / 'browser-ports.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            ports = json.loads(path.read_text())
        else:
            http = next((port for port in range(4313, 4514, 20) if available(port, port + 1)), None)
            if http is None:
                raise ValueError('Нет свободной пары портов для расширения Chrome.')
            ports = {'http': http, 'websocket': http + 1}
            path.write_text(json.dumps(ports))
            path.chmod(0o600)
        values = (ports.get('http'), ports.get('websocket'))
        if any(type(port) is not int or not 1024 <= port <= 65535 for port in values) or values[0] == values[1]:
            raise ValueError('Проверь .local/browser-ports.json: нужны два разных локальных порта.')
        return values


PORT, WS_PORT = installation_ports()
