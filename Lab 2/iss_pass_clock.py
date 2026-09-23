"""A stargazer's ISS sky clock for the Mini PiTFT.

Edit ``iss_locations.json`` to choose the stargazing locations to track. The
two Mini PiTFT buttons cycle backward and forward through that list.

The display is organized around the decision a viewer needs to make: when to
go outside, how long the *visible* viewing window lasts, and how much time
remains once the ISS is in the sky. During an active pass, the station travels
along the same arc that is drawn on screen.
"""

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789


PASS_API = "https://iss-api.polluxlabs.io/iss-pass"
# The API refreshes its orbital elements about every six hours. Refreshing more
# often does not make a saved forecast meaningfully more accurate.
REFRESH_SECONDS = 6 * 60 * 60
RETRY_SECONDS = 15 * 60
FRAME_SECONDS = 0.1
LOCATIONS_FILE = Path(__file__).with_name("iss_locations.json")
PASS_CACHE_FILE = Path(__file__).with_name("iss_pass_cache.json")

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


def load_locations():
    """Load and validate the user-editable list of stargazing locations."""
    try:
        with LOCATIONS_FILE.open(encoding="utf-8") as config_file:
            locations = json.load(config_file)["locations"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Check {LOCATIONS_FILE.name}") from exc

    if not isinstance(locations, list) or not locations:
        raise RuntimeError(f"Add at least one location to {LOCATIONS_FILE.name}")
    for location in locations:
        if not isinstance(location, dict) or not all(
            key in location for key in ("name", "latitude", "longitude")
        ):
            raise RuntimeError(f"Each location needs name, latitude, and longitude in {LOCATIONS_FILE.name}")
        location["latitude"] = float(location["latitude"])
        location["longitude"] = float(location["longitude"])
    return locations


def fetch_passes(location):
    latitude = location["latitude"]
    longitude = location["longitude"]
    # A pass can be above the horizon without being visible (for example,
    # while the ISS is in Earth's shadow). Ask the API for sightable passes.
    query = urlencode(
        {"lat": latitude, "lon": longitude, "n": 20, "days_ahead": 14, "visible_only": "true"}
    )
    request = Request(f"{PASS_API}?{query}", headers={"User-Agent": "Lab2-ISSPassClock/1.0"})
    with urlopen(request, timeout=10) as response:  # nosec B310 - fixed HTTPS URL
        payload = json.load(response)
    return payload.get("passes", [])


def location_key(location):
    """A stable cache key that changes when a location's coordinates change."""
    return f"{location['name']}|{location['latitude']:.6f}|{location['longitude']:.6f}"


def load_pass_cache():
    """Return saved forecasts, if any; a bad cache should never stop the clock."""
    try:
        with PASS_CACHE_FILE.open(encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
        locations = cache.get("locations", {})
        return locations if isinstance(locations, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_pass_cache(cache):
    """Atomically save forecasts so an interrupted write keeps the old cache."""
    temporary_file = PASS_CACHE_FILE.with_suffix(".tmp")
    try:
        with temporary_file.open("w", encoding="utf-8") as cache_file:
            json.dump({"locations": cache}, cache_file, separators=(",", ":"))
        temporary_file.replace(PASS_CACHE_FILE)
    except OSError:
        # The in-memory cache still lets the current session work if the SD
        # card is unavailable or read-only.
        try:
            temporary_file.unlink(missing_ok=True)
        except OSError:
            pass


def iso_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def visible_window(item):
    """Return the interval when the ISS is visible, not merely above horizon."""
    start = item.get("visible_start") or item["rise"]["time"]
    end = item.get("visible_end") or item["set"]["time"]
    return iso_time(start), iso_time(end)


def get_active_or_next_pass(passes, now):
    for item in passes:
        start, end = visible_window(item)
        if start <= now <= end:
            return item, start, end, True
        if start > now:
            return item, start, end, False
    return None


def format_duration(seconds, include_hours=True):
    """Format an interval without treating it as a wall-clock timestamp."""
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if include_hours or hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def local_time(timestamp):
    """Short, local time suitable for a tiny planning display."""
    return datetime.fromtimestamp(timestamp).strftime("%I:%M %p").lstrip("0")


def pass_label(timestamp):
    """Use Tonight/Tomorrow when useful, otherwise show the weekday."""
    when = datetime.fromtimestamp(timestamp)
    today = datetime.now().date()
    offset = (when.date() - today).days
    if offset == 0:
        return "TONIGHT"
    if offset == 1:
        return "TOMORROW"
    return when.strftime("%a").upper()


def draw_station(draw, cx, cy, scale=1):
    """Small, high-contrast ISS silhouette."""
    wing = max(3, int(13 * scale))
    body = max(3, int(5 * scale))
    draw.rectangle((cx - wing, cy - 2, cx - body, cy + 2), fill="#f3c969")
    draw.rectangle((cx + body, cy - 2, cx + wing, cy + 2), fill="#f3c969")
    draw.rectangle((cx - 3, cy - 3, cx + 3, cy + 3), fill="#ffffff")
    draw.line((cx, cy - 6, cx, cy + 6), fill="#ffffff", width=1)


def draw_sky_clock(draw, progress, active):
    """Draw the pass timeline and return the ISS position on its exact arc."""
    # Keep the entire sky visualization below the countdown so the time is
    # always readable, even when the ISS is at either end of its path.
    arc_box = (70, 74, 230, 142)
    start_angle, end_angle = 188, 350
    arc_color = "#6c89ba" if active else "#314765"
    draw.arc(arc_box, start_angle, end_angle, fill=arc_color, width=2)

    # Tick marks turn the orbital path into a duration clock at a glance.
    center_x, center_y = 150, 108
    radius_x, radius_y = 80, 34
    for fraction in (0, 0.25, 0.5, 0.75, 1):
        angle = math.radians(start_angle + (end_angle - start_angle) * fraction)
        outer_x = center_x + radius_x * math.cos(angle)
        outer_y = center_y + radius_y * math.sin(angle)
        inner_x = center_x + (radius_x - 4) * math.cos(angle)
        inner_y = center_y + (radius_y - 4) * math.sin(angle)
        draw.line((inner_x, inner_y, outer_x, outer_y), fill="#8ba2ca", width=1)

    angle = math.radians(start_angle + (end_angle - start_angle) * progress)
    station_x = int(center_x + radius_x * math.cos(angle))
    station_y = int(center_y + radius_y * math.sin(angle))
    return station_x, station_y


def render(draw, fonts, location, pass_info, now, error=None, stale=False):
    title_font, timer_font, small_font, detail_font = fonts
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill="#050914")

    for x, y in ((12, 25), (48, 14), (98, 27), (165, 13), (222, 28), (206, 76), (28, 94)):
        draw.point((x, y), fill="#8193b7")
    location_name = location.get("display_name", location["name"])
    draw.text((8, 4), f"ISS / {location_name}", font=title_font, fill="#d8e7ff")
    draw.text((181, 6), datetime.fromtimestamp(now).strftime("%I:%M").lstrip("0"), font=small_font, fill="#9bb2d8")

    if pass_info:
        _item, start, end, active = pass_info
        duration = max(1, end - start)
        if active:
            remaining = end - now
            label = "LOOK UP NOW"
            progress = min(1.0, max(0.0, (now - start) / duration))
            timer_color = "#ffcf66"
        else:
            remaining = start - now
            label = "NEXT VISIBLE PASS"
            progress = 0.0
            timer_color = "#ffffff"

        draw.text((8, 23), label, font=small_font, fill="#9bb2d8")
        draw.text((8, 33), format_duration(remaining), font=timer_font, fill=timer_color)
        station_x, station_y = draw_sky_clock(draw, progress, active)
        draw_station(draw, station_x, station_y, 1.0 if active else 0.8)

        # The two end markers make the arc a readable start-to-finish window.
        draw.ellipse((68, 100, 74, 106), outline="#67e8f9", width=1)
        draw.ellipse((226, 99, 232, 105), outline="#67e8f9", width=1)
        estimate = "EST. " if stale else ""
        if active:
            detail = f"{estimate}{format_duration(duration, include_hours=False)} VISIBLE  |  ENDS {local_time(end)}"
        else:
            detail = f"{estimate}{pass_label(start)} {local_time(start)}  |  {format_duration(duration, include_hours=False)} VISIBLE"
        draw.rectangle((0, 118, WIDTH, HEIGHT), fill="#0b1425")
        draw.text((8, 121), detail, font=detail_font, fill="#c3d5f0")
    else:
        if error == "Loading forecast...":
            dots = "." * (int(now * 2) % 3 + 1)
            draw.text((8, 43), f"LOADING FORECAST{dots}", font=title_font, fill="#d8e7ff")
            draw.text((8, 67), "Getting passes for this location", font=small_font, fill="#9bb2d8")
        elif error == "Refreshing forecast...":
            dots = "." * (int(now * 2) % 3 + 1)
            draw.text((8, 43), f"UPDATING FORECAST{dots}", font=title_font, fill="#d8e7ff")
            draw.text((8, 67), "Looking for the next visible pass", font=small_font, fill="#9bb2d8")
        else:
            draw.text((8, 43), "FORECAST UNAVAILABLE", font=title_font, fill="#ff7b72")
            draw.text((8, 67), error or "Connect once to save a forecast", font=small_font, fill="#d8e7ff")


def main():
    locations = load_locations()
    location_index = 0
    pass_cache = load_pass_cache()
    last_fetch_attempt = {}
    fetch_errors = {}
    fetch_future = None
    fetch_key = None
    display = make_display()
    backlight = digitalio.DigitalInOut(board.D22)
    backlight.switch_to_output(value=True)
    button_a = digitalio.DigitalInOut(board.D23)
    button_b = digitalio.DigitalInOut(board.D24)
    button_a.switch_to_input(pull=digitalio.Pull.UP)
    button_b.switch_to_input(pull=digitalio.Pull.UP)
    was_a_pressed = False
    was_b_pressed = False
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    fonts = (
        ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13),
        ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 26),
        ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10),
        ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9),
    )

    # Fetching happens in one background worker. The display stays responsive,
    # so switching locations never waits on Wi-Fi or an API response.
    with ThreadPoolExecutor(max_workers=1) as fetcher:
        while True:
            now = time.time()
            a_pressed = not button_a.value
            b_pressed = not button_b.value
            if a_pressed and not was_a_pressed:
                location_index = (location_index - 1) % len(locations)
            elif b_pressed and not was_b_pressed:
                location_index = (location_index + 1) % len(locations)
            was_a_pressed = a_pressed
            was_b_pressed = b_pressed

            if fetch_future is not None and fetch_future.done():
                try:
                    pass_cache[fetch_key] = {
                        "fetched_at": now,
                        "passes": fetch_future.result(),
                    }
                    fetch_errors.pop(fetch_key, None)
                    save_pass_cache(pass_cache)
                except Exception as exc:  # keep showing the last good result offline
                    fetch_errors[fetch_key] = str(exc)[:28]
                fetch_future = None
                fetch_key = None

            location = locations[location_index]
            key = location_key(location)
            cached_forecast = pass_cache.get(key, {})
            passes = cached_forecast.get("passes", [])
            fetched_at = cached_forecast.get("fetched_at", 0)
            stale = bool(cached_forecast) and now - fetched_at > REFRESH_SECONDS
            pass_info = get_active_or_next_pass(passes, now)

            needs_refresh = stale or not passes or pass_info is None
            can_retry = now - last_fetch_attempt.get(key, 0) >= RETRY_SECONDS
            if needs_refresh and fetch_future is None and can_retry:
                fetch_future = fetcher.submit(fetch_passes, location)
                fetch_key = key
                last_fetch_attempt[key] = now

            if not passes:
                error = "Loading forecast..." if fetch_key == key else fetch_errors.get(key, "No saved forecast")
            elif pass_info is None:
                error = "Refreshing forecast..."
            else:
                error = None
            render(draw, fonts, location, pass_info, now, error, stale)
            display.image(image, ROTATION)
            time.sleep(FRAME_SECONDS)


if __name__ == "__main__":
    main()
