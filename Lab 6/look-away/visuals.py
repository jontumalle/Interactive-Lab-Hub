"""Original Pillow party-game graphics, sized for the 240 x 135 MiniPiTFT."""
import math
from PIL import Image, ImageDraw, ImageFont
from game import LOOK_SECONDS, KNOCKOUT_DELAY

INK = '#17244a'
WHITE = '#fff8e8'
YELLOW = '#ffd44d'
BLUE = '#458bfa'
PINK = '#ff7197'
GREEN = '#73e6ae'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONTS = {size: ImageFont.truetype(FONT, size) for size in (10, 12, 14, 18, 22, 28)}


def text(d, xy, label, size=12, fill=WHITE, anchor=None):
    d.text(xy, label, font=FONTS[size], fill=fill, anchor=anchor)


def base(t):
    image = Image.new('RGB', (240, 135), INK)
    d = ImageDraw.Draw(image)
    for i in range(14):
        x = (i * 47) % 240
        y = (i * 31 + int(t * 6)) % 135
        d.ellipse((x, y, x+3, y+3), fill='#30416b')
    return image, d


def face(d, x, y, radius=31, direction=None, mood='happy', color=YELLOW, t=0,
         look_progress=1, blink=True):
    d.ellipse((x-radius, y-radius+3, x+radius, y+radius+3), fill='#0c1630')
    d.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color, outline=WHITE, width=2)
    dx, dy = {'up': (0,-4), 'down': (0,4), 'left': (-4,0), 'right': (4,0)}.get(direction, (0,0))
    dx, dy = dx * look_progress, dy * look_progress
    for ex in (x-radius*.35, x+radius*.35):
        ey = y-radius*.12
        if mood == 'out':
            d.line((ex-4,ey-4,ex+4,ey+4), fill=INK, width=2)
            d.line((ex+4,ey-4,ex-4,ey+4), fill=INK, width=2)
        elif mood == 'closed' or (blink and t % 4 > 3.85):
            d.line((ex-5,ey,ex+5,ey), fill=INK, width=3)
        else:
            d.ellipse((ex-7,ey-9,ex+7,ey+9), fill=WHITE)
            d.ellipse((ex-3+dx,ey-4+dy,ex+3+dx,ey+4+dy), fill=INK)
    if mood == 'out':
        d.ellipse((x-5,y+10,x+5,y+19), fill=INK)
    else:
        d.arc((x-11,y+2,x+11,y+19), 0, 180, fill=INK, width=2)


def footer(d, label):
    d.rectangle((0,116,240,135), fill='#0c1630')
    text(d,(120,125),label,10,anchor='mm')


def menu(lines, t):
    image, d = base(t)
    if lines[0] == 'LOOK AWAY' and any('> ' in line for line in lines):
        text(d,(120,20),'LOOK AWAY!',22,YELLOW,'mm')
        text(d,(120,40),'ONE VS THREE',10,WHITE,'mm')
        for i, label in enumerate(('HOST', 'JOIN')):
            x = 10+i*116
            selected = lines[i+1].startswith('>')
            y = 56 - (2 if selected and int(t*3)%2 else 0)
            d.rounded_rectangle((x,y,x+104,y+46),radius=10,fill=BLUE if i==0 else PINK,
                                outline=YELLOW if selected else INK,width=3)
            text(d,(x+52,y+23),label,18,INK,'mm')
        footer(d,'UP / DOWN TO PICK  -  CLICK TO GO')
    elif lines[0] == 'JOIN ROOM':
        text(d,(120,16),'JOIN THE PARTY',18,YELLOW,'mm')
        cursor = lines[2].index('^')
        for i, digit in enumerate(lines[1]):
            x=35+i*44
            d.rounded_rectangle((x,38,x+36,79),radius=6,fill=BLUE if i==cursor else '#30416b',
                                outline=YELLOW if i==cursor else WHITE,width=2)
            text(d,(x+18,58),digit,28,WHITE,'mm')
        # Same cell centers for digit and caret; never rely on space widths.
        text(d,(53+cursor*44,91),'^',18,YELLOW,'mm')
        text(d,(120,106),'UP/DOWN: DIGIT   LEFT/RIGHT: MOVE',10,WHITE,'mm')
        footer(d,'CLICK TO JOIN')
    else:
        text(d,(120,18),lines[0][:25],14,YELLOW,'mm')
        for i, line in enumerate(lines[1:5]):
            text(d,(120,45+i*19),line[:30],12,WHITE,'mm')
    return image


