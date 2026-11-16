import unittest

from bots import Bots
from game import Game


class Practice(unittest.TestCase):
    def test_bots_wait_and_submit_once(self):
        game = Game('human')
        bots = Bots(game)
        self.assertEqual(len(game.players), 4)
        game.start(0)
        bots.tick(game, 4)
        self.assertEqual(game.choices, {})
        bots.tick(game, 5)
        choices = dict(game.choices)
        self.assertEqual(set(choices), set(bots.players))
        bots.tick(game, 6)
        self.assertEqual(game.choices, choices)
        game.tick(6)
        self.assertEqual(game.phase, 'waiting')
        game.choose('human', 'up', game.revision)
        game.tick(7)
        self.assertEqual(game.phase, 'reveal')

    def test_bot_can_be_solo_on_replay(self):
        game = Game('human')
        bots = Bots(game)
        game.start(0)
        game.phase = 'finished'
        game.start(10)
        self.assertEqual(game.solo, 'bot-1')
        bots.tick(game, 15)
        self.assertIn(game.solo, game.choices)
