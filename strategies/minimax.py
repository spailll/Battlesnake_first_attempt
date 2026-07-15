import time
import typing
from itertools import product

from .base import Strategy
from .voronoi import compute_voronoi

import sys
import os

# board_sim.py lives at the project root, one level up from strategies/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from board_sim import state_from_game_state, apply_moves, legal_moves, DIRECTIONS  # noqa: E402

TIME_BUDGET_SECONDS = 0.35  # leave margin under Battlesnake's ~500ms timeout
MAX_DEPTH = 8               # sane ceiling so iterative deepening can't run forever

# --- Evaluation weights (tune these to change playstyle) ---
VORONOI_WEIGHT = 10           # reward per cell of territory advantage
LENGTH_WEIGHT = 20            # reward per segment longer than the biggest opponent
HEALTH_CRITICAL_THRESHOLD = 30
HEALTH_PENALTY_WEIGHT = 5     # penalty scaling once health drops below the threshold

FOOD_BASE_WEIGHT = 8          # small constant pull toward food even at full health
FOOD_LOW_HEALTH_THRESHOLD = 50
FOOD_URGENCY_WEIGHT = 12      # extra pull toward food per missing health point below the threshold

# Constrictor has no food and no starvation -- the entire game is board
# control, so territory matters even more than in standard play.
CONSTRICTOR_VORONOI_WEIGHT = 25

# Royale: standing in a hazard cell already costs extra health (simulated in
# apply_moves), which naturally raises food urgency and the health penalty.
# This adds a small additional nudge to avoid lingering in hazard right now.
ROYALE_HAZARD_PENALTY = 30

# Opponents farther than this (Manhattan distance) from our head are not
# treated as fully adversarial in the search -- we still simulate a move for
# them (so Voronoi/collisions stay accurate), but we don't enumerate every
# option they have and assume the worst one against us. Without this, the
# "paranoid" search imagines every opponent on the board conspiring against
# you turns in advance, which can make it needlessly avoid nearby food when
# no real threat is close enough to matter yet.
OPPONENT_CONSIDERATION_RADIUS = 5

# A flat bonus applied ONLY to the root decision when a candidate move lands
# directly on food this turn. Deep lookahead can correctly identify that
# growing costs long-term space near tight corners/coils, and no reasonable
# food-distance weight can consistently overcome that without destabilizing
# every other tradeoff in the evaluation. This bonus targets the specific,
# narrow case of "free food is one step away right now" directly, without
# changing how food/space are weighed anywhere else in the search.
IMMEDIATE_EAT_BONUS = 250


class TimeBudgetExceeded(Exception):
    pass


