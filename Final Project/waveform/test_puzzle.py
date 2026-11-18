"""Meaningful state-machine checks; no GPIO or I2C hardware is accessed."""
import math
import unittest
from puzzle import ReceiverPuzzle, SIGNALS


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.puzzle=ReceiverPuzzle()

    def target(self):
        sig=SIGNALS[self.puzzle.signal_index]
        self.puzzle.frequency=sig['frequency']
        self.puzzle.amplitude=sig['amplitude']

    def dwell(self,seconds=1.1):
        for _ in range(round(seconds/.02)):
            self.puzzle.update(.02)

    def first(self):
        self.target();self.dwell()
        self.assertEqual(self.puzzle.stage,'recovered')

    def next(self):
        self.puzzle.update(.02)
        self.puzzle.update(.02,x=1)
        self.assertEqual(self.puzzle.signal_index,1)
        self.assertEqual(self.puzzle.stage,'tuning')

    def finish(self):
        self.first();self.next();self.target();self.dwell()
        self.assertEqual(self.puzzle.stage,'complete')

    def test_axes_time_based_and_center_retains_values(self):
        initial=(self.puzzle.frequency,self.puzzle.amplitude)
        self.puzzle.update(.1,x=1,y=1)
        self.assertGreater(self.puzzle.frequency,initial[0])
        self.assertGreater(self.puzzle.amplitude,initial[1])
        position=(self.puzzle.frequency,self.puzzle.amplitude)
        self.puzzle.update(.1,x=.1,y=-.1)
        self.assertEqual(position,(self.puzzle.frequency,self.puzzle.amplitude))
        other=ReceiverPuzzle()
        for _ in range(10):other.update(.01,x=1,y=1)
        self.assertAlmostEqual(position[0],other.frequency)
        self.assertAlmostEqual(position[1],other.amplitude)

    def test_bounds_and_nonfinite_input(self):
        for _ in range(100):self.puzzle.update(.1,x=50,y=50)
        self.assertEqual((6,.85),(self.puzzle.frequency,self.puzzle.amplitude))
        for _ in range(100):self.puzzle.update(.1,x=-1,y=-1)
        self.assertEqual((1,.15),(self.puzzle.frequency,self.puzzle.amplitude))
        self.puzzle.update(float('nan'),x=float('inf'),y='bad')
        self.assertTrue(math.isfinite(self.puzzle.frequency))
        self.assertEqual(self.puzzle.stage,'tuning')

    def test_off_target_dwell_and_long_dt_do_not_acquire(self):
        self.dwell(3)
        self.assertEqual(self.puzzle.stage,'tuning')
        self.target()
        self.puzzle.update(60)
        self.assertLess(self.puzzle.snapshot()['match_progress'],1)
        self.assertEqual(self.puzzle.stage,'tuning')

    def test_stability_is_continuous_and_must_be_centered(self):
        self.target();self.dwell(.6)
        self.assertGreater(self.puzzle.snapshot()['match_progress'],.5)
        self.puzzle.update(.02,x=.3)
        self.assertEqual(self.puzzle.match_time,0)
        self.target();self.dwell(.6)
        self.assertEqual(self.puzzle.stage,'tuning')
        self.puzzle.frequency+=1
        self.puzzle.update(.02)
        self.assertEqual(self.puzzle.match_time,0)
        self.target();self.dwell()
        self.assertEqual(self.puzzle.stage,'recovered')

    def test_first_fragment_waits_for_neutral_then_new_right(self):
        self.target();self.dwell(1.0)
        self.puzzle.update(.02,x=1)
        self.assertEqual(self.puzzle.stage,'recovered')
        self.next()
        for _ in range(10):self.puzzle.update(.02,x=1)
        self.assertEqual(self.puzzle.stage,'tuning')
        self.assertEqual(self.puzzle.signal_index,1)
        self.assertEqual(len(self.puzzle.messages),1)

    def test_held_press_does_not_advance_on_capture(self):
        self.target()
        for _ in range(60):self.puzzle.update(.02,press=True)
        self.assertEqual(self.puzzle.stage,'recovered')
        self.puzzle.update(.02,press=True)
        self.assertEqual(self.puzzle.stage,'recovered')
        self.puzzle.update(.02)
        self.puzzle.update(.02,press=True)
        self.assertEqual(self.puzzle.stage,'tuning')
        self.assertEqual(self.puzzle.signal_index,1)

    def test_second_signal_completion_and_archive(self):
        self.finish()
        state=self.puzzle.snapshot()
        self.assertEqual(len(state['messages']),2)
        self.assertEqual(state['archive_index'],1)
        self.assertEqual(state['messages'][1]['symbol'],'moon')
        self.assertEqual(state['messages'][1]['text'],'The moon produced a code greater than 3 and less than 6.')
        self.puzzle.update(.02)
        self.puzzle.update(.02,y=1)
        self.assertEqual(self.puzzle.archive_index,0)
        self.puzzle.update(.02,y=1)
        self.assertEqual(self.puzzle.archive_index,0)
        self.puzzle.update(.02)
        self.puzzle.update(.02,y=-1)
        self.assertEqual(self.puzzle.archive_index,1)
        for _ in range(50):self.puzzle.update(.02,x=1)
        self.assertEqual(self.puzzle.stage,'complete')
        self.assertEqual(len(self.puzzle.messages),2)

    def test_receiver_only_reveals_diagnostic_records(self):
        self.finish()
        first, second = self.puzzle.snapshot()['messages']
        self.assertEqual(first['text'], 'The triangle produced an odd-numbered code.')
        self.assertEqual([first['title'], second['title']], ['TEST RECORD A', 'TEST RECORD B'])
        for record in (first, second):
            self.assertEqual(record['type'], 'diagnostic')
            self.assertNotIn('rows', record)
            for hidden in ('VOICE', 'BEACON', 'SENSOR', 'DISTRESS', 'Triangle at 3'):
                self.assertNotIn(hidden, str(record))

    def test_reset_and_snapshot_do_not_leak_mutable_state(self):
        self.finish()
        snap=self.puzzle.snapshot()
        snap['messages'][0]['symbol']='moon'
        self.assertEqual(self.puzzle.messages[0]['symbol'],'triangle')
        self.puzzle.reset()
        self.assertEqual(self.puzzle.stage,'tuning')
        self.assertEqual(self.puzzle.messages,[])
        self.assertEqual(self.puzzle.signal_index,0)
        self.assertEqual((self.puzzle.frequency,self.puzzle.amplitude),self.puzzle.START_SETTINGS[0])

    def test_render_all_states_is_actual_display_size(self):
        from display import render
        states=[self.puzzle.snapshot()]
        self.target();self.dwell(.5);states.append(self.puzzle.snapshot())
        self.dwell(.6);states.append(self.puzzle.snapshot())
        self.next();self.target();self.dwell();states.append(self.puzzle.snapshot())
        self.puzzle.update(.02);self.puzzle.update(.02,y=1);states.append(self.puzzle.snapshot())
        for state in states:
            frame=render(state)
            self.assertEqual(frame.size,(240,135))
            self.assertEqual(frame.mode,'RGB')


if __name__=='__main__':
    unittest.main()
