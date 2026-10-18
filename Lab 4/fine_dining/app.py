#!/usr/bin/env python3
"""One Pi-owned dining session with a phone viewer and explicit start control."""
import argparse
import json
import math
from pathlib import Path
import signal
import socket
import threading
import time
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent


def image_path(name):
    if not isinstance(name, str) or Path(name).name != name or Path(name).suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
        raise ValueError('image must be a JPG, PNG, or WebP filename inside static/images.')
    path = (ROOT / 'static/images' / name).resolve()
    if not path.is_relative_to((ROOT / 'static/images').resolve()) or not path.is_file():
        raise ValueError(f'Image file not found: {name}')
    return path


def sound_path(name):
    if not isinstance(name, str) or Path(name).name != name or Path(name).suffix.lower() != '.wav':
        raise ValueError('Sound must be a WAV filename inside static/sounds.')
    path = (ROOT / 'static/sounds' / name).resolve()
    if not path.is_relative_to((ROOT / 'static/sounds').resolve()) or not path.is_file():
        raise ValueError(f'Sound file not found: {name}')
    return path


def sound_duration(name):
    if not name:
        return 0
    try:
        with wave.open(str(sound_path(name))) as clip:
            return clip.getnframes() / clip.getframerate()
    except (wave.Error, EOFError, ZeroDivisionError) as exc:
        raise ValueError(f'Invalid WAV file: {name}') from exc


