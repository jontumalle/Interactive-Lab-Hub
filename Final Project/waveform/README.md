# Waveform Receiver Puzzle

Joystick waveform matching for the existing Raspberry Pi 5, Qwiic joystick, and landscape 240 by 135 Mini PiTFT. The Python core and Pillow renderer are shared with an arrow key browser simulator. No external services are needed at runtime.

## Run on the Pi

From the existing repository checkout, fetch the branch and enter the project:

```bash
git fetch origin
git switch final-project
git pull --ff-only origin final-project
cd "Final Project/waveform"
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -r requirements-pi.txt
bash run_pi.sh
```

Use the same enabled SPI and I2C setup as the earlier display and joystick labs. Leave the joystick centered during startup. The launcher temporarily stops an active `piscreen.service` and restores it when the receiver exits, including normal Ctrl+C shutdown. It only restarts the service if it was active before launch.

If physical right decreases frequency or physical up decreases amplitude, run the calibration routine, following its screen instructions, then restart with the stick centered:

```bash
bash run_pi.sh --calibrate
bash run_pi.sh
```

Each Pi saves its axis calibration outside Git in its user configuration directory. To start a fresh session, exit with Ctrl+C and run the launcher again. Plain `python play.py` also works when you manage screen ownership yourself.

## Play

- Move left or right to change frequency; up or down to change amplitude. Centering retains the chosen values.
- Match the teal solid Target curve with the pale dashed Signal curve. Release the controls and hold the match for one second to acquire automatically. This replaces the earlier planned click to lock, so browser play needs only arrow keys.
- The first successful lock reveals Voice = Triangle and Beacon = Cross. Release the controls, then move right or click to continue to the second signal.
- The second lock reveals Sensor = Hexagon and Distress = Cross plus Moon. Both fragments remain available; move up or down to review them.

Only encrypted requirements are revealed. The receiver never provides the decoder setting, decoded meanings, or target parameter numbers to the player.

## Browser simulator on the Pi or laptop

The simulator requires Pillow, not the GPIO libraries. From this directory with the virtual environment active:

```bash
python serve.py --host 0.0.0.0
```

Open `http://<PI_IP>:8765` on another device on the same trusted network, or `http://localhost:8765` in the Pi browser. Find the Pi address with `hostname -I`. Arrow keys or the on screen directional buttons control the puzzle. The screen image is produced by exactly the same `display.render` function as the physical display; enlargement changes display size only. The 1x option shows its 240 by 135 pixel raster, not a calibrated physical screen size.

This is a separate simulator session and does not operate the physical screen. Use `bash run_pi.sh` for the hardware game. The browser server shares one session across connected tabs; New session resets it for everyone. It has no login and is intended for local testing. Omit `--host 0.0.0.0` for loopback only access on a laptop.

## Verification and remaining hardware checks

```bash
python -m unittest -v test_puzzle.py
```

Nine behavior tests cover time based controls, limits, noise dead zone, uninterrupted centered acquisition, navigation edges, both captures, archive, reset, and canonical frame dimensions. These tests do not establish GPIO access, physical axis direction, actual screen refresh speed, or joystick responsiveness; check those on the Pi. The runner reuses the existing lab screen configuration, and bus wiring remains a build concern.

The browser clears held keys on blur and uses a short input timeout to avoid stale controls. Server responses omit numeric targets, although the visible target curve remains intentionally available as the matching reference. There is no audio yet; messages are shown on screen.
