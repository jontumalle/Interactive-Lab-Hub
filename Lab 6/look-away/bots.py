"""Local practice players; use real Pis to test MQTT clients and audio sync."""
import random

from game import DIRECTIONS


class Bots:
    def __init__(self, game):
        self.players = []
        for number in range(1, 4):
            if len(game.players) == 4:
                break
            player = 'bot-' + str(number)
            if player not in game.players and game.join(player):
                self.players.append(player)

    def tick(self, game, now):
        if game.phase not in ('choosing', 'waiting') or now < game.deadline:
            return
        for player in self.players:
            if player not in game.choices:
                game.choose(player, random.choice(DIRECTIONS), game.revision)
