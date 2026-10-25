#!/usr/bin/env python3
"""One Pi-owned dining session with a phone viewer and explicit start control."""
import argparse
import json
import math
from pathlib import Path
import signal
import socket
import sys
import threading
import time
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))  # fork_sensor.py (pad detector, saved calibration) lives in Lab 4

from calibration import TableCalibrator  # noqa: E402
from fork_sensor import PadDetector, load_calibration, save_calibration  # noqa: E402

# How long a utensil may stay off its pad before the phone reminds the diner to put it back.
REMIND_AFTER_CORRECT = 2  # seconds after the correct-answer feedback time has ended
REMIND_AFTER_WRONG = 5    # seconds after a wrong answer
REMIND_AFTER_OTHER = 3    # seconds when a utensil was already up at the start

# An answer can be several utensils at once. While what is in the diner's hand could still grow
# into a correct answer (for example the fork alone, when the steak needs fork + knife), the Pi
# waits this long for the rest before judging.
ANSWER_SETTLE = 2.0


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


def parse_answers(accepted, enabled_ids, label):
    """`accepted` lists alternative correct answers. Each is a utensil ID (that utensil alone) or a
    list of IDs (those utensils picked up together). Returns a list of frozensets of IDs."""
    if not isinstance(accepted, list) or not accepted:
        raise ValueError(f'{label}: accepted must be a nonempty list.')
    answers = []
    for entry in accepted:
        ids = [entry] if isinstance(entry, str) else entry
        if (not isinstance(ids, list) or not ids or len(set(ids)) != len(ids)
                or any(not isinstance(x, str) or x not in enabled_ids for x in ids)):
            raise ValueError(f'{label}: each accepted entry must be an enabled utensil ID, or a list of '
                             'distinct enabled utensil IDs to pick up together.')
        answers.append(frozenset(ids))
    return answers


def join_names(names):
    return names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]


