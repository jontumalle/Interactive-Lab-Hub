"""Local practice players; use real Pis to test MQTT clients and audio sync."""
import random

from game import DIRECTIONS


class Bots:
    def __init__(self, game):
        self.players = ['bot-1', 'bot-2', 'bot-3']
        for player in self.players:
            game.join(player)

    def tick(self, game, now):
        if game.phase not in ('choosing', 'waiting') or now < game.deadline:
            return
        for player in self.players:
            if player not in game.choices:
                game.choose(player, random.choice(DIRECTIONS), game.revision)
