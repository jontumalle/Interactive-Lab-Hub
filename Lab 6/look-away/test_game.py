import unittest
from game import Game, REVEAL_SECONDS


class Rules(unittest.TestCase):
    def game(self):
        g = Game('a')
        for p in 'bcd':
            self.assertTrue(g.join(p))
        self.assertFalse(g.join('e'))
        self.assertTrue(g.start(0))
        return g

    def resolve(self, g, choices):
        for p, d in zip('abcd', choices):
            g.choose(p, d, g.revision)
        g.tick(g.deadline)

    def test_early_win_and_rotation(self):
        g = self.game()
        self.resolve(g, ['up'] * 4)
        self.assertEqual(g.winner, 'solo')
        self.assertEqual(g.alive, [])
        g.tick(g.deadline + REVEAL_SECONDS)
        self.assertTrue(g.start(20))
        self.assertEqual(g.solo, 'b')
        self.assertEqual(len(g.alive), 3)

    def test_five_round_team_win(self):
        g = self.game()
        for _ in range(5):
            self.resolve(g, ['up', 'down', 'left', 'right'])
            g.tick(g.deadline + REVEAL_SECONDS)
        self.assertEqual(g.round, 5)
        self.assertEqual(g.winner, 'team')
        self.assertEqual(g.phase, 'finished')

    def test_missing_stale_duplicate_and_private(self):
        g = self.game()
        g.choose('a', 'up', g.revision - 1)
        g.choose('intruder', 'up', g.revision)
        self.assertEqual(g.choices, {})
        g.choose('a', 'up', g.revision)
        g.choose('a', 'down', g.revision)
        self.assertEqual(g.choices['a'], 'up')
        self.assertEqual(g.snapshot()['choices'], {})
        g.tick(6)
        self.assertEqual(g.phase, 'waiting')
        for p in 'bcd':
            g.choose(p, 'left', g.revision)
        g.tick(7)
        self.assertEqual(g.phase, 'reveal')

    def test_reveal_holds_all_choices_for_spectators(self):
        g = self.game()
        self.resolve(g, ['up', 'up', 'left', 'right'])
        self.assertEqual(g.snapshot()['choices'], dict(zip('abcd', ['up', 'up', 'left', 'right'])))
        self.assertNotIn('b', g.alive)
        g.tick(g.deadline + REVEAL_SECONDS - .1)
        self.assertEqual(g.phase, 'reveal')
        g.tick(g.deadline + REVEAL_SECONDS)
        self.assertEqual(g.phase, 'choosing')
        self.assertEqual(g.round, 2)
        self.assertEqual(g.snapshot()['choices'], {})

    def test_need_four(self):
        self.assertFalse(Game('a').start(0))


if __name__ == '__main__':
    unittest.main()