class MinimaxStrategy(Strategy):
    """Paranoid minimax with alpha-beta pruning and iterative deepening.
    Opponents are treated as a single worst-case adversary. Board states
    are scored using Voronoi territory control, length, health, and food
    -- with mode-specific adjustments for constrictor and royale.

    NOTE on scaling: each "opponent" ply enumerates the full cartesian
    product of every opponent's legal moves. With 1-3 opponents and
    alpha-beta pruning this is fine within the time budget on an 11x11
    board. With many more snakes on the board you may want to cap which
    opponents are considered (e.g. only the nearest 2) to keep the
    branching factor manageable.
    """

    def choose_move(self, game_state, safe_moves, candidates, space_scores, game_mode="standard"):
        if not safe_moves:
            return "up"

        state = state_from_game_state(game_state, mode=game_mode)
        my_id = game_state["you"]["id"]

        if my_id not in state["snakes"]:
            return safe_moves[0]

        start_time = time.time()
        best_move = safe_moves[0]
        depth = 1

        while time.time() - start_time < TIME_BUDGET_SECONDS and depth <= MAX_DEPTH:
            try:
                move = self._search_root(state, my_id, depth, start_time)
                if move is not None:
                    best_move = move
                depth += 1
            except TimeBudgetExceeded:
                break

        return best_move

    # ---- search ----

    def _check_time(self, start_time):
        if time.time() - start_time > TIME_BUDGET_SECONDS:
            raise TimeBudgetExceeded()

    def _search_root(self, state, my_id, depth, start_time):
        alpha, beta = float("-inf"), float("inf")
        best_score = float("-inf")
        best_move = None

        moves = legal_moves(state, my_id)
        if not moves:
            return None

        my_head = state["snakes"][my_id]["body"][0]
        food_cells = state["food"]

        for direction in moves:
            self._check_time(start_time)
            raw_score = self._min_node(state, my_id, direction, depth, alpha, beta, start_time)

            dx, dy = DIRECTIONS[direction]
            landing_cell = (my_head[0] + dx, my_head[1] + dy)
            bonus = IMMEDIATE_EAT_BONUS if landing_cell in food_cells else 0
            display_score = raw_score + bonus

            if display_score > best_score:
                best_score = display_score
                best_move = direction
            # Use the raw (un-bonused) score for the pruning bound, so the
            # one-off eat bonus doesn't cause the search to prune a
            # legitimate competing branch too aggressively.
            alpha = max(alpha, raw_score)

        return best_move

    def _max_node(self, state, my_id, depth, alpha, beta, start_time):
        self._check_time(start_time)

        if my_id not in state["snakes"]:
            return self._evaluate(state, my_id)
        if depth <= 0:
            return self._evaluate(state, my_id)

        moves = legal_moves(state, my_id)
        if not moves:
            # No non-reversing move available; snake is almost certainly
            # about to die -- score the current state as-is.
            return self._evaluate(state, my_id)

        best = float("-inf")
        for direction in moves:
            score = self._min_node(state, my_id, direction, depth, alpha, beta, start_time)
            best = max(best, score)
            alpha = max(alpha, best)
            if alpha >= beta:
                break  # alpha-beta cutoff
        return best

    def _min_node(self, state, my_id, my_direction, depth, alpha, beta, start_time):
        self._check_time(start_time)

        opponent_ids = [sid for sid in state["snakes"] if sid != my_id]

        if not opponent_ids:
            next_state = apply_moves(state, {my_id: my_direction})
            return self._max_node(next_state, my_id, depth - 1, alpha, beta, start_time)

        my_head = state["snakes"][my_id]["body"][0]
        nearby_ids = []
        fixed_moves = {}
        for sid in opponent_ids:
            other_head = state["snakes"][sid]["body"][0]
            dist = abs(other_head[0] - my_head[0]) + abs(other_head[1] - my_head[1])
            if dist <= OPPONENT_CONSIDERATION_RADIUS:
                nearby_ids.append(sid)
            else:
                # Too far away to threaten us this turn. Give it one
                # reasonable move rather than exhaustively searching all of
                # its options and assuming the worst -- this keeps distant
                # snakes from making the search irrationally cautious.
                opts = legal_moves(state, sid) or ["up"]
                fixed_moves[sid] = opts[0]

        if not nearby_ids:
            moves = {my_id: my_direction, **fixed_moves}
            next_state = apply_moves(state, moves)
            return self._max_node(next_state, my_id, depth - 1, alpha, beta, start_time)

        nearby_options = [legal_moves(state, sid) or ["up"] for sid in nearby_ids]

        worst = float("inf")
        for combo in product(*nearby_options):
            self._check_time(start_time)
            moves = {my_id: my_direction, **fixed_moves}
            for sid, d in zip(nearby_ids, combo):
                moves[sid] = d
            next_state = apply_moves(state, moves)
            score = self._max_node(next_state, my_id, depth - 1, alpha, beta, start_time)
            worst = min(worst, score)
            beta = min(beta, worst)
            if alpha >= beta:
                break  # alpha-beta cutoff
        return worst

    # ---- evaluation ----

    def _evaluate(self, state, my_id):
        if my_id not in state["snakes"]:
            return -1_000_000

        opponents = [sid for sid in state["snakes"] if sid != my_id]
        if not opponents:
            return 1_000_000  # last snake standing

        mode = state.get("mode", "standard")
        my_snake = state["snakes"][my_id]
        my_length = len(my_snake["body"])
        longest_opponent = max(len(state["snakes"][o]["body"]) for o in opponents)
        my_area, opp_area = compute_voronoi(state, my_id)
        length_diff = my_length - longest_opponent

        if mode == "constrictor":
            # No food, no starvation -- the entire game is board control.
            # Health/food terms would be meaningless noise here.
            return (my_area - opp_area) * CONSTRICTOR_VORONOI_WEIGHT + length_diff * LENGTH_WEIGHT

        health = my_snake["health"]
        # Penalize low health increasingly as it approaches zero
        health_score = 0
        if health < HEALTH_CRITICAL_THRESHOLD:
            health_score = (health - HEALTH_CRITICAL_THRESHOLD) * HEALTH_PENALTY_WEIGHT

        # Food term: closer to the nearest food is better. Weight ramps up
        # as health drops, so it's a mild preference at full health and a
        # strong pull once starving. Manhattan distance is a cheap
        # approximation (ignores walls/other snakes) but is fine here since
        # it's only used as a soft tiebreaker, not a safety check.
        food = state["food"]
        my_head = my_snake["body"][0]
        if food:
            nearest_food_dist = min(
                abs(my_head[0] - f[0]) + abs(my_head[1] - f[1]) for f in food
            )
        else:
            nearest_food_dist = 0

        food_weight = FOOD_BASE_WEIGHT
        if health < FOOD_LOW_HEALTH_THRESHOLD:
            food_weight += (FOOD_LOW_HEALTH_THRESHOLD - health) * FOOD_URGENCY_WEIGHT

        food_score = -nearest_food_dist * food_weight

        # Royale: extra nudge to avoid lingering in a hazard cell right now,
        # on top of the health cost already reflected via simulation.
        hazard_score = 0
        if mode == "royale":
            hazards = state.get("hazards", set())
            if my_head in hazards:
                hazard_score = -ROYALE_HAZARD_PENALTY

        score = (
            (my_area - opp_area) * VORONOI_WEIGHT
            + length_diff * LENGTH_WEIGHT
            + health_score
            + food_score
            + hazard_score
        )
        return score