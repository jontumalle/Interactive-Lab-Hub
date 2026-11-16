"""Joystick/display adapter; terminal mode uses WASD + Enter (press return after keys)."""
import select
import sys
import time
import json
from pathlib import Path

CALIBRATION = Path(__file__).with_name('joystick.json')


class Hardware:
    def __init__(self, terminal=False):
        self.terminal = terminal
        self.previous = None
        self.last_text = None
        self.last_render = 0
        if terminal:
            return
        import board
        import digitalio
        import qwiic_joystick
        from adafruit_rgb_display import st7789
        from PIL import Image, ImageDraw, ImageFont
        self.joy = qwiic_joystick.QwiicJoystick()
        if not self.joy.connected:
            raise RuntimeError('Qwiic joystick missing; check I2C wiring')
        self.joy.begin()
        self.center = (self.joy.horizontal, self.joy.vertical)
        self.axis_signs = json.loads(CALIBRATION.read_text()) if CALIBRATION.exists() else {'x': 1, 'y': 1}
        self.backlight = digitalio.DigitalInOut(board.D22)
        self.backlight.switch_to_output(value=True)
        self.display = st7789.ST7789(board.SPI(), cs=digitalio.DigitalInOut(board.D5),
            dc=digitalio.DigitalInOut(board.D25), rst=None, baudrate=64000000,
            width=135, height=240, x_offset=53, y_offset=40, rotation=90)
        self.image = Image.new('RGB', (240, 135))
        self.draw = ImageDraw.Draw(self.image)
        self.font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15)
        self.code_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 15)

    def input(self):
        if self.terminal:
            if select.select([sys.stdin], [], [], 0)[0]:
                return {'w': 'up', 's': 'down', 'a': 'left', 'd': 'right', '': 'press', 'q': 'quit'}.get(sys.stdin.readline().strip())
            return None
        x = (self.joy.horizontal - self.center[0]) * self.axis_signs['x']
        y = (self.joy.vertical - self.center[1]) * self.axis_signs['y']
        value = None
        if not self.joy.button:
            value = 'press'
        elif max(abs(x), abs(y)) > 200:
            value = ('right' if x > 0 else 'left') if abs(x) > abs(y) else ('up' if y > 0 else 'down')
        event = value if value != self.previous else None
        self.previous = value
        return event

    def calibrate(self):
        if self.terminal:
            raise RuntimeError('Calibration requires the real joystick')
        for axis, direction, index in [('x', 'RIGHT', 0), ('y', 'UP', 1)]:
            self.show(['CALIBRATION', 'Release to center'])
            while True:
                values = (self.joy.horizontal, self.joy.vertical)
                if max(abs(values[i] - self.center[i]) for i in (0, 1)) < 150:
                    break
                time.sleep(.02)
            self.show(['CALIBRATION', 'Hold joystick ' + direction])
            while True:
                value = (self.joy.horizontal, self.joy.vertical)[index] - self.center[index]
                if abs(value) > 250:
                    self.axis_signs[axis] = 1 if value > 0 else -1
                    break
                time.sleep(.02)
        CALIBRATION.write_text(json.dumps(self.axis_signs))
        self.show(['Calibration saved', 'Restart to play'])

    def show(self, lines, monospace=False):
        text = '\n'.join(lines)
        frame = (text, monospace)
        if frame == self.last_text and (self.terminal or time.monotonic() - self.last_render < 1 / 12):
            return
        self.last_text = frame
        if self.terminal:
            print('\n' + text, flush=True)
        else:
            from visuals import menu
            self.last_render = time.monotonic()
            self.display.image(menu(lines, self.last_render))

    def show_game(self, state, player, selected, submitted, room, clock, lines):
        if self.terminal:
            self.show(lines)
            return
        now = time.monotonic()
        if now - self.last_render < 1 / 12:
            return
        from visuals import game_frame
        self.last_render = now
        self.last_text = None
        self.display.image(game_frame(state, player, selected, submitted, room, clock, now))
