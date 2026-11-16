import unittest
from game import Game, KNOCKOUT_DELAY
from visuals import game_frame


class RevealAnimation(unittest.TestCase):
    def test_ready_hides_directions_then_moves_then_knocks_out(self):
        g = Game('a')
        for p in 'bcd':
            g.join(p)
        g.start(0)
        for p, direction in zip('abcd', ['left', 'left', 'up', 'right']):
            g.choose(p, direction, g.revision)
        g.tick(5)
        state = g.snapshot()
        def frame(clock):
            return game_frame(state, 'b', 'left', True, '6278', clock, 0).tobytes()
        ready = frame(g.deadline - 1)
        saved = dict(state['choices'])
        state['choices'] = dict.fromkeys(saved, 'down')
        self.assertEqual(ready, frame(g.deadline - 1))
        state['choices'] = saved
        looking = frame(g.deadline + .5)
        self.assertNotEqual(ready, looking)
        self.assertEqual(looking, frame(g.deadline + KNOCKOUT_DELAY - .01))
        self.assertNotEqual(looking, frame(g.deadline + KNOCKOUT_DELAY))
