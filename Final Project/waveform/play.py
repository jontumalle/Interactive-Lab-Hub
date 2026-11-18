#!/usr/bin/env python3
"""Run the physical receiver: python play.py [--calibrate]."""
import argparse
import time
from puzzle import ReceiverPuzzle
from display import render


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibrate',action='store_true',help='learn physical right/up joystick directions')
    args=parser.parse_args()
    from hardware import PiHardware
    print('Leave the joystick centered during startup. Ctrl+C exits.',flush=True)
    hw=None
    try:
        hw=PiHardware(ignore_calibration=args.calibrate)
        if args.calibrate:
            hw.calibrate()
            return
        puzzle=ReceiverPuzzle()
        previous=time.monotonic()
        next_frame=previous
        while True:
            now=time.monotonic()
            x,y,press=hw.read()
            puzzle.update(now-previous,x,y,press)
            previous=now
            if now>=next_frame:
                hw.show(render(puzzle.snapshot()))
                next_frame=now+1/12
            time.sleep(.015)
    except KeyboardInterrupt:
        print('\nReceiver stopped.')
    finally:
        if hw is not None:
            hw.close()


if __name__=='__main__':
    main()
