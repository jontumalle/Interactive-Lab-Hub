"""Guided table setup: learn each utensil's sensor thresholds from live readings.

Pure logic with no hardware access: the sensor loop feeds it MPR121 filtered readings.
A utensil resting on its copper pad LOWERS that pad's reading, so "drop" below means
(empty reading - current reading).
"""
from statistics import median

MAX_EMPTY_NOISE = 30   # counts a pad's reading may move while it is measured empty
SETTLE_SECONDS = 0.7   # ignore readings this long after "measure" is tapped
STUCK_SECONDS = 30     # after this long without detecting a utensil, show a hint


def spread(values):
    """Peak-to-peak range of the readings, ignoring the highest and lowest few so a single
    stray sample (an I2C glitch) does not count as wobble."""
    ordered = sorted(values)
    trim = len(ordered) // 15  # 2 of 30 samples at each end
    kept = ordered[trim:len(ordered) - trim]
    return round(kept[-1] - kept[0])


class PadCalibration:
    """Learns one pad. The utensil counts as placed once the drop has been above `trigger`
    for (nearly) every reading over the last `hold` seconds; thresholds are then 40% and 20%
    of the median drop. A stray dip while it settles does not restart the clock."""

    def __init__(self, empty, noise, hold=1.2, steady=0.9):
        self.empty = empty
        self.hold = hold
        self.steady = steady  # fraction of the window that must clear the trigger
        # Same bar `fork_sensor.py --calibrate` uses for "usable": the drop must be at
        # least twice the pad's own wobble, so the thresholds sit above the noise.
        self.trigger = max(6, 2 * noise)
        self.drop = 0  # latest drop, shown on the phone while waiting
        self._window = []  # (time, reading) for the last `hold` seconds
        self.result = None  # (on, off) once learned

    def update(self, reading, now):
        if self.result:
            return
        self.drop = self.empty - reading
        self._window.append((now, reading))
        while now - self._window[0][0] > self.hold:
            self._window.pop(0)
        if now - self._window[0][0] < self.hold * 0.9:
            return  # not enough history yet
        drops = [self.empty - r for _, r in self._window]
        if sum(d > self.trigger for d in drops) >= self.steady * len(drops):
            drop = median(drops)
            # Putting a utensil back should be easier to detect than picking one up is to miss:
            # a utensil resting less firmly than it did here must still count as "on its pad".
            self.result = (drop * 0.4, drop * 0.2)


class TableCalibrator:
    """Steps: clear (waiting for 'table is clear') -> measuring -> placing -> done.

    `items` is [(utensil id, display name)] in the order they are placed.
    """

    def __init__(self, items, measure_seconds=1.5, hold=1.2):
        self.items = list(items)
        self.measure_seconds = measure_seconds
        self.hold = hold
        self.reset()

    def reset(self, notice=''):
        self.step = 'clear'
        self.notice = notice
        self.references = {}  # id -> mean empty reading
        self.results = {}     # id -> (on, off)
        self._samples = {}
        self._measure_start = 0
        self._measure_end = 0
        self._pads = {}
        self._current = 0
        self._placing_since = 0
        self._stuck = False

    def start_measuring(self, now):
        if self.step == 'clear':
            self.step = 'measuring'
            self.notice = ''
            self._samples = {uid: [] for uid, _ in self.items}
            # Skip the first moments: a utensil lifted just before the tap is still settling.
            self._measure_start = now + SETTLE_SECONDS
            self._measure_end = self._measure_start + self.measure_seconds

    def feed(self, readings, now):
        """Call every tick while measuring/placing. `readings` maps utensil id -> value."""
        if self.step == 'measuring':
            if now >= self._measure_start:
                for uid, value in readings.items():
                    self._samples[uid].append(value)
            if now >= self._measure_end:
                self._finish_measuring(now)
        elif self.step == 'placing':
            uid = self.items[self._current][0]
            pad = self._pads[uid]
            pad.update(readings[uid], now)
            if pad.result:
                self.results[uid] = pad.result
                self._current += 1
                self._placing_since = now
                self._stuck = False
                if self._current == len(self.items):
                    self.step = 'done'
            elif now - self._placing_since > STUCK_SECONDS:
                self._stuck = True

    def _finish_measuring(self, now):
        noisy = []
        for uid, name in self.items:
            values = self._samples[uid]
            noise = spread(values)
            if noise > MAX_EMPTY_NOISE:
                noisy.append(f'{name.lower()} {noise}')
            self.references[uid] = sum(values) / len(values)
            self._pads[uid] = PadCalibration(self.references[uid], noise, self.hold)
        if noisy:
            self.reset(f"An empty pad's reading moved too much while measuring ({', '.join(noisy)}; limit "
                       f"{MAX_EMPTY_NOISE}). Make sure every utensil is fully off its pad, keep your hands away "
                       "from the pads and wires, wait a moment, then measure again.")
            return
        self.step = 'placing'
        self._current = 0
        self._placing_since = now

    def view(self):
        """What the phone shows: step, a message, and a status for each utensil."""
        items = []
        for i, (uid, name) in enumerate(self.items):
            if uid in self.results:
                status = 'done'
            elif self.step == 'placing' and i == self._current:
                status = 'current'
            else:
                status = 'pending'
            items.append({'id': uid, 'name': name, 'status': status})
        detail = ''
        if self.step == 'placing':
            pad = self._pads[self.items[self._current][0]]
            detail = f'Pad reading: drop {max(0, round(pad.drop))}, needs more than {round(pad.trigger)}.'
        if self.step == 'clear':
            message = self.notice or 'Take every utensil off its pad and keep your hands away from the table.'
        elif self.step == 'measuring':
            message = 'Measuring the empty table. Hold still…'
        elif self.step == 'placing':
            name = self.items[self._current][1].lower()
            message = f'Now place the {name} on its pad and leave it there.'
            if self._stuck:
                message += (' Not detecting it? Press it firmly onto the copper tape and check the '
                            'connection to the pad.')
        else:
            message = 'Every utensil was detected. Your table is ready.'
        return {'step': self.step, 'message': message, 'detail': detail, 'items': items}
