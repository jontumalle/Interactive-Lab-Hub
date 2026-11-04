#!/usr/bin/env python3
"""Run on each Pi: python play.py [--terminal] [--room CODE] [--host]."""
import argparse
import heapq
import json
import os
from pathlib import Path
import queue
import random
import time
import uuid

from game import Game, DIRECTIONS, REVEAL_SECONDS, KNOCKOUT_DELAY
from hardware import Hardware


def main():
    import paho.mqtt.client as mqtt
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terminal', action='store_true')
    parser.add_argument('--host', action='store_true')
    parser.add_argument('--simulate', action='store_true',
                        help='host a practice game with three local random players')
    parser.add_argument('--room', help='four-digit room code')
    parser.add_argument('--broker', default=os.getenv('LOOK_AWAY_BROKER', 'farlab.infosci.cornell.edu'))
    parser.add_argument('--port', type=int, default=1883)
    parser.add_argument('--mute', action='store_true')
    parser.add_argument('--calibrate', action='store_true', help='learn physical right/up directions and exit')
    parser.add_argument('--audio-test', action='store_true', help='play every sound and exit (no MQTT needed)')
    parser.add_argument('--audio-device', help='SDL output device name; audio test lists available names')
    args = parser.parse_args()
    if args.simulate:
        args.host = True
        args.room = args.room or str(random.randint(1000, 9999))
    sounds = {}
    if not args.mute and not args.calibrate:
        import pygame
        pygame.mixer.init(devicename=args.audio_device)
        print('Audio driver:', pygame.mixer.get_init(), 'SDL:', os.getenv('SDL_AUDIODRIVER', 'default'))
        sounds = {name: pygame.mixer.Sound(str(Path(__file__).parent / 'assets' / (name + '.wav')))
                  for name in ('tick', 'reveal', 'elimination', 'victory')}
    if args.audio_test:
        if args.mute:
            parser.error('--audio-test cannot be combined with --mute')
        from pygame._sdl2.audio import get_audio_device_names
        print('Output devices:', get_audio_device_names(False))
        for name, sound in sounds.items():
            print('Playing:', name, flush=True)
            sound.play()
            time.sleep(sound.get_length() + .4)
        return
    hw = Hardware(args.terminal)
    if args.calibrate:
        hw.calibrate()
        return
    player = uuid.uuid4().hex[:8]
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='lookaway-' + player)
    client.username_pw_set(os.getenv('LOOK_AWAY_USER', 'idd'), os.getenv('LOOK_AWAY_PASSWORD', 'device@theFarm'))
    inbox = queue.Queue()
    client.on_message = lambda c, u, m: inbox.put((m.topic, m.payload))
    connected = False

    def connection(c, u, flags, reason, properties):
        nonlocal connected
        connected = reason == 0
        if connected:
            c.subscribe('IDD/look-away/' + room + '/#', qos=1)
    client.on_connect = connection
    client.on_disconnect = lambda *a: inbox.put(('', b'{}'))
    mode = 0
    digits = [0, 0, 0, 0]
    cursor = 0
    room = args.room
    host = args.host
    if room and (len(room) != 4 or not room.isdigit()):
        parser.error('--room must be four digits')
    while not room:
        hw.show(['LOOK AWAY', ('> Host' if mode == 0 else '  Host'),
                 ('> Join' if mode == 1 else '  Join'), 'Joystick + click'])
        event = hw.input()
        if event == 'quit':
            return
        if event == 'up':
            mode = 0
        elif event == 'down':
            mode = 1
        if event == 'press':
            host = mode == 0
            if host:
                room = str(random.randint(1000, 9999))
            else:
                while room is None:
                    hw.show(['JOIN ROOM', ''.join(map(str, digits)), ' ' * cursor + '^', 'Up/down: digit', 'Right/left: move', 'Click: join'], monospace=True)
                    e = hw.input()
                    if e == 'quit':
                        return
                    if e in ('up', 'down'):
                        digits[cursor] = (digits[cursor] + (1 if e == 'up' else -1)) % 10
                    if e in ('left', 'right'):
                        cursor = (cursor + (1 if e == 'right' else -1)) % 4
                    if e == 'press':
                        room = ''.join(map(str, digits))
                    time.sleep(.02)
        time.sleep(.02)
    base = 'IDD/look-away/' + room + '/'

    def send(kind, data):
        client.publish(base + kind, json.dumps(data), qos=1, retain=False)

    session = uuid.uuid4().hex if host else None
    game = Game(player) if host else None
    bots = None
    if args.simulate:
        from bots import Bots
        bots = Bots(game)
    state = None
    seen = {player: time.monotonic()}
    host_seen = time.monotonic()
    last_publish = last_hello = 0
    offset = 0
    selected = None
    revision = None
    submitted = False
    paused = False
    scheduled = []
    scheduled_keys = set()
    pending = {}
    error = ''
    client.connect(args.broker, args.port, keepalive=5)
    client.loop_start()
    try:
        while True:
            now = time.monotonic()
            event = hw.input()
            if event == 'quit':
                break
            if now - last_hello > 1:
                nonce = uuid.uuid4().hex
                pending = {nonce: now}
                send('hello', {'player': player, 'nonce': nonce})
                last_hello = now
            while not inbox.empty():
                topic, raw = inbox.get()
                if not topic:
                    connected = False
                    continue
                try:
                    data = json.loads(raw)
                    kind = topic.rsplit('/', 1)[-1]
                    if not isinstance(data, dict):
                        continue
                    if host and kind == 'hello' and isinstance(data.get('player'), str):
                        other = data['player']
                        if game.join(other):
                            seen[other] = now
                            send('pong', {'player': other, 'nonce': data.get('nonce'), 'time': now, 'session': session})
                        else:
                            send('reject', {'player': other, 'message': 'Room full or in progress'})
                    elif kind == 'pong' and data.get('player') == player and data.get('nonce') in pending:
                        offset = data['time'] - (now + pending.pop(data['nonce'])) / 2
                    elif kind == 'state' and not host:
                        if session is not None and data['session'] != session:
                            error = 'Host restarted; restart to join'
                            continue
                        session = data['session']
                        state = data['state']
                        paused = data['paused']
                        host_seen = now
                    elif kind == 'reject' and data.get('player') == player:
                        error = data['message']
                    elif host and kind == 'choice' and data.get('session') == session:
                        game.choose(data.get('player'), data.get('direction'), data.get('revision'))
                except (ValueError, TypeError, KeyError):
                    continue
            if host:
                seen[player] = now
                if bots:
                    for bot in bots.players:
                        seen[bot] = now
                missing = [p for p in game.players if now - seen.get(p, 0) > 4]
                new_pause = bool(missing) or not connected
                if paused and not new_pause and game.phase in ('choosing', 'waiting', 'reveal'):
                    # Replay interrupted round so stale choices/timers cannot affect the result.
                    if game.phase == 'reveal':
                        game.alive += game.eliminated
                    game.round -= 1
                    game.next_round(now)
                paused = new_pause
                if event == 'press' and not paused:
                    if game.phase == 'lobby' and bots is None:
                        from bots import Bots
                        bots = Bots(game)
                    game.start(now)
                if not paused:
                    if bots:
                        bots.tick(game, now)
                    game.tick(now)
                state = game.snapshot()
                if now - last_publish > .1:
                    send('state', {'session': session, 'state': state, 'paused': paused})
                    last_publish = now
            if not host and now - host_seen > 6:
                error = 'Host unavailable. Restart to join.'
                scheduled.clear()
            if error:
                hw.show(['LOOK AWAY', error, 'Ctrl-C to exit'])
                time.sleep(.03)
                continue
            if not state or player not in state['players']:
                hw.show(['Room ' + room, 'Connecting / joining...'])
                time.sleep(.03)
                continue
            if revision != state['revision']:
                revision = state['revision']
                selected = None
                submitted = False
                scheduled.clear()
                scheduled_keys.clear()
            clock = now if host else now + offset
            phase = state['phase']
            active = player == state['solo'] or player in state['alive']
            if paused:
                scheduled.clear()
                hw.show(['Room ' + room, 'PAUSED', 'Waiting for reconnect'])
                time.sleep(.03)
                continue
            if phase in ('choosing', 'waiting'):
                if event in DIRECTIONS and not submitted and active:
                    selected = event
                if clock >= state['deadline'] and selected and active and player not in state['submitted']:
                    send('choice', {'session': session, 'player': player, 'direction': selected, 'revision': revision})
                    submitted = True
            cues = []
            if phase == 'choosing':
                cues = [(state['deadline'] - n, 'tick', str(n)) for n in (3, 2, 1)]
            if phase == 'reveal':
                cues = [(state['deadline'], 'reveal', 'reveal')]
                if state['eliminated']:
                    cues.append((state['deadline'] + KNOCKOUT_DELAY, 'elimination', 'out'))
                if state['winner']:
                    cues.append((state['deadline'] + REVEAL_SECONDS, 'victory', 'win'))
            for when, sound, key in cues:
                if key not in scheduled_keys:
                    scheduled_keys.add(key)
                    if when >= clock - .1:
                        heapq.heappush(scheduled, (when, sound))
            while scheduled and scheduled[0][0] <= clock:
                _, sound = heapq.heappop(scheduled)
                if sound in sounds:
                    sounds[sound].play()
            visible_active = active or (phase == 'reveal' and clock < state['deadline'] and player in state['eliminated'])
            role = 'SOLO' if player == state['solo'] else ('TEAM' if visible_active else 'OUT')
            lines = ['Room ' + room + '  ' + role, 'Round ' + str(state['round']) + '/5']
            if phase == 'lobby':
                lines += [str(len(state['players'])) + '/4 players', 'Host click: start']
            elif phase in ('choosing', 'waiting'):
                lines += ['Choose: ' + (selected or '---') if active else 'Watch this round',
                          'Locked' if submitted else 'Time: ' + str(max(0, int(state['deadline'] - clock) + 1)),
                          'Waiting for choices' if phase == 'waiting' else 'Keep choice hidden!']
            elif phase == 'reveal' and clock < state['deadline']:
                lines += ['Choices locked', 'Get ready...']
            else:
                lines += ['Solo: ' + state['choices'].get(state['solo'], '?'),
                          'Remaining: ' + str(len(state['alive']))]
                if state['winner']:
                    lines += [state['winner'].upper() + ' WINS!', 'Host click: replay' if phase == 'finished' else '']
            if phase == 'reveal':
                lines = ['Round ' + str(state['round']) + ': ' + ('READY' if clock < state['deadline'] else 'REVEAL')]
                for i, seat in enumerate(state['players']):
                    label = 'P' + str(i + 1) + (' SOLO' if seat == state['solo'] else '')
                    answer = state['choices'].get(seat, 'OUT').upper()
                    if clock < state['deadline'] and seat in state['choices']:
                        answer = 'READY'
                    lines.append(label + ': ' + answer)
            hw.show_game(state, player, selected, submitted, room, clock, lines)
            time.sleep(.02)
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
