"""Generate editable SVG diagrams for the Markdown design document.

Run with Python 3 standard library. Hardware is not driven.
The Markdown document is edited directly and is never overwritten by this script.
"""
from pathlib import Path
import html, math, json, itertools

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'design-assets'
ASSETS.mkdir(exist_ok=True)
BLUE, TEAL, INK, GRAY = '#255878', '#117c76', '#182a37', '#667783'

class SVG:
    def __init__(self, title, h=620):
        self.h=h
        self.items=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{h}" viewBox="0 0 1200 {h}" role="img"><title>{html.escape(title)}</title>', '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#667783"/></marker></defs>', f'<rect width="1200" height="{h}" fill="white"/>']
    def rect(self,x,y,w,h,fill='#f1f5f7',stroke='#b9c8cf',r=10):
        self.items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    def text(self,x,y,lines,size=22,color=INK,anchor='start',bold=False):
        if isinstance(lines,str): lines=lines.split('\n')
        for i,line in enumerate(lines):
            self.items.append(f'<text x="{x}" y="{y+i*(size*1.35)}" font-family="Arial, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}" text-anchor="{anchor}">{html.escape(str(line))}</text>')
    def line(self,x1,y1,x2,y2,color=GRAY,arrow=False,width=3):
        self.items.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"'+(' marker-end="url(#arrow)"' if arrow else '')+'/>')
    def circle(self,x,y,r,fill='white',stroke=BLUE,width=3):
        self.items.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')
    def path(self,d,color=BLUE,width=3):
        self.items.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"/>')
    def save(self,name):
        out=ASSETS/(name+'.svg'); out.write_text('\n'.join(self.items+['</svg>']))
        return name

s=SVG('Player journey and information dependencies',480)
for x,n,t,sub in [(30,'01','RECOVER','Joystick waveform matching'),(430,'02','DECODE','Encoder mounted symbol wheel'),(830,'03','RECONNECT','Four physical patch cables')]:
    s.rect(x,40,340,125);s.text(x+20,75,n,22,TEAL,bold=True);s.text(x+20,113,t,29,bold=True);s.text(x+20,145,sub,19)
for x in [370,770]: s.line(x+4,102,x+52,102,arrow=True)
s.text(30,220,['Recovered records','Triangle odd / Moon range'],23,bold=True)
s.text(430,220,['Correct wheel setting','Unlock and decode dispatch'],23,bold=True)
s.text(830,220,['Decoded requirements','Allocate four compatible ports'],22,bold=True)
s.text(30,340,['Receiver supplies diagnostic records; correct wheel confirmation unlocks encrypted dispatch.','Successful patching reveals the final message. Audio always has an equivalent text version.'],23)
flow=s.save('01-player-journey')

s=SVG('Proposed briefcase layout and service layer',650)
s.rect(35,20,1130,590,'#faf9f5','#56656b',25)
s.rect(70,55,1060,145,'#edf3f5');s.text(90,86,'LID OR REAR OF BASE',18,GRAY,bold=True)
s.rect(95,103,280,70,'white');s.text(235,145,'Shared Mini PiTFT',23,anchor='middle',bold=True)
s.text(415,125,['Attribute legend + locked dispatch cards','Lid mounting requires a restrained hinge cable loop.'],23)
for x,w,title in [(70,250,'1  RECEIVER'),(345,410,'2  DECODER'),(780,350,'3  PATCH PANEL')]:
    s.rect(x,225,w,255,'white');s.text(x+18,261,title,22,bold=True)
s.circle(195,345,38);s.text(195,410,'Joystick',22,anchor='middle');s.text(195,446,'Frequency / amplitude',17,anchor='middle')
s.circle(545,360,86);s.circle(545,360,58,'#eff7f5',TEAL);s.text(545,367,'Wheel',22,anchor='middle');s.text(545,466,'Encoder + hub below panel',18,anchor='middle')
s.circle(705,340,17,'#e1eeea',TEAL);s.text(705,382,'Confirm',16,anchor='middle')
for i in range(4):
    y=295+i*43;s.circle(830,y,9);s.circle(1070,y,9);s.line(845,y,1055,y,color='#b1bfc5');s.text(855,y+7,['Voice','Beacon','Sensor','Distress'][i],17)
s.text(955,466,'8 sockets + 4 cables',18,anchor='middle')
s.rect(70,505,1060,70,'#edf5f2');s.text(95,535,'SERVICE SPACE UNDER REMOVABLE PANEL',18,TEAL,bold=True)
s.text(95,562,'Pi + cooling clearance | expander | secured harness | USB power and audio',21)
s.text(600,632,'Conceptual layout only; measure the case and all parts before producing cut files.',19,GRAY,anchor='middle')
layout=s.save('02-briefcase-layout')

s=SVG('Waveform matching display and joystick controls',620)
s.rect(25,35,745,350,'#f5f8fa');s.text(50,73,'RECOVER SIGNAL 1 OF 2',23,bold=True)
s.line(55,210,735,210,color='#ccd5da')
for freq,amp,color in [(3,80,TEAL),(4.5,48,BLUE)]:
    pts=[]
    for i in range(601):
        x=60+i*1.1;y=210-amp*math.sin(2*math.pi*freq*i/600)
        pts.append(('M' if i==0 else 'L')+f'{x:.1f},{y:.1f}')
    s.path(' '.join(pts),color,4)
    if color==BLUE: s.items[-1]=s.items[-1].replace('fill="none"','fill="none" stroke-dasharray="10 6"')
s.text(55,335,'Target',21,TEAL,bold=True);s.text(185,335,'Player',21,BLUE,bold=True)
s.circle(960,220,53);s.line(850,220,1065,220,arrow=True);s.line(960,115,960,322,arrow=True)
s.text(960,85,'JOYSTICK',24,anchor='middle',bold=True);s.text(960,360,'Left / right = frequency',22,anchor='middle');s.text(960,390,'Up / down = amplitude',22,anchor='middle')
for x,title,body in [(30,'ADJUST','Deflection changes the setting'),(430,'MATCH','Center joystick; hold 1 second'),(830,'ACQUIRE','Release to recover the record')]:
    s.rect(x,450,340,100);s.text(x+15,483,title,23,bold=True);s.text(x+15,520,body,17)
s.text(30,592,'Diagnostic records remain available while players work out the decoder setting.',21)
wave=s.save('03-waveform-interaction')

s=SVG('Decoder front face and mechanical assembly',660)
cx,cy=260,265
s.circle(cx,cy,185,'#f5f0e5','#796c50');s.circle(cx,cy,140,'white',BLUE);s.circle(cx,cy,14,'#d6e4eb')
symbols=['TRI','MOON','STAR','SQUARE','SUN','WAVE','CROSS','HEX']
for i in range(8):
    a=2*math.pi*i/8-math.pi/2
    s.text(cx+164*math.cos(a),cy+164*math.sin(a)+8,str(i+1),23,anchor='middle',bold=True)
    s.text(cx+108*math.cos(a),cy+108*math.sin(a)+6,symbols[i],17,anchor='middle')
s.text(260,43,'FRONT AT HOME POSITION',22,anchor='middle',bold=True)
s.text(260,495,['Fixed numbered ring','Rotating symbol disk on encoder shaft'],21,anchor='middle')
s.text(825,43,'ASSEMBLY SECTION',22,anchor='middle',bold=True)
s.rect(600,120,430,22,'#e5d6ba');s.text(1050,140,'Disk',20)
s.rect(790,153,50,40,'#cbd9e1');s.text(860,183,'Secure hub',21)
s.rect(600,230,430,24,'#e5d6ba');s.text(1050,250,'Panel',20)
s.line(815,142,815,310,color=INK,width=8)
s.rect(740,310,150,60,'#d8e9df');s.text(815,348,'Encoder PCB',18,anchor='middle')
for x in [710,920]: s.line(x,254,x,400,color=GRAY,width=8)
s.rect(650,400,330,18,'#dae2e6');s.text(825,454,'Bracket and standoffs',21,anchor='middle')
s.text(590,515,['Provide a rotating clearance gap.','Bracket height depends on shaft length.','Keep PCB and hub accessible for repair.'],21)
s.text(30,617,'Illustration is not a cut template. Match symbol sectors to measured encoder positions.',21,GRAY)
wheel=s.save('04-decoder-construction')

s=SVG('Solved patch panel showing physical cable connections',630)
s.text(70,50,'SIGNAL SOURCES',24,bold=True);s.text(960,50,'TRANSMITTER PORTS',24,anchor='middle',bold=True)
sources=['Voice','Beacon','Sensor','Distress']; ports=['1  Long / delay 3 / encrypted','2  Short / delay 1 / plain','3  Long / delay 2 / plain','4  Short / delay 2 / encrypted']
ys=[120,240,360,480]; mapping=[1,2,3,0]; colors=[BLUE,TEAL,'#9b6d2e','#8c537d']
for i,y in enumerate(ys):
    s.text(60,y+8,sources[i],24,bold=True);s.circle(245,y,16);s.circle(825,y,16);s.text(865,y+7,ports[i],18)
for i,j in enumerate(mapping):
    y1,y2=ys[i],ys[j];s.path(f'M261,{y1} C420,{y1} 660,{y2} 809,{y2}',colors[i],6)
s.rect(360,535,400,55,'#edf5f2');s.text(560,570,'CONFIRM / TRANSMIT',23,anchor='middle',bold=True)
s.text(30,620,'Builder solution shown. Player panel has no preprinted solution cables or matching color hints.',19,GRAY)
patch=s.save('05-patch-panel')

s=SVG('High level shared peripheral bus through the Mini PiTFT',650)
s.rect(440,30,320,95,'#edf3f5');s.text(600,68,'RASPBERRY PI',27,anchor='middle',bold=True);s.text(600,102,'Game logic and progression',20,anchor='middle')
s.rect(35,35,270,80);s.text(170,83,'Existing power supply',22,anchor='middle');s.line(305,75,440,75,arrow=True)
s.rect(880,35,275,80);s.text(1017,83,'Existing audio setup',22,anchor='middle');s.line(760,75,880,75,arrow=True)
s.line(600,125,600,180)
s.rect(405,180,390,100,'#edf5f2');s.text(600,219,'MINI PiTFT',27,anchor='middle',bold=True);s.text(600,254,'Display + Qwiic / STEMMA QT port',20,anchor='middle')
s.line(600,280,600,300);s.line(600,340,600,350);s.line(160,350,1060,350,color=TEAL,width=5);s.text(600,330,'SHARED PERIPHERAL BUS',23,TEAL,anchor='middle',bold=True)
for x,title,sub in [(35,'Joystick','Waveform controls'),(335,'Encoder','Wheel rotation'),(635,'Confirm button','Contextual actions'),(935,'Patch interface','Cable connections')]:
    s.line(x+125,350,x+125,405);s.rect(x,405,250,110);s.text(x+125,448,title,24,anchor='middle',bold=True);s.text(x+125,485,sub,19,anchor='middle')
s.text(30,575,['Connect compatible peripherals using a bus chain or hub.','Final interface selection and connection details will be tested during prototyping.'],23)
bus=s.save('06-system-wiring')

s=SVG('High level patch panel connection detection',560)
s.text(30,45,'PHYSICAL ACTION TO GAME FEEDBACK',24,bold=True)
for x,title,lines in [(30,'CONNECT',['Four patch cables','Eight mounted sockets']),(430,'DETECT',['Interface reports','source to port mapping']),(830,'CHECK',['Pi evaluates the','complete arrangement'])]:
    s.rect(x,100,340,145);s.text(x+20,143,title,25,bold=True);s.text(x+20,188,lines,22)
for x in [370,770]: s.line(x+4,172,x+52,172,arrow=True)
s.line(1000,245,1000,320);s.line(1000,320,600,320);s.line(600,320,600,365,arrow=True)
s.rect(380,365,440,100,'#edf5f2');s.text(600,404,'DISPLAY RESULT',24,anchor='middle',bold=True);s.text(600,441,'Revise connections or reveal final message',20,anchor='middle')
s.text(30,525,'Interface and sensing circuit will be selected and verified during the build.',23)
scan=s.save('07-patch-scanner')

# Validate the logic examples and ensure no unreachable target orientations.
ports={1:('long',3,True),2:('short',1,False),3:('long',2,False),4:('short',2,True)}
solutions=[]
for v,bn,se,di in itertools.permutations(ports):
    if ports[v][1]==1 and ports[bn][0]=='long' and ports[se][0]=='short' and ports[di][0]=='long' and ports[di][2]:
        solutions.append((v,bn,se,di))
assert solutions==[(2,3,4,1)], solutions
# Each diagnostic clue is incomplete; together they identify exactly one orientation.
triangle_odd = [offset for offset in range(8) if (offset % 8 + 1) % 2 == 1]
moon_range = [offset for offset in range(8) if 3 < ((offset + 1) % 8 + 1) < 6]
diagnostic_solutions = sorted(set(triangle_odd) & set(moon_range))
assert len(triangle_odd) == 4 and len(moon_range) == 2
assert diagnostic_solutions == [2], diagnostic_solutions
assert diagnostic_solutions[0] * 45 == 90
assert [((symbols.index(sym)+2)%8)+1 for sym in ['TRI','CROSS','HEX','MOON']] == [3,1,2,4]

# Check diagram references without rewriting the authoritative Markdown document.
import re
text = (ROOT/'design-document.md').read_text()
images = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text)
assert len(images) == 7
for image in images:
    assert (ROOT/image).is_file(), image
print(json.dumps({'diagrams': len(images), 'patch_solution': solutions[0], 'diagnostic_solutions': diagnostic_solutions, 'document': str(ROOT/'design-document.md')}))
