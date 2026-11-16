"""Generate the paper prototype PDFs with reportlab. Does not modify design files.

Dependencies: reportlab and pypdf. Run from any directory.
All dimensions are print dimensions, not final laser cutter specifications.
"""
from pathlib import Path
import math
import itertools
import os
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.utils import simpleSplit
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'pdf'
OUT.mkdir(parents=True, exist_ok=True)
FONT_DIR = Path(os.environ.get('PAPER_FONT_DIR', '/Users/jonathantumalle/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/truetype'))
pdfmetrics.registerFont(TTFont('PaperSans', str(FONT_DIR/'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('PaperSans-Bold', str(FONT_DIR/'DejaVuSans-Bold.ttf')))
TEAL = HexColor('#216561')
GRAY = HexColor('#58636a')
LIGHT = HexColor('#d0d7d8')
SYMBOLS = ['Triangle', 'Moon', 'Star', 'Square', 'Sun', 'Wave', 'Cross', 'Hexagon']
ATTRS = ['LONG RANGE', 'SHORT RANGE', 'LOWEST DELAY', 'ENCRYPTED', 'ANY DELAY', 'PLAIN', 'LOCAL ONLY', 'OFFLINE']
PORTS = [('1','Long','3','Yes'),('2','Short','1','No'),('3','Long','2','No'),('4','Short','2','Yes')]

def txt(c,x,y,t,size=11,bold=False,color=black,align='left'):
    c.setFillColor(color); c.setFont('PaperSans-Bold' if bold else 'PaperSans',size)
    {'left':c.drawString,'center':c.drawCentredString,'right':c.drawRightString}[align](x,y,t)

def para(c,x,y,text,width,size=11,leading=16,bold=False,color=black):
    lines=simpleSplit(text,'PaperSans-Bold' if bold else 'PaperSans',size,width)
    for line in lines:
        txt(c,x,y,line,size,bold,color); y-=leading
    return y

def page(c,title,subtitle,num,size=letter,facilitator=False):
    c.setPageSize(size);w,h=size
    txt(c,42,h-42,'THE LAST TRANSMISSION',10,True,TEAL)
    txt(c,42,h-76,title,23,True)
    para(c,42,h-99,subtitle,w-84,10,14,color=GRAY)
    txt(c,42,23,'FACILITATOR ONLY - KEEP SEPARATE' if facilitator else 'PAPER PROTOTYPE - US LETTER - PRINT SINGLE SIDED AT 100%',8,True,GRAY)
    txt(c,w-42,23,str(num),9,color=GRAY,align='right')

def cutrect(c,x,y,w,h):
    c.saveState();c.setDash(5,4);c.setStrokeColor(GRAY);c.setLineWidth(.75)
    c.rect(x,y,w,h);c.restoreState()

def center_mark(c,x,y):
    c.saveState();c.setLineWidth(.7);c.setStrokeColor(GRAY)
    c.line(x-4,y,x+4,y);c.line(x,y-4,x,y+4);c.circle(x,y,2.4,stroke=1,fill=0);c.restoreState()

def ruler(c,x,y):
    c.saveState();c.setStrokeColor(black);c.setLineWidth(.8)
    c.line(x,y,x+100*mm,y)
    for i in range(11):
        c.line(x+i*10*mm,y-3,x+i*10*mm,y+5)
    txt(c,x,y-17,'0',9);txt(c,x+100*mm,y-17,'100 mm',9,align='right')
    txt(c,x,y+18,'Print scale check',9,True);c.restoreState()

def symbol(c,name,x,y,r=15):
    c.saveState();c.setStrokeColor(black);c.setFillColor(white);c.setLineWidth(1.7)
    p=c.beginPath()
    if name=='Triangle':
        p.moveTo(x,y+r);p.lineTo(x-r*.95,y-r*.7);p.lineTo(x+r*.95,y-r*.7);p.close();c.drawPath(p,stroke=1)
    elif name=='Moon':
        # One closed crescent outline; no font dependency or white overpainting.
        p.moveTo(x+r*.40,y+r*.92)
        p.curveTo(x-r*1.15,y+r*.95,x-r*1.15,y-r*.95,x+r*.40,y-r*.92)
        p.curveTo(x-r*.35,y-r*.55,x-r*.35,y+r*.55,x+r*.40,y+r*.92)
        p.close();c.drawPath(p,stroke=1)
    elif name=='Star':
        for i in range(10):
            a=math.pi/2+i*math.pi/5;rr=r if i%2==0 else r*.43
            xx=x+rr*math.cos(a);yy=y+rr*math.sin(a)
            p.moveTo(xx,yy) if i==0 else p.lineTo(xx,yy)
        p.close();c.drawPath(p,stroke=1)
    elif name=='Square':c.rect(x-r*.78,y-r*.78,r*1.56,r*1.56)
    elif name=='Sun':
        c.circle(x,y,r*.5)
        for i in range(8):
            a=i*math.pi/4;c.line(x+r*.68*math.cos(a),y+r*.68*math.sin(a),x+r*math.cos(a),y+r*math.sin(a))
    elif name=='Wave':
        for offset in [-r*.48,0,r*.48]:
            p=c.beginPath();p.moveTo(x-r,y+offset)
            for i in range(1,41):
                xx=-r+2*r*i/40;p.lineTo(x+xx,y+offset+math.sin(i/40*math.pi*3)*r*.15)
            c.drawPath(p,stroke=1)
    elif name=='Cross':
        c.setLineWidth(3);c.line(x-r*.8,y,x+r*.8,y);c.line(x,y-r*.8,x,y+r*.8)
    elif name=='Hexagon':
        for i in range(6):
            a=i*math.pi/3;xx=x+r*math.cos(a);yy=y+r*math.sin(a)
            p.moveTo(xx,yy) if i==0 else p.lineTo(xx,yy)
        p.close();c.drawPath(p,stroke=1)
    else:raise ValueError(name)
    c.restoreState()

def table(c,x,top,width,headers,rows,colfracs,rowheight=38,fontsize=11):
    widths=[width*f for f in colfracs];total=(len(rows)+1)*rowheight
    c.setStrokeColor(LIGHT);c.setLineWidth(.7)
    c.setFillColor(HexColor('#eef2f2'));c.rect(x,top-rowheight,width,rowheight,stroke=0,fill=1)
    for k in range(len(rows)+2):c.line(x,top-k*rowheight,x+width,top-k*rowheight)
    xx=x
    for w in widths:c.line(xx,top,xx,top-total);xx+=w
    c.line(x+width,top,x+width,top-total)
    for ri,row in enumerate([headers]+list(rows)):
        xx=x
        for ci,cell in enumerate(row):
            para(c,xx+10,top-ri*rowheight-23,str(cell),widths[ci]-20,fontsize,14,bold=ri==0)
            xx+=widths[ci]
    return top-total

player=OUT/'last-transmission-player-templates.pdf'
c=canvas.Canvas(str(player),pagesize=letter)
c.setTitle('The Last Transmission Player Templates');c.setAuthor('Jonathan Tumalle')

# 1. The stationary base; rotor printed on the next sheet.
page(c,'Decoder base','Keep this numbered base intact. Attach the separate symbol disk through the center.',1)
cx,cy=306,408
c.setLineWidth(1);c.setStrokeColor(LIGHT);c.circle(cx,cy,85*mm)
c.setStrokeColor(GRAY);c.setDash(3,3);c.circle(cx,cy,63*mm);c.setDash()
for i in range(8):
    a=math.pi/2-i*math.pi/4
    txt(c,cx+77*mm*math.cos(a),cy+77*mm*math.sin(a)-8,str(i+1),25,True,align='center')
    c.setStrokeColor(LIGHT)
    c.line(cx+65*mm*math.cos(a),cy+65*mm*math.sin(a),cx+68*mm*math.cos(a),cy+68*mm*math.sin(a))
center_mark(c,cx,cy)
txt(c,cx,cy+10,'CENTER',8,color=GRAY,align='center')
para(c,62,128,'Turn the inner disk. The number opposite each symbol is its code. Use both diagnostic records to find one setting, then keep the disk still while decoding the dispatch.',488,12,17)
ruler(c,62,60)
c.showPage()

# 2. The actual cutout and assembly dimensions, not a picture of a wheel.
page(c,'Decoder symbol disk','Cut along the dashed circle. Pierce the center mark and attach over the numbered base.',2)
cx,cy=306,410;r=62*mm
c.setStrokeColor(GRAY);c.setLineWidth(.8);c.setDash(5,4);c.circle(cx,cy,r);c.setDash()
for i,name in enumerate(SYMBOLS):
    a=math.pi/2-i*math.pi/4
    # Sector dividers are halfway between the symbols, so a symbol has a clear radial axis.
    div=a-math.pi/8;c.setStrokeColor(LIGHT);c.setLineWidth(.6)
    c.line(cx+18*mm*math.cos(div),cy+18*mm*math.sin(div),cx+r*math.cos(div),cy+r*math.sin(div))
    symbol(c,name,cx+47*mm*math.cos(a),cy+47*mm*math.sin(a),15)
    txt(c,cx+34*mm*math.cos(a),cy+34*mm*math.sin(a)-3,name.upper(),7,align='center')
center_mark(c,cx,cy)
para(c,62,175,'Assembly: use a paper fastener through both center marks. Leave enough clearance for the disk to rotate. A small card washer can protect the center hole.',488,11,16)
para(c,62,124,'The fixed base is 170 mm across; the rotating disk is 124 mm across. These sizes are for the paper test only.',488,10,14,color=GRAY)
ruler(c,62,60)
c.showPage()

# 3. Separate clues: no solved alignment or test answer appears on this sheet.
page(c,'Diagnostic records','Cut the two cards apart. Their placement can be changed between playtests.',3)
for y,label,name,lines in [(425,'TEST RECORD A','Triangle',['The triangle produced an','odd-numbered code.']),
                           (175,'TEST RECORD B','Moon',['The moon produced a code','greater than 3 and less than 6.'])]:
    cutrect(c,60,y,492,210)
    txt(c,82,y+174,label,12,True,TEAL);symbol(c,name,108,y+99,22)
    for i,line in enumerate(lines):txt(c,157,y+112-i*28,line,17,True)
    txt(c,82,y+27,'Receiver maintenance archive',9,color=GRAY)
c.showPage()

# 4. Ciphertext is released in two chunks to represent two receiver captures.
page(c,'Recovered dispatch','Two encrypted fragments. Read each symbol using the decoder and attribute legend.',4)
for bottom,title,rows in [(410,'FRAGMENT A',[('VOICE',['Triangle']),('BEACON',['Cross'])]),
                          (135,'FRAGMENT B',[('SENSOR',['Hexagon']),('DISTRESS',['Cross','Moon'])])]:
    cutrect(c,60,bottom,492,230);txt(c,82,bottom+196,title,12,True,TEAL)
    for i,(name,syms) in enumerate(rows):
        y=bottom+132-i*77;txt(c,88,y-6,name,18,True)
        for j,sym in enumerate(syms):
            x=290+j*155;c.setStrokeColor(LIGHT);c.roundRect(x-27,y-27,54,54,4,stroke=1,fill=0);symbol(c,sym,x,y,18)
        if len(syms)==2:txt(c,367,y-4,'AND',10,True,align='center')
c.showPage()

# 5. Legend reveals meanings of numbers, not the substitution key.
page(c,'Attribute legend and field notes','Use the code numbers read from the wheel to interpret the recovered dispatch.',5)
cutrect(c,60,290,250,352)
txt(c,78,614,'ATTRIBUTE LEGEND',12,True,TEAL)
for i,attribute in enumerate(ATTRS):
    y=577-i*34;txt(c,80,y,str(i+1),15,True);txt(c,113,y,attribute,12)
txt(c,337,612,'DECODED REQUIREMENTS',11,True)
for i,name in enumerate(['VOICE','BEACON','SENSOR','DISTRESS']):
    y=562-i*66;txt(c,337,y,name,10,True);c.setStrokeColor(LIGHT);c.line(337,y-26,551,y-26)
para(c,60,235,'Confirm your chosen decoder setting, then leave the disk in place while reading all symbols. A dispatch may contain more than one requirement for a source.',492,12,18)
para(c,60,170,'Use your recovered requirements and the separate port specifications to plan the transmitter connections.',492,12,18)
c.showPage()

# 6. Landscape physical board: no solution cables and no color answer cues.
size=landscape(letter)
page(c,'Transmitter patch panel','Connect each source to one compatible port. Use each source and each port exactly once.',6,size)
txt(c,65,445,'SOURCES',11,True,TEAL);txt(c,565,445,'PORTS',11,True,TEAL)
for i,name in enumerate(['VOICE','BEACON','SENSOR','DISTRESS']):
    y=395-i*83;txt(c,65,y-5,name,16,True)
    for x in [255,530]:c.setStrokeColor(black);c.setLineWidth(1.5);c.circle(x,y,13)
    txt(c,570,y-6,str(i+1),22,True)
c.setStrokeColor(black);c.roundRect(327,58,142,43,7,stroke=1,fill=0);txt(c,398,73,'TRANSMIT',13,True,align='center')
txt(c,65,55,'Place string ends on the circles,',10,color=GRAY)
txt(c,65,40,'or draw connections on a spare copy.',10,color=GRAY)
txt(c,575,66,'Use the port specification sheet.',10,color=GRAY)
c.showPage()

# 7. Reference artifact kept separate from ciphertext and notes.
page(c,'Transmitter port specifications','Compare all requirements before connecting the four sources.',7)
cutrect(c,52,320,508,330)
txt(c,73,615,'TRANSMITTER PORT REGISTER',12,True,TEAL)
table(c,72,590,468,['PORT','RANGE','DELAY','ENCRYPTED'],PORTS,[.15,.28,.22,.35],rowheight=43,fontsize=12)
txt(c,73,348,'Lower delay values mean faster transmission.',11)
para(c,62,266,'Each port accepts one source. Sources may have several requirements. A connection must satisfy all of that source\'s requirements.',488,12,18)
para(c,62,192,'When your connections are ready, press Transmit and ask the facilitator to check the complete configuration.',488,12,18)
c.save()

# Facilitator guide is deliberately a separate file with spoilers.
guide=OUT/'last-transmission-facilitator-guide.pdf'
c=canvas.Canvas(str(guide),pagesize=letter)
c.setTitle('The Last Transmission Facilitator Guide');c.setAuthor('Jonathan Tumalle')
page(c,'Setup and running the test','Keep this guide out of sight. The player PDF contains no answer key.',1,facilitator=True)
y=646
for heading,text in [
('Print and gather','Print the seven player pages single sided on US Letter at Actual Size or 100%, with automatic page orientation. Page 6 is landscape. Turn off Fit to page and duplex printing. Check the 100 mm ruler. Gather scissors, a paper fastener, scrap cardboard, four pieces of string about 30 cm long, low tack tape or clips, and a pencil.'),
('Assemble the decoder','Mount page 1 on cardboard. Cut only the outer dashed circle on page 2. Pierce both center marks and attach the rotor over the base with a paper fastener and optional card washer. Keep the fixed numbers visible. Check that every symbol can align with any number. Start with Triangle at 1; that is a reset reference, not the solution.'),
('Place the artifacts','Cut out the two diagnostic cards and place them separately but visibly around the case or tabletop. Set out the decoder, attribute legend, blank notes, empty patch panel, and port register. Keep dispatch fragments A and B with you until the receiver stage is represented as complete. Do not place a solved checklist or this guide on the player table.'),
('Represent the receiver stage','This pack tests decoding, patch allocation, and their handoff. It does not test the waveform controls. Use the actual waveform prototype if available, releasing A and B after its two successful locks. Otherwise announce that the receiver recovered the dispatch and hand over both fragments. Record this stage as simulated rather than completed hardware testing.'),
('Run without teaching the solution','Opening prompt: Recover the dispatch, work out what each source needs, and restore the transmitter connections. Let players explore. When they confirm the wheel, quietly note the number beside Triangle and say Decoder set without giving correctness feedback. At Transmit check that recorded setting and the cable assignment using page 2 of this guide.')]:
    txt(c,42,y,heading,12,True);y-=21
    y=para(c,42,y,text,528,10.4,14.5)-19
c.showPage()
page(c,'Answers hints and observation log','Spoilers below. These are facilitator instructions, not player clues.',2,facilitator=True)
y=647
txt(c,42,y,'Answer key',12,True);y-=22
y=para(c,42,y,'Triangle must be odd. Moon can only be 4 or 5. Moon is one sector after Triangle, so Moon at 5 would put Triangle at 4 and fail the odd clue. The unique solution is Triangle at 3 and Moon at 4. Square consequently reaches 6, but no clue states that setting.',528,10.5,14.5)-12
table(c,42,y,528,['SOURCE','DECODED REQUIREMENT','PORT'],[
('Voice','Triangle = 3 = lowest delay','2'),('Beacon','Cross = 1 = long range','3'),('Sensor','Hexagon = 2 = short range','4'),('Distress','Cross + Moon = long and encrypted','1')],[.17,.68,.15],rowheight=29,fontsize=10)
y-=29*5+22
y=para(c,42,y,'Accept only recorded Triangle at 3 plus Voice to 2, Beacon to 3, Sensor to 4, and Distress to 1. If wrong or incomplete, say Transmission not established. Check your setting and connections. Do not identify an individual correct cable. On success reveal: The archive is secure. Delivery confirmed.',528,10.5,14.5)-17
txt(c,42,y,'Hints on request',12,True);y-=20
for t in [
    'Decoder hint 1: Both diagnostic records describe the same wheel setting.',
    'Decoder hint 2: Moon can be at 4 or 5. What number would Triangle have in each case?',
    'Patching hint 1: Satisfy every requirement and reserve a port for sources with fewer options.',
    'Patching hint 2: Which port is both long range and encrypted? Which has the lowest delay?']:
    y=para(c,42,y,t,528,10,14)-4
y-=9;txt(c,42,y,'Observe then reset',12,True);y-=20
y=para(c,42,y,'Record confusion, hints, completion time, accidental wheel movement, and how players interpret crossed patch cords. Reset by removing every cord, clearing notes and the recorded setting, returning Triangle to 1, and collecting the dispatch fragments. Keep the two diagnostic cards separate.',528,10,14)-16
for label in ['Participants and date','Time and hints','Observed problem and next change']:
    txt(c,42,y,label,9,True);c.setStrokeColor(LIGHT);c.line(205,y-2,570,y-2);y-=24
c.save()

# Validate unique logical solutions and basic PDF integrity.
diagnostic=[o for o in range(8) if (o+1)%2==1 and 3<((o+1)%8+1)<6]
assert diagnostic==[2]
mapping={SYMBOLS[i]:((i+diagnostic[0])%8)+1 for i in range(8)}
assert [mapping[s] for s in ['Triangle','Cross','Hexagon','Moon']]==[3,1,2,4]
values={1:('Long',3,True),2:('Short',1,False),3:('Long',2,False),4:('Short',2,True)}
valid=[p for p in itertools.permutations(values) if values[p[0]][1]==1 and values[p[1]][0]=='Long' and values[p[2]][0]=='Short' and values[p[3]][0]=='Long' and values[p[3]][2]]
assert valid==[(2,3,4,1)]
pr=PdfReader(player);gr=PdfReader(guide)
assert len(pr.pages)==7 and len(gr.pages)==2
for i,p in enumerate(pr.pages):
    expected=landscape(letter) if i==5 else letter
    assert abs(float(p.mediabox.width)-expected[0])<.1
    assert abs(float(p.mediabox.height)-expected[1])<.1
assert 'Triangle at 3' not in ''.join(p.extract_text() for p in pr.pages)
print(f'Created {player.name}: 7 pages; {guide.name}: 2 pages. Unique wheel and patch solutions verified.')