def game_frame(state, player, selected, submitted, room, clock, t):
    image, d = base(t)
    phase = state['phase']
    solo = player == state['solo']
    reveal = phase in ('reveal','finished') and clock >= state['deadline']
    outcome_visible = phase == 'finished' or (phase == 'reveal' and clock >= state['deadline'] + KNOCKOUT_DELAY)
    alive = player in state['alive'] or (not outcome_visible and player in state['eliminated'])
    active = solo or alive
    color = YELLOW if solo else GREEN
    if phase == 'lobby':
        text(d,(120,16),'ROOM '+room,22,YELLOW,'mm')
        for i in range(4):
            occupied = i < len(state['players'])
            face(d,34+i*57,65,21,color=YELLOW if i==0 else GREEN if occupied else '#536081',
                 mood='happy' if occupied else 'closed',t=t)
        text(d,(120,100),str(len(state['players']))+' / 4 READY',12,WHITE,'mm')
        footer(d,'HOST: CLICK TO START')
        return image
    d.rounded_rectangle((5,4,68,23),radius=6,fill=color)
    text(d,(36,14),'SOLO' if solo else 'TEAM' if alive else 'OUT',10,INK,'mm')
    text(d,(117,14),'ROUND '+str(state['round'])+'/5',10,WHITE,'mm')
    remaining = len(state['alive']) + (len(state['eliminated']) if not outcome_visible else 0)
    for i in range(3):
        d.ellipse((183+i*18,9,193+i*18,19),fill=GREEN if i<remaining else '#536081')
    if phase == 'reveal':
        # Every station, including spectators, sees the same four-seat board.
        # Keep player numbers stable even as the solo role rotates on replay.
        for i, seat in enumerate(state['players']):
            x = 32 + i * 58
            is_solo = seat == state['solo']
            direction = state['choices'].get(seat)
            was_out = direction is None
            elapsed = clock - state['deadline']
            progress = max(0, min(1, elapsed / LOOK_SECONDS))
            progress = progress * progress * (3 - 2 * progress)
            knocked_out = elapsed >= KNOCKOUT_DELAY and seat in state['eliminated']
            label = 'P' + str(i + 1) + (' SOLO' if is_solo else '')
            text(d,(x,36),label,10,YELLOW if is_solo else WHITE,'mm')
            if seat == player:
                d.rounded_rectangle((x-25,44,x+25,94),radius=9,outline=WHITE,width=2)
            face(d,x,69,20,direction=direction,
                 mood='out' if was_out or knocked_out else 'happy',
                 color=YELLOW if is_solo else GREEN if not was_out else '#536081',t=t,
                 look_progress=progress, blink=False)
            answer = 'OUT' if was_out else direction.upper() if reveal else 'READY'
            text(d,(x,102),answer,10,WHITE,'mm')
        footer(d,'READY... EYES FRONT!' if not reveal else
               'PICKS REVEALED!  MATCH = OUT')
        return image
    if phase == 'finished' and state['winner']:
        won = (state['winner']=='solo') == solo
        if won:
            for i in range(24):
                x=(i*43)%240; y=(i*23+int(t*40))%116
                d.rectangle((x,y,x+3,y+5),fill=(PINK,YELLOW,GREEN,BLUE)[i%4])
        text(d,(120,39),'YOU WIN!' if won else 'YOU LOSE',22,YELLOW if won else PINK,'mm')
        text(d,(120,59),state['winner'].upper()+' WINS',10,WHITE,'mm')
        face(d,120,88+(int(math.sin(t*6)*3) if won else 0),21,
             mood='happy' if won else 'out',color=color if won else '#8792aa',t=t,
             blink=won)
        footer(d,'HOST: CLICK FOR REMATCH' if phase=='finished' else 'WHAT A ROUND!')
        return image
    closed = phase == 'reveal' and not reveal
    face(d,91,69+int(math.sin(t*4)*2),34,direction=selected,
         mood='closed' if closed else 'happy' if active else 'out',color=color,t=t)
    if phase in ('choosing','waiting'):
        count=max(0,math.ceil(state['deadline']-clock))
        text(d,(188,59),str(count) if count else 'OK' if submitted else '?',28,YELLOW,'mm')
        text(d,(188,86),(selected or 'PICK!').upper() if active else 'WATCH',10,WHITE,'mm')
        footer(d,'SPECTATING' if not active else 'CHOICE LOCKED!' if submitted else
               'PICK A DIRECTION!' if phase=='waiting' else 'MOVE YOUR JOYSTICK!')
    elif closed:
        text(d,(184,65),'READY?',12,YELLOW,'mm')
        footer(d,'THE BIG REVEAL...')
    else:
        direction=state['choices'].get(state['solo'],'?').upper()
        text(d,(184,48),'SOLO',10,YELLOW,'mm')
        text(d,(184,71),direction,14,WHITE,'mm')
        footer(d,'YOU ARE OUT!' if not active else 'GOT THEM!' if solo and state['eliminated'] else
               'MISSED!' if solo else 'SAFE!')
    return image
