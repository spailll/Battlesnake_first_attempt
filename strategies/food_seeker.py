import random

from .base import Strategy


class FoodSeekerStrategy(Strategy):
    def choose_move(self, game_state, safe_moves, candidates, space_scores, game_mode="standard"):
        my_head = game_state["you"]["body"][0]
        food = game_state["board"]["food"]

        if not food:
            return self._pick_most_open(safe_moves, space_scores)

        def dist(coord, target):
            return abs(coord["x"] - target["x"]) + abs(coord["y"] - target["y"])

        nearest = min(food, key=lambda f: dist(my_head, f))
        current_dist = dist(my_head, nearest)

        preferred = [
            d for d in safe_moves
            if dist(candidates[d], nearest) < current_dist
        ]

        if not preferred:
            return self._pick_most_open(safe_moves, space_scores)

        # Among moves that get us closer to food, tie-break toward
        # whichever leaves the most open space, rather than pure random.
        return self._pick_most_open(preferred, space_scores)

    @staticmethod
    def _pick_most_open(moves, space_scores):
        if not space_scores:
            return random.choice(moves)
        best_score = max(space_scores.get(m, 0) for m in moves)
        best_moves = [m for m in moves if space_scores.get(m, 0) == best_score]
        return random.choice(best_moves)