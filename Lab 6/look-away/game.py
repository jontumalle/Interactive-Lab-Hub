"""Authoritative, hardware-independent game rules."""
DIRECTIONS = ('up', 'down', 'left', 'right')
REVEAL_SECONDS = 6
LOOK_SECONDS = .4
KNOCKOUT_DELAY = 1.4


class Game:
    def __init__(self, host):
        self.host = host
        self.players = [host]
        self.solo = host
        self.round = 0
        self.phase = 'lobby'
        self.alive = []
        self.choices = {}
        self.winner = None
        self.revision = 0
        self.deadline = 0
        self.eliminated = []

    def join(self, player):
        if player in self.players:
            return True
        if self.phase != 'lobby' or len(self.players) == 4:
            return False
        self.players.append(player)
        return True

    def start(self, now):
        if len(self.players) != 4 or self.phase not in ('lobby', 'finished'):
            return False
        if self.phase == 'finished':
            self.solo = self.players[(self.players.index(self.solo) + 1) % 4]
        self.alive = [p for p in self.players if p != self.solo]
        self.winner = None
        self.round = 0
        self.next_round(now)
        return True

    def next_round(self, now):
        self.winner = None
        self.round += 1
        self.revision += 1
        self.choices = {}
        self.eliminated = []
        self.phase = 'choosing'
        self.deadline = now + 5  # two-second preparation, three countdown beats

    def choose(self, player, direction, revision):
        if (self.phase not in ('choosing', 'waiting') or revision != self.revision
                or player not in [self.solo] + self.alive or direction not in DIRECTIONS):
            return
        self.choices.setdefault(player, direction)

    def tick(self, now):
        if self.phase == 'choosing' and now >= self.deadline:
            self.phase = 'waiting'
        if self.phase == 'waiting' and all(p in self.choices for p in [self.solo] + self.alive):
            self.eliminated = [p for p in self.alive if self.choices[p] == self.choices[self.solo]]
            self.alive = [p for p in self.alive if p not in self.eliminated]
            self.winner = 'solo' if not self.alive else ('team' if self.round == 5 else None)
            self.phase = 'reveal'
            self.deadline = now + 2  # publish result before synchronized reveal
        elif self.phase == 'reveal' and now >= self.deadline + REVEAL_SECONDS:
            if self.winner:
                self.phase = 'finished'
            else:
                self.next_round(now)

    def snapshot(self):
        return {k: v for k, v in vars(self).items() if k != 'choices'} | {
            'submitted': list(self.choices),
            'choices': self.choices if self.phase in ('reveal', 'finished') else {}}
