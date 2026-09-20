"""ISS pass countdown for the Mini PiTFT.

Set HOME_LAT and HOME_LON below (or as environment variables) to the
location you want to track.  The address itself never needs to be stored.

The animation is intentionally schematic: the station travels along an
orbital arc toward a small beacon that represents home.  The large timer is
the useful part; the moving station makes it immediately clear what is being
counted down.
"""

import json
import math
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789


# Replace these with coordinates for home, not the street address.
HOME_LAT = os.environ.get("HOME_LAT")
HOME_LON = os.environ.get("HOME_LON")
PASS_API = "https://iss-api.polluxlabs.io/iss-pass"
REFRESH_SECONDS = 15 * 60

WIDTH, HEIGHT = 240, 135
ROTATION = 90


def make_display():
    cs_pin = digitalio.DigitalInOut(board.D5)
    dc_pin = digitalio.DigitalInOut(board.D25)
    spi = board.SPI()
    return st7789.ST7789(
        spi,
        cs=cs_pin,
        dc=dc_pin,
        rst=None,
        baudrate=64_000_000,
        width=135,
        height=240,
        x_offset=53,
        y_offset=40,
    )


def fetch_passes():
    if HOME_LAT is None or HOME_LON is None:
        raise RuntimeError("Set HOME_LAT and HOME_LON first")
    latitude = float(HOME_LAT)
    longitude = float(HOME_LON)
    query = urlencode({"lat": latitude, "lon": longitude, "n": 5, "days_ahead": 14})
    request = Request(f"{PASS_API}?{query}", headers={"User-Agent": "Lab2-ISSPassClock/1.0"})
    with urlopen(request, timeout=10) as response:  # nosec B310 - fixed HTTPS URL
        payload = json.load(response)
    return payload.get("passes", [])


def iso_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def get_active_or_next_pass(passes, now):
    for item in passes:
        rise = iso_time(item["rise"]["time"])
        set_time = iso_time(item["set"]["time"])
        if rise <= now <= set_time:
            return item, rise, set_time, True
        if rise > now:
            return item, rise, set_time, False
    return None


def format_duration(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%H:%M:%S")


def draw_station(draw, cx, cy, scale=1):
    """Small, high-contrast ISS silhouette."""
    wing = max(3, int(13 * scale))
    body = max(3, int(5 * scale))
    draw.rectangle((cx - wing, cy - 2, cx - body, cy + 2), fill="#f3c969")
    draw.rectangle((cx + body, cy - 2, cx + wing, cy + 2), fill="#f3c969")
    draw.rectangle((cx - 3, cy - 3, cx + 3, cy + 3), fill="#ffffff")
    draw.line((cx, cy - 6, cx, cy + 6), fill="#ffffff", width=1)


def render(draw, fonts, pass_info, now, error=None):
    title_font, timer_font, small_font = fonts
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill="#050914")

    # Star field and a thin orbital arc: visual language for an orbit, not a clock face.
    for x, y in ((12, 23), (53, 13), (98, 29), (165, 12), (222, 29), (206, 73), (28, 91)):
        draw.point((x, y), fill="#8193b7")
    draw.arc((53, 16, 229, 116), 188, 350, fill="#5577aa", width=2)
    draw.text((8, 5), "ISS  /  HOME PASS", font=title_font, fill="#d8e7ff")

    if pass_info:
        item, rise, set_time, active = pass_info
        duration = max(1, set_time - rise)
        if active:
            remaining = set_time - now
            label = "OVERHEAD NOW"
            progress = min(1.0, max(0.0, (now - rise) / duration))
            timer_color = "#ffcf66"
        else:
            remaining = rise - now
            label = "NEXT PASS IN"
            progress = 0.0
            timer_color = "#ffffff"

        draw.text((8, 25), label, font=small_font, fill="#9bb2d8")
        draw.text((8, 36), format_duration(remaining), font=timer_font, fill=timer_color)

        # ISS moves along the arc as the pass progresses; waiting state has it at orbit start.
        station_x = int(65 + 145 * progress)
        station_y = int(83 - 47 * math.sin(math.pi * progress))
        draw_station(draw, station_x, station_y, 1.0 if active else 0.8)

        # Home beacon: the target that makes “above this address” legible.
        draw.ellipse((222, 87, 230, 95), outline="#67e8f9", width=2)
        draw.line((226, 77, 226, 87), fill="#67e8f9", width=1)
        draw.text((188, 99), "HOME", font=small_font, fill="#67e8f9")
        peak = item["culmination"].get("elevation_deg", 0)
        draw.text((8, 119), f"PEAK {round(peak)}°  •  {item['rise']['time'][11:16]} UTC", font=small_font, fill="#8193b7")
    else:
        draw.text((8, 42), "NO PASS DATA", font=timer_font, fill="#ff7b72")
        draw.text((8, 76), error or "Check Wi-Fi and coordinates", font=small_font, fill="#d8e7ff")


def main():
    display = make_display()
    backlight = digitalio.DigitalInOut(board.D22)
    backlight.switch_to_output(value=True)
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    fonts = (
        ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13),
        ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 26),
        ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10),
    )

    passes = []
    last_fetch = 0
    error = None
    while True:
        now = time.time()
        if now - last_fetch > REFRESH_SECONDS or not passes:
            try:
                passes = fetch_passes()
                last_fetch = now
                error = None
            except Exception as exc:  # keep showing the last good result offline
                error = str(exc)[:28]
                last_fetch = now

        pass_info = get_active_or_next_pass(passes, now)
        if pass_info is None and passes:
            # The returned window has expired; force a refresh on the next frame.
            last_fetch = 0
        render(draw, fonts, pass_info, now, error)
        display.image(image, ROTATION)
        time.sleep(1)


if __name__ == "__main__":
    main()