def judge(chosen, answers, waited):
    """Verdict for the utensils currently in hand: True (correct), False (wrong), or None (wait).

    Waits only while the diner could still add utensils to reach a correct answer, and
    never longer than ANSWER_SETTLE seconds since the set last changed.
    """
    could_grow = any(chosen < answer for answer in answers)
    if chosen in answers:
        return True if not could_grow or waited >= ANSWER_SETTLE else None
    if could_grow:
        return False if waited >= ANSWER_SETTLE else None
    return False


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
        course['answers'] = parse_answers(course['accepted'], enabled_ids, f'Course {i}')
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
        self.phase = 'calibrating'  # table setup comes before the welcome screen
        self.title = 'Welcome to the table'
        self.message = 'Setting the table.'
        self.sensor = 'starting'
        self.error = ''
        self.touched = []  # names of utensils currently picked up
        self.armed = False
        self.until = 0
        self.pending = None  # utensil IDs in hand while an answer is still being put together
        self.pending_since = 0
        self.reminder = ''  # shown on the phone while a utensil should be back on its pad
        self.remind_from = None
        self.setup = {'step': 'connecting', 'message': 'Connecting to the sensor…', 'items': []}
        self.setup_cmd = None

    def start(self):
        with self.lock:
            if self.sensor != 'connected' or self.phase == 'calibrating':
                return False
            if self.phase == 'waiting':
                self.phase = 'ready'
                self.message = 'Your dinner is served. Pick up the utensil or utensils you would use.'
                self.armed = False  # A utensil already lifted must be put back first.
            return True  # Repeated starts/joining phones never reset progress.

    def sensor_ready(self):
        with self.lock:
            self.sensor = 'connected'

    def show_setup(self, view):
        with self.lock:
            self.setup = view

    def finish_setup(self):
        with self.lock:
            self.phase = 'waiting'
            self.message = 'Your table is ready.'

    def request_setup(self, command):
        """A phone asked to measure the empty table, or to redo setup. Returns whether it applies now."""
        with self.lock:
            if command == 'measure' and self.phase == 'calibrating' and self.setup['step'] == 'clear':
                self.setup_cmd = 'measure'
                return True
            if command == 'restart' and self.phase in ('calibrating', 'waiting') and self.sensor == 'connected':
                self.phase = 'calibrating'
                self.setup = {'step': 'clear', 'message': 'Starting setup again…', 'items': self.setup['items']}
                self.setup_cmd = 'restart'
                return True
            return False

    def take_setup_cmd(self):
        with self.lock:
            command, self.setup_cmd = self.setup_cmd, None
            return command

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
                        sensor=self.sensor, error=self.error, touched=self.touched, setup=self.setup, reminder=self.reminder,
                        course_number=min(self.index + 1, len(self.courses)), total=len(self.courses),
                        dish=self.courses[self.index]['dish'] if self.index < len(self.courses) else 'Dinner is complete',
                        prompt=self.courses[self.index]['prompt'] if self.index < len(self.courses) else 'Thank you for joining us at the table.',
                        first_try=self.first_try, retries=sum(max(0, n - 1) for n in self.attempts))

    def remind(self, active, now):
        """Nudge the diner when a utensil is still off its pad although the table should be reset
        (after an answer, or when two were lifted at once). Caller holds the lock."""
        stuck = bool(active) and not self.armed  # armed again only once every utensil is back
        if not stuck:
            self.reminder, self.remind_from = '', None
            return
        if self.remind_from is None:
            self.remind_from = {'correct': self.until + REMIND_AFTER_CORRECT,
                                'wrong': now + REMIND_AFTER_WRONG}.get(self.phase, now + REMIND_AFTER_OTHER)
        if now < self.remind_from:
            self.reminder = ''
            return
        names = [self.mapping[ch]['name'].lower() for ch in sorted(active)]
        self.reminder = f"Please put the {join_names(names)} back on {'its pad' if len(names) == 1 else 'their pads'} and press down."

    def update(self, active, now):
        # Called only for a stable (debounced) sensor sample. `active` holds the channels
        # of utensils that are currently picked up (off their pads).
        with self.lock:
            self.sensor = 'connected'
            self.touched = [self.mapping[ch]['name'] for ch in sorted(active)]
            if self.phase in ('calibrating', 'waiting', 'complete'):
                self.reminder, self.remind_from = '', None
                return
            self.remind(active, now)
            if self.phase == 'correct':
                if now < self.until or active:
                    return
                self.index += 1
                if self.index == len(self.courses):
                    self.phase, self.title = 'complete', 'A lovely finish'
                    self.message = 'Restart the app on the Pi to begin a new dinner.'
                    self.cue(self.sounds.get('end'))
                    return
                self.phase, self.title, self.message = 'ready', 'Next course', 'Pick up the utensil or utensils you would use.'
                self.cue(self.courses[self.index].get('sound'))
                self.armed = True
                return
            if not active:
                self.armed = True
                self.pending = None
                if self.title == 'Welcome to the table':
                    self.message = 'Pick up the utensil or utensils you would use.'
                return
            if not self.armed:
                return
            # The answer is whatever is in the diner's hand. It is judged straight away unless it
            # could still grow into a correct answer, in which case judge() waits up to ANSWER_SETTLE.
            chosen = frozenset(self.mapping[ch]['id'] for ch in active)
            if chosen != self.pending:
                self.pending, self.pending_since = chosen, now
            course = self.courses[self.index]
            verdict = judge(chosen, course['answers'], now - self.pending_since)
            if verdict is None:
                return  # could still become a correct answer: wait for the rest
            self.armed, self.pending = False, None
            names = join_names([self.mapping[ch]['name'] for ch in sorted(active)])
            self.attempts[self.index] += 1
            if verdict:
                self.phase, self.title = 'correct', f"Correct — {names}"
                self.message = course['explanation'] + ' Put your utensils back to continue.'
                self.first_try += self.attempts[self.index] == 1
                self.until = now + self.duration
                self.cue(self.sounds.get('correct'))
            else:
                self.phase, self.title = 'wrong', f"Try again — you chose {names}"
                self.message = course['hint'] + ' Put your utensils back, then choose again.'
                self.cue(self.sounds.get('incorrect'))


