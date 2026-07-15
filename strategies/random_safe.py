import random

from .base import Strategy


class RandomSafeStrategy(Strategy):
    def choose_move(self, game_state, safe_moves, candidates, space_scores, game_mode="standard"):
        return random.choice(safe_moves)