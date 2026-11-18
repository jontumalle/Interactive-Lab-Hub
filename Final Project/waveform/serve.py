#!/usr/bin/env python3
"""Local browser simulator using the same core and 240x135 renderer as the Pi."""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import threading
import time

from puzzle import ReceiverPuzzle
from display import render

WEB = Path(__file__).with_name('web')
ARROWS = {'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'}


class Session:
    def __init__(self):
        self.puzzle = ReceiverPuzzle()
        self.lock = threading.Lock()
        self.keys = set()
        self.input_time = 0.0
        self.sequence = -1
        self.running = True

    def tick(self):
        last = time.monotonic()
        while self.running:
            now = time.monotonic()
            with self.lock:
                keys = self.keys if now - self.input_time < .4 else set()
                x = int('ArrowRight' in keys) - int('ArrowLeft' in keys)
                y = int('ArrowUp' in keys) - int('ArrowDown' in keys)
                self.puzzle.update(now - last, x=x, y=y)
            last = now
            time.sleep(1 / 30)

    def state(self):
        with self.lock:
            snapshot = self.puzzle.snapshot()
        picture = BytesIO()
        render(snapshot).save(picture, format='PNG')
        snapshot.pop('target_frequency', None)
        snapshot.pop('target_amplitude', None)
        return {'state': snapshot, 'frame': base64.b64encode(picture.getvalue()).decode('ascii')}


def handler_for(session):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, content, mime='application/json'):
            if isinstance(content, (dict, list)):
                content = json.dumps(content).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            path = self.path.split('?', 1)[0]
            if path == '/api/frame':
                self.reply(200, session.state())
            elif path in ('/', '/index.html', '/app.js', '/style.css'):
                name = 'index.html' if path == '/' else path[1:]
                mime = {'html': 'text/html; charset=utf-8', 'js': 'text/javascript; charset=utf-8', 'css': 'text/css; charset=utf-8'}[name.rsplit('.', 1)[1]]
                self.reply(200, (WEB / name).read_bytes(), mime)
            else:
                self.reply(404, {'error': 'Not found'})

        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 2048:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected an object')
                with session.lock:
                    if self.path == '/api/input':
                        keys, seq = data.get('keys'), data.get('sequence')
                        if not isinstance(keys, list) or len(keys) > 4 or not all(isinstance(k, str) and k in ARROWS for k in keys) or type(seq) is not int:
                            raise ValueError('Invalid controls')
                        if seq > session.sequence:
                            session.keys = set(keys)
                            session.sequence = seq
                            session.input_time = time.monotonic()
                    elif self.path == '/api/reset':
                        session.keys.clear()
                        session.puzzle.reset()
                    else:
                        self.reply(404, {'error': 'Not found'})
                        return
                self.reply(200, {'ok': True})
            except (ValueError, TypeError, json.JSONDecodeError):
                self.reply(400, {'error': 'Invalid request'})

        def log_message(self, fmt, *args):
            if not args or str(args[1] if len(args) > 1 else '') not in ('200', '304'):
                super().log_message(fmt, *args)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    session = Session()
    server = ThreadingHTTPServer((args.host, args.port), handler_for(session))
    threading.Thread(target=session.tick, daemon=True).start()
    print(f'Waveform simulator: http://{args.host}:{args.port}', flush=True)
    print('Arrow keys adjust; release to acquire. Ctrl+C stops.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        session.running = False
        server.server_close()


if __name__ == '__main__':
    main()
