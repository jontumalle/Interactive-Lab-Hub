import time
import subprocess
import digitalio
import board
from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789

# For Lab 2b
import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Configuration for CS and DC pins (these are FeatherWing defaults on M0/M4):
cs_pin = digitalio.DigitalInOut(board.D5) 
dc_pin = digitalio.DigitalInOut(board.D25)
reset_pin = None

# Config for display baudrate (default max is 24mhz):
BAUDRATE = 64000000

# Setup SPI bus using hardware SPI:
spi = board.SPI()

# Create the ST7789 display:
disp = st7789.ST7789(
    spi,
    cs=cs_pin,
    dc=dc_pin,
    rst=reset_pin,
    baudrate=BAUDRATE,
    width=135,
    height=240,
    x_offset=53,
    y_offset=40,
)

# Create blank image for drawing.
# Make sure to create image with mode 'RGB' for full color.
height = disp.width  # we swap height/width to rotate it to landscape!
width = disp.height
image = Image.new("RGB", (width, height))
rotation = 90

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0, 0, width, height), outline=0, fill=(0, 0, 0))
disp.image(image, rotation)
# Draw some shapes.
# First define some constants to allow easy resizing of shapes.
padding = -2
top = padding
bottom = height - padding
# Move left to right keeping track of the current x position for drawing shapes.
x = 0

# Alternatively load a TTF font.  Make sure the .ttf font file is in the
# same directory as the python script!
# Some other nice fonts to try: http://www.dafont.com/bitmap.php
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)

# Turn on the backlight
backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output()
backlight.value = True

while True:
    # Draw a black filled box to clear the image.
    draw.rectangle((0, 0, width, height), outline=0, fill=(0, 0, 0))

    # Lab 2b - Modify to show next pass
    def fetch_passes():
        CORNELL_TECH_LAT = 40.75559
        CORNELL_TECH_LONG = -73.95613
        query = urlencode({"lat": CORNELL_TECH_LAT, "lon": CORNELL_TECH_LONG, "n":2, "days_ahead": 1})
        # API Endpoint was found with research with AI
        API = "https://iss-api.polluxlabs.io/iss-pass"
        request = Request(f"{API}?{query}", headers={"User-Agent": "Lab2-ISSPassClock/1.0"})
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
                return rise, set_time, True
            if rise > now:
                return rise, set_time, False
        return None

    now = time.time()
    (rise, set_time, is_active) = get_active_or_next_pass(fetch_passes(), now)
    if is_active:
        label = 'OVERHEAD NOW'
        remaining = set_time - now
    else:
        label = 'ISS WILL PASS IN'
        remaining = rise - now

    def format_duration(seconds):
        return datetime.fromtimestamp(seconds, timezone.utc).strftime("%H:%M:%S")

    y = top
    draw.text((x, y), label, font=font, fill="#FFFFFF")
    y += draw.textbbox((0,0), label, font=font)[3]
    draw.text((x, y), format_duration(remaining), font=font, fill="#FFFFFF")

    # Display image.
    disp.image(image, rotation)
    time.sleep(1)