class SensorRunner:
    """Table setup first, then play. `read(channel)` returns an MPR121 filtered value,
    so this runs without hardware.

    Each utensil rests on its copper pad. Setup learns the empty-pad reading and each
    utensil's thresholds; during play a utensil counts as selected while it is lifted off
    its pad (the same pick-up / put-down detection as fork_sensor.py).
    """

    def __init__(self, session, read):
        self.session, self.read = session, read
        self.items = [(item['id'], item['name'], ch) for ch, item in session.mapping.items()]
        self.names = {ch: name for _, name, ch in self.items}
        self.calibrator = TableCalibrator([(uid, name) for uid, name, _ in self.items])
        self.detectors = {}  # channel -> PadDetector; empty while setup is running
        self.candidate, self.changed = frozenset(), 0
        session.show_setup(self.calibrator.view())
        session.sensor_ready()

    def tick(self, now, debounce):
        command = self.session.take_setup_cmd()
        if command == 'restart':
            self.calibrator.reset()
            self.detectors = {}
        if not self.detectors:
            self._setup_tick(command, now)
        else:
            self._play_tick(now, debounce)

    def _setup_tick(self, command, now):
        calibrator = self.calibrator
        if command == 'measure':
            calibrator.start_measuring(now)
        if calibrator.step in ('measuring', 'placing'):
            calibrator.feed({uid: self.read(ch) for uid, _, ch in self.items}, now)
        if calibrator.step == 'done':
            self._finish_setup(now)
        else:
            self.session.show_setup(calibrator.view())

    def _finish_setup(self, now):
        saved = load_calibration()
        for uid, _, ch in self.items:
            on, off = self.calibrator.results[uid]
            detector = PadDetector(self.calibrator.references[uid], on, off)
            detector.present = True  # setup ends with every utensil resting on its pad
            self.detectors[ch] = detector
            saved[uid] = {'on': on, 'off': off}
        try:
            save_calibration(saved)  # shared with fork_sensor.py and utensil_quiz.py
        except OSError as exc:
            print(f'Could not save calibration: {exc}', flush=True)
        self.candidate, self.changed = frozenset(), now
        self.session.finish_setup()

    def _play_tick(self, now, debounce):
        lifted = set()
        for ch, detector in self.detectors.items():
            reading = self.read(ch)
            if detector.update(reading) is not None:
                # One line per lift / put-back, so a misread shows up in the terminal.
                print(f"{self.names[ch]}: {'back on its pad' if detector.present else 'lifted'} "
                      f"(drop {detector.delta(reading):.0f}; on > {detector.on:.0f}, off < {detector.off:.0f})", flush=True)
            if not detector.present:
                lifted.add(ch)
        active = frozenset(lifted)
        if active != self.candidate:
            self.candidate, self.changed = active, now
        if now - self.changed >= debounce:
            self.session.update(active, now)


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
        if mapping_mode:
            candidate, changed = None, time.monotonic()
            reported = None
            while not stop.is_set():
                active = frozenset(i for i in range(12) if sensor[i].value)
                now = time.monotonic()
                if active != candidate:
                    candidate, changed = active, now
                if now - changed >= debounce and active != reported:
                    print('Touched channels: ' + (', '.join(map(str, sorted(active))) or 'none'), flush=True)
                    reported = active
                stop.wait(0.02)
        else:
            runner = SensorRunner(session, sensor.filtered_data)
            failures = 0
            while not stop.is_set():
                try:
                    runner.tick(time.monotonic(), debounce)
                    failures = 0
                except OSError:
                    failures += 1  # tolerate a dropped I2C read, but not a dead sensor
                    if failures > 50:
                        raise
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
            if self.path == '/api/start':
                ok = session.start()
                body = json.dumps({'started': ok}).encode()
            elif self.path in ('/api/setup/measure', '/api/setup/restart'):
                ok = session.request_setup(self.path.rsplit('/', 1)[1])
                body = json.dumps({'accepted': ok}).encode()
            else:
                self.send_error(404)
                return
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
