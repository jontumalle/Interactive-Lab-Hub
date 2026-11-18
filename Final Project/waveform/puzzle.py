"""Hardware-independent receiver puzzle and input state machine.

x is right-positive and y is up-positive, both normalized to [-1, 1].
Call update at a regular interval; one long update cannot acquire a signal.
"""
from copy import deepcopy
import math

SIGNALS = (
    {"frequency": 3.0, "amplitude": 0.60,
     "record": {"title": "TEST RECORD A", "symbol": "triangle",
                "text": "The triangle produced an odd-numbered code."}},
    {"frequency": 5.0, "amplitude": 0.35,
     "record": {"title": "TEST RECORD B", "symbol": "moon",
                "text": "The moon produced a code greater than 3 and less than 6."}},
)


class ReceiverPuzzle:
    DEAD_ZONE = 0.18
    FREQUENCY_LIMITS = (1.0, 6.0)
    AMPLITUDE_LIMITS = (0.15, 0.85)
    FREQUENCY_RATE = 1.15
    AMPLITUDE_RATE = 0.36
    FREQUENCY_TOLERANCE = 0.13
    AMPLITUDE_TOLERANCE = 0.045
    ACQUIRE_SECONDS = 1.0
    MAX_STEP_SECONDS = 0.10
    START_SETTINGS = ((1.55, 0.28), (2.10, 0.70))

    def __init__(self):
        self.reset()

    def reset(self):
        self.stage = "tuning"
        self.signal_index = 0
        self.frequency, self.amplitude = self.START_SETTINGS[0]
        self.match_time = 0.0
        self.messages = []
        self.archive_index = 0
        self._nav_armed = False
        self._press_previous = False
        self._centered = True
        self.status = "Match both curves"

    @staticmethod
    def _finite(value, fallback=0.0):
        try:
            value = float(value)
            return value if math.isfinite(value) else fallback
        except (TypeError, ValueError):
            return fallback

    def _axis(self, value):
        value = max(-1.0, min(1.0, self._finite(value)))
        if abs(value) <= self.DEAD_ZONE:
            return 0.0
        return math.copysign((abs(value) - self.DEAD_ZONE) / (1.0 - self.DEAD_ZONE), value)

    def _matched(self):
        target = SIGNALS[self.signal_index]
        return (abs(self.frequency - target["frequency"]) <= self.FREQUENCY_TOLERANCE + 1e-9
                and abs(self.amplitude - target["amplitude"]) <= self.AMPLITUDE_TOLERANCE + 1e-9)

    def update(self, dt, x=0.0, y=0.0, press=False):
        dt = max(0.0, min(self.MAX_STEP_SECONDS, self._finite(dt)))
        x, y = self._axis(x), self._axis(y)
        self._centered = x == 0.0 and y == 0.0
        press_edge = bool(press) and not self._press_previous
        self._press_previous = bool(press)

        if self.stage == "tuning":
            low, high = self.FREQUENCY_LIMITS
            self.frequency = max(low, min(high, self.frequency + x * self.FREQUENCY_RATE * dt))
            low, high = self.AMPLITUDE_LIMITS
            self.amplitude = max(low, min(high, self.amplitude + y * self.AMPLITUDE_RATE * dt))
            if self._matched() and self._centered:
                self.match_time += dt
                self.status = "Hold steady"
                if self.match_time + 1e-9 >= self.ACQUIRE_SECONDS:
                    self.match_time = self.ACQUIRE_SECONDS
                    self.messages.append({"signal_index": self.signal_index,
                                          "type": "diagnostic",
                                          **deepcopy(SIGNALS[self.signal_index]["record"])})
                    self.archive_index = len(self.messages) - 1
                    self.stage = "complete" if self.signal_index == len(SIGNALS) - 1 else "recovered"
                    self.status = "Diagnostic records recovered" if self.stage == "complete" else "Test record recovered"
                    # A neutral frame after acquisition must precede navigation.
                    self._nav_armed = False
            else:
                self.match_time = 0.0
                self.status = "Release to acquire" if self._matched() else "Match both curves"
            return

        if self._centered and not press:
            self._nav_armed = True
        if self.stage == "recovered":
            if self._nav_armed and (x > 0.0 or press_edge):
                self.signal_index += 1
                self.frequency, self.amplitude = self.START_SETTINGS[self.signal_index]
                self.match_time = 0.0
                self.stage = "tuning"
                self.status = "Match both curves"
                self._nav_armed = False
            return
        if self.stage == "complete" and self._nav_armed:
            if y != 0.0:
                step = -1 if y > 0 else 1
                self.archive_index = (self.archive_index + step) % len(self.messages)
                self._nav_armed = False
            elif press_edge:
                self.archive_index = (self.archive_index + 1) % len(self.messages)
                self._nav_armed = False

    def snapshot(self):
        target = SIGNALS[self.signal_index]
        return {
            "stage": self.stage,
            "signal_index": self.signal_index,
            "signal_count": len(SIGNALS),
            "frequency": self.frequency,
            "amplitude": self.amplitude,
            "target_frequency": target["frequency"],
            "target_amplitude": target["amplitude"],
            "match_progress": min(1.0, self.match_time / self.ACQUIRE_SECONDS),
            "matched": self._matched(),
            "controls_centered": self._centered,
            "can_advance": self._nav_armed,
            "status": self.status,
            "messages": deepcopy(self.messages),
            "archive_index": self.archive_index,
        }
