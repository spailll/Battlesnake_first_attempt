import random
from .base import Strategy


class FoodSeekerStrategy(Strategy):
    def choose_move(self, game_state, safe_moves, candidates):
        my_head = game_state["you"]["body"][0]
        food = game_state["board"]["food"]

        if not food:
            return random.choice(safe_moves)

        def dist(coord, target):
            return abs(coord["x"] - target["x"]) + abs(coord["y"] - target["y"])

        nearest = min(food, key=lambda f: dist(my_head, f))
        current_dist = dist(my_head, nearest)

        preferred = [
            d for d in safe_moves
            if dist(candidates[d], nearest) < current_dist
        ]

        return random.choice(preferred) if preferred else random.choice(safe_moves)