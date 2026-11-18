"""Lazy-loaded real Pi hardware adapter for the existing lab wiring."""
import json
import os
from pathlib import Path
import statistics
import time


def calibration_path():
    """Keep per-device settings outside Git and out of the shared repository."""
    base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))
    return base/'last-transmission'/'joystick.json'


class PiHardware:
    def __init__(self, *, ignore_calibration=False):
        import board
        import digitalio
        import qwiic_joystick
        from adafruit_rgb_display import st7789
        self.joy = qwiic_joystick.QwiicJoystick()
        if not self.joy.connected:
            raise RuntimeError('Qwiic joystick missing. Check the shared bus and I2C configuration.')
        self.joy.begin()
        self.center = self._measure_center()
        self.signs = {'x': 1, 'y': 1}
        path = calibration_path()
        if path.exists() and not ignore_calibration:
            try:
                data = json.loads(path.read_text())
                for axis in ('x', 'y'):
                    if data.get(axis) in (-1, 1):
                        self.signs[axis] = data[axis]
            except (OSError, ValueError, TypeError):
                raise RuntimeError(f'Invalid joystick calibration at {path}; run --calibrate again.')
        self._pins = []
        self.backlight = digitalio.DigitalInOut(board.D22)
        self.backlight.switch_to_output(value=True)
        cs = digitalio.DigitalInOut(board.D5)
        dc = digitalio.DigitalInOut(board.D25)
        self._pins.extend((cs, dc, self.backlight))
        self.display = st7789.ST7789(board.SPI(), cs=cs, dc=dc, rst=None,
            baudrate=64000000, width=135, height=240,
            x_offset=53, y_offset=40, rotation=90)

    def _measure_center(self):
        xs, ys = [], []
        for _ in range(15):
            xs.append(self.joy.horizontal)
            ys.append(self.joy.vertical)
            time.sleep(.012)
        return statistics.median(xs), statistics.median(ys)

    @staticmethod
    def _normalize(value, center):
        span = max(1.0, 1023-center if value >= center else center)
        return max(-1.0, min(1.0, (value-center)/span))

    def read(self):
        x = self._normalize(self.joy.horizontal, self.center[0]) * self.signs['x']
        y = self._normalize(self.joy.vertical, self.center[1]) * self.signs['y']
        return x, y, not bool(self.joy.button)

    def show(self, image):
        self.display.image(image)

    def calibrate(self):
        from PIL import Image, ImageDraw
        from display import BACKGROUND, WHITE, font
        def prompt(lines):
            image = Image.new('RGB', (240,135), BACKGROUND)
            draw = ImageDraw.Draw(image)
            for i,line in enumerate(lines):
                draw.text((8,10+i*24),line,font=font(13),fill=WHITE)
            self.show(image)
        for axis, label, index in [('x','RIGHT',0),('y','UP',1)]:
            prompt(['JOYSTICK SETUP','Release to center'])
            start=time.monotonic()
            while True:
                vals=(self.joy.horizontal,self.joy.vertical)
                if max(abs(vals[i]-self.center[i]) for i in (0,1)) < 150:
                    break
                if time.monotonic()-start > 30:
                    raise RuntimeError('Center calibration timed out; restart with joystick released.')
                time.sleep(.02)
            prompt(['JOYSTICK SETUP','Hold '+label])
            start=time.monotonic()
            while True:
                vals=(self.joy.horizontal,self.joy.vertical)
                difference=vals[index]-self.center[index]
                if abs(difference)>250:
                    self.signs[axis]=1 if difference>0 else -1
                    break
                if time.monotonic()-start>30:
                    raise RuntimeError('Direction calibration timed out.')
                time.sleep(.02)
        path=calibration_path();path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(self.signs)+'\n')
        prompt(['Calibration saved','Restart with stick','released at center'])
        print('Calibration saved to',path)
        time.sleep(1)

    def close(self):
        self.backlight.value = False
        for pin in self._pins:
            pin.deinit()