def number(value, label, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be a number from {minimum} to {maximum}.")
    return value


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text.")
    return value


def load_config():
    mapping = json.loads((ROOT / 'cutlery.json').read_text(encoding='utf-8'))
    scenarios = json.loads((ROOT / 'scenarios.json').read_text(encoding='utf-8'))
    debounce = number(mapping.get('debounce_ms', 100), 'debounce_ms', 20, 2000) / 1000
    duration = number(scenarios.get('feedback_seconds', 4), 'feedback_seconds', 1, 60)
    sounds = scenarios.get('sounds', {})
    if not isinstance(sounds, dict):
        raise ValueError('sounds must be an object mapping events to WAV filenames.')
    for event, filename in sounds.items():
        if event not in ('welcome', 'correct', 'incorrect', 'end'):
            raise ValueError(f'Unknown sound event: {event}')
        sound_duration(filename)
    duration = max(duration, sound_duration(sounds.get('correct')) + 1)
    items = mapping['cutlery']
    if not isinstance(items, list) or not items:
        raise ValueError('cutlery must be a nonempty list.')
    ids, channels, enabled = set(), set(), {}
    for item in items:
        uid = nonempty(item['id'], 'Utensil id')
        nonempty(item['name'], f'{uid} name')
        channel = item['channel']
        if type(channel) is not int or channel not in range(12):
            raise ValueError(f'{uid}: channel must be an integer from 0 to 11.')
        if uid in ids or channel in channels:
            raise ValueError(f'{uid}: utensil IDs and channels must be unique.')
        if type(item.get('enabled', True)) is not bool:
            raise ValueError(f'{uid}: enabled must be true or false.')
        ids.add(uid)
        channels.add(channel)
        if item.get('enabled', True):
            enabled[channel] = item
    if not enabled:
        raise ValueError('Enable at least one utensil.')
    courses = scenarios['courses']
    if not isinstance(courses, list) or not courses:
        raise ValueError('courses must be a nonempty list.')
    enabled_ids = {item['id'] for item in enabled.values()}
    for i, course in enumerate(courses, 1):
        for field in ('course_label', 'subtitle', 'description', 'image_alt', 'image_credit', 'image_source', 'image_license', 'image_license_url'):
            if field in course:
                nonempty(course[field], f'Course {i} {field}')
        if course.get('image'):
            image_path(course['image'])
            nonempty(course.get('image_alt'), f'Course {i} image_alt')
        if course.get('image_source') and not course['image_source'].startswith('https://'):
            raise ValueError(f'Course {i}: image_source must be an HTTPS URL.')
        if course.get('image_license_url') and not course['image_license_url'].startswith('https://'):
            raise ValueError(f'Course {i}: image_license_url must be an HTTPS URL.')
        for field in ('dish', 'prompt', 'hint', 'explanation'):
            nonempty(course[field], f'Course {i} {field}')
        if course.get('sound_optional'):
            # Missing optional recording is allowed; malformed paths/files are not.
            name = course['sound_optional']
            if not isinstance(name, str) or Path(name).name != name or Path(name).suffix.lower() != '.wav':
                raise ValueError('sound_optional must be a WAV filename.')
            if (ROOT / 'static/sounds' / name).exists():
                course['sound'] = name
        sound_duration(course.get('sound'))
        accepted = course['accepted']
        if not isinstance(accepted, list) or not accepted or any(not isinstance(x, str) or x not in enabled_ids for x in accepted):
            raise ValueError(f'Course {i}: accepted must list enabled utensil IDs.')
    return enabled, courses, debounce, duration, sounds


class Session:
    def __init__(self, mapping, courses, duration, sounds):
        self.mapping, self.courses, self.duration = mapping, courses, duration
        self.sounds = sounds
        self.session_id = uuid.uuid4().hex
        self.audio_id = 0
        self.audio_clips = [x for x in (sounds.get('welcome'), courses[0].get('sound')) if x]
        self.lock = threading.Lock()
        self.index = 0
        self.attempts = [0] * len(courses)
        self.first_try = 0
        self.phase = 'waiting'
        self.title = 'Welcome to the table'
        self.message = 'Keep your hands off the utensils while the sensor starts.'
        self.sensor = 'starting'
        self.error = ''
        self.touched = []
        self.armed = False
        self.until = 0

    def start(self):
        with self.lock:
            if self.sensor != 'connected':
                return False
            if self.phase == 'waiting':
                self.phase = 'ready'
                self.message = 'Your dinner is served. Touch one utensil to answer.'
                self.armed = False  # A held utensil must be released first.
            return True  # Repeated starts/joining phones never reset progress.

    def cue(self, *clips):
        self.audio_id += 1
        self.audio_clips = [clip for clip in clips if clip]

    def snapshot(self):
        with self.lock:
            course = self.courses[self.index] if self.index < len(self.courses) else {}
            return dict(audio={'id': f'{self.session_id}:{self.audio_id}', 'clips': self.audio_clips}, phase=self.phase, title=self.title, message=self.message,
                        presentation={key: course.get(key, '') for key in ('course_label', 'subtitle', 'description', 'image', 'image_alt', 'image_credit', 'image_source', 'image_license', 'image_license_url')},
                        menu=[{'dish': c['dish'], 'label': c.get('course_label', f'Course {i + 1}'),
                               'status': 'served' if i < self.index else 'current' if i == self.index else 'upcoming'}
                              for i, c in enumerate(self.courses)],
                        sensor=self.sensor, error=self.error, touched=self.touched,
                        course_number=min(self.index + 1, len(self.courses)), total=len(self.courses),
                        dish=self.courses[self.index]['dish'] if self.index < len(self.courses) else 'Dinner is complete',
                        prompt=self.courses[self.index]['prompt'] if self.index < len(self.courses) else 'Thank you for joining us at the table.',
                        first_try=self.first_try, retries=sum(max(0, n - 1) for n in self.attempts))

    def update(self, active, now):
        # Called only for a stable (debounced) sensor sample.
        with self.lock:
            self.sensor = 'connected'
            self.touched = [self.mapping[ch]['name'] for ch in sorted(active)]
            if self.phase in ('waiting', 'complete'):
                return
            if self.phase == 'correct':
                if now < self.until or active:
                    return
                self.index += 1
                if self.index == len(self.courses):
                    self.phase, self.title = 'complete', 'A lovely finish'
                    self.message = 'Restart the app on the Pi to begin a new dinner.'
                    self.cue(self.sounds.get('end'))
                    return
                self.phase, self.title, self.message = 'ready', 'Next course', 'Touch one utensil to answer.'
                self.cue(self.courses[self.index].get('sound'))
                self.armed = True
                return
            if not active:
                self.armed = True
                if self.title == 'Welcome to the table':
                    self.message = 'Touch one utensil to answer.'
                return
            if not self.armed:
                return
            self.armed = False
            if len(active) != 1:
                # Ambiguous touches are ignored without feedback or a penalty.
                return
            item = self.mapping[next(iter(active))]
            course = self.courses[self.index]
            self.attempts[self.index] += 1
            if item['id'] in course['accepted']:
                self.phase, self.title = 'correct', f"Correct — {item['name']}"
                self.message = course['explanation'] + ' Release the utensils to continue.'
                self.first_try += self.attempts[self.index] == 1
                self.until = now + self.duration
                self.cue(self.sounds.get('correct'))
            else:
                self.phase, self.title = 'wrong', f"Try again — you chose {item['name']}"
                self.message = course['hint'] + ' Release the utensils, then choose again.'
                self.cue(self.sounds.get('incorrect'))


def sensor_loop(session, debounce, stop, mapping_mode):
    i2c = None
    try:
        # Same hardware driver as cap_test.py. Imports stay here so --check-config
        # can run on a computer without the board or CircuitPython installed.
        import board
        import busio
        import adafruit_mpr121
        i2c = busio.I2C(board.SCL, board.SDA)
        sensor = adafruit_mpr121.MPR121(i2c)
        candidate, changed = None, time.monotonic()
        reported = None
        while not stop.is_set():
            raw = frozenset(i for i in range(12) if sensor[i].value)
            active = raw if mapping_mode else raw.intersection(session.mapping)
            now = time.monotonic()
            if active != candidate:
                candidate, changed = active, now
            if now - changed >= debounce:
                if mapping_mode:
                    if active != reported:
                        print('Touched channels: ' + (', '.join(map(str, sorted(active))) or 'none'), flush=True)
                        reported = active
                else:
                    session.update(active, now)
            stop.wait(0.02)
    except Exception as exc:
        message = f'{type(exc).__name__}: {exc}'
        print(f'Sensor unavailable: {message}\nCheck wiring and the Lab 4 Python environment, then restart.', flush=True)
        if mapping_mode:
            stop.set()
        else:
            with session.lock:
                session.sensor, session.error = 'error', message
    finally:
        if i2c is not None:
            i2c.deinit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map', action='store_true', help='Print touched channels without running the website')
    parser.add_argument('--check-config', action='store_true', help='Validate configuration without accessing hardware')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    try:
        mapping, courses, debounce, duration, sounds = load_config()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Configuration error: {exc}\nCheck cutlery.json and scenarios.json.\n')
    if args.check_config:
        print(f'Configuration OK: {len(mapping)} enabled utensils, {len(courses)} courses.')
        return
    session, stop = Session(mapping, courses, duration, sounds), threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != '/api/start':
                self.send_error(404)
                return
            ok = session.start()
            body = json.dumps({'started': ok}).encode()
            self.send_response(200 if ok else 503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = self.path.split('?', 1)[0]
            if route == '/api/state':
                body = json.dumps(session.snapshot()).encode()
                content_type = 'application/json'
            elif route == '/':
                body = (ROOT / 'static/index.html').read_bytes()
                content_type = 'text/html; charset=utf-8'
            elif route.startswith('/sounds/'):
                try:
                    body = sound_path(unquote(route.removeprefix('/sounds/'))).read_bytes()
                    content_type = 'audio/wav'
                except (ValueError, OSError):
                    self.send_error(404)
                    return
            elif route.startswith('/images/'):
                try:
                    path = image_path(unquote(route.removeprefix('/images/')))
                    body = path.read_bytes()
                    content_type = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}[path.suffix.lower()]
                except (ValueError, OSError):
                    self.send_error(404)
                    return
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    server = None
    if not args.map:
        try:
            server = ThreadingHTTPServer(('0.0.0.0', args.port), Handler)
            server.timeout = 0.3
        except OSError as exc:
            parser.exit(1, f'Could not start web server: {exc}\nTry --port 8001 or stop the other server.\n')
        print(f'Phone viewer: http://{socket.gethostname()}.local:{args.port}', flush=True)
        print(f'Or use http://<Pi IP>:{args.port} (find the IP with hostname -I).', flush=True)
    print('Keep hands off utensils during startup. Stop with Ctrl+C.', flush=True)
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    worker = threading.Thread(target=sensor_loop, args=(session, debounce, stop, args.map), daemon=True)
    worker.start()
    try:
        while not stop.is_set():
            if server:
                server.handle_request()
            else:
                stop.wait(0.3)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        worker.join(timeout=3)
        if server:
            server.server_close()
        print('\nDining session stopped.', flush=True)


if __name__ == '__main__':
    main()
