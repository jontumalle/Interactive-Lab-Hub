"""Canonical 240 x 135 player display, shared by Pi and browser simulator."""
from functools import lru_cache
import math
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 240, 135
BACKGROUND = (8, 18, 23)
GRID = (25, 44, 50)
TEAL = (76, 225, 200)
WHITE = (240, 248, 248)
MUTED = (153, 180, 187)


@lru_cache(maxsize=20)
def font(size, bold=False):
    name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    choices = [os.getenv('WAVEFORM_FONT_BOLD' if bold else 'WAVEFORM_FONT', ''), name,
               '/usr/share/fonts/truetype/dejavu/' + name,
               str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/truetype' / name),
               '/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf']
    for path in choices:
        if not path:
            continue
        try:
            return ImageFont.truetype(path, size)
        except (OSError, ValueError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def text(draw, xy, value, size=11, color=WHITE, bold=False):
    draw.text(xy, value, font=font(size, bold), fill=color)


def centered(draw, y, value, size=11, color=WHITE, bold=False):
    f = font(size, bold)
    box = draw.textbbox((0, 0), value, font=f)
    draw.text(((WIDTH-(box[2]-box[0]))/2, y), value, font=f, fill=color)


def glyph(draw, name, x, y, r=9, color=TEAL):
    if name == 'triangle':
        draw.line([(x, y-r), (x-r, y+r*.75), (x+r, y+r*.75), (x, y-r)], fill=color, width=2)
    elif name == 'cross':
        draw.line((x-r, y, x+r, y), fill=color, width=3)
        draw.line((x, y-r, x, y+r), fill=color, width=3)
    elif name == 'hexagon':
        points = [(x+r*math.cos(a*math.pi/3), y+r*math.sin(a*math.pi/3)) for a in range(6)]
        draw.line(points+[points[0]], fill=color, width=2)
    elif name == 'moon':
        draw.ellipse((x-r, y-r, x+r, y+r), fill=color)
        draw.ellipse((x-r+6, y-r-1, x+r+6, y+r+1), fill=BACKGROUND)
    else:
        raise ValueError('Unknown cipher glyph: '+str(name))


def render(snapshot):
    """Return the exact frame sent to the Mini PiTFT, never numeric solutions."""
    image = Image.new('RGB', (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    stage = snapshot['stage']
    index = snapshot['signal_index']
    if stage == 'tuning':
        text(draw, (8, 4), 'RECEIVER', 11, bold=True)
        text(draw, (194, 4), f'{index+1:02d}/02', 11, TEAL, bold=True)
        draw.line((8, 21, 20, 21), fill=TEAL, width=2)
        text(draw, (25, 15), 'TARGET', 10, TEAL)
        draw.line((128, 21, 133, 21), fill=WHITE, width=2)
        draw.line((137, 21, 142, 21), fill=WHITE, width=2)
        text(draw, (147, 15), 'SIGNAL', 10, WHITE)
        x0, y0, x1, y1 = 8, 33, 231, 94
        for x in range(x0, x1+1, 28):
            draw.line((x, y0, x, y1), fill=GRID)
        for y in range(y0, y1+1, 15):
            draw.line((x0, y, x1, y), fill=GRID)
        mid = (y0+y1)/2
        scale = (y1-y0)/2
        for frequency, amplitude, color, dashed in [
                (snapshot['target_frequency'], snapshot['target_amplitude'], TEAL, False),
                (snapshot['frequency'], snapshot['amplitude'], WHITE, True)]:
            points = [(x0+i, mid-amplitude*scale*math.sin(2*math.pi*frequency*i/(x1-x0)))
                      for i in range(x1-x0+1)]
            if dashed:
                for i in range(0, len(points)-1, 10):
                    draw.line(points[i:i+6], fill=color, width=1)
            else:
                draw.line(points, fill=color, width=2)
        if snapshot['matched']:
            status = 'HOLD STEADY' if snapshot['controls_centered'] else 'RELEASE TO LOCK'
        else:
            status = 'MATCH THE WAVEFORMS'
        centered(draw, 98, status, 10, TEAL if snapshot['matched'] else WHITE, True)
        draw.rectangle((8, 115, 231, 118), fill=GRID)
        progress = max(0, min(1, snapshot['match_progress']))
        if progress:
            draw.rectangle((8, 115, 8+int(223*progress), 118), fill=TEAL)
        centered(draw, 122, 'L/R frequency   U/D amplitude', 9, MUTED)
        return image

    messages = snapshot['messages']
    archive = min(snapshot.get('archive_index', len(messages)-1), len(messages)-1)
    record = messages[archive]
    text(draw, (8, 4), record['title'], 11, TEAL, True)
    text(draw, (210, 4), f"{record['signal_index']+1}/2", 10, TEAL)
    draw.line((8, 25, 231, 25), fill=GRID)
    glyph(draw, record['symbol'], 217, 43, 10)
    # Short lines keep every word visible on the real 240 x 135 display.
    if record['symbol'] == 'triangle':
        lines = ['The triangle produced', 'an odd-numbered code.']
    else:
        lines = ['The moon produced a code', 'greater than 3 and', 'less than 6.']
    for i, line in enumerate(lines):
        text(draw, (9, 34 + i*23), line, 12, WHITE)
    draw.line((8, 108, 231, 108), fill=GRID)
    footer = 'RIGHT: NEXT SIGNAL' if stage == 'recovered' else 'UP/DOWN: REVIEW A / B'
    centered(draw, 117, footer, 10, MUTED)
    return image
