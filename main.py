import json
import os
import typing

from strategies.random_safe import RandomSafeStrategy
from strategies.food_seeker import FoodSeekerStrategy
from strategies.minimax import MinimaxStrategy

STRATEGY_FILE = os.environ.get(
    "STRATEGY_FILE", "/home/ubuntu/Battlesnake_first_attempt/strategy.txt"
)
LOG_FILE = os.environ.get(
    "LOG_FILE", "/home/ubuntu/Battlesnake_first_attempt/latest_game_log.jsonl"
)
DEFAULT_STRATEGY = "minimax"
VALID_GAME_MODES = {"standard", "constrictor", "royale"}

STRATEGIES = {
    "random_safe": RandomSafeStrategy(),
    "food_seeker": FoodSeekerStrategy(),
    "minimax": MinimaxStrategy(),
}


def get_current_config() -> typing.Tuple[str, typing.Optional[str]]:
    """Reads strategy.txt. Format is up to two lines:
        line 1: strategy name (e.g. "minimax")
        line 2 (optional): game mode override ("standard", "constrictor",
                            or "royale")
    If line 2 is missing or invalid, the game mode is auto-detected from
    the real game_state's own ruleset on each move instead -- the file
    override exists mainly for forcing a mode during local CLI testing.
    Returns (strategy_name, game_mode_override_or_None)."""
    strategy_name = DEFAULT_STRATEGY
    mode_override = None
    try:
        with open(STRATEGY_FILE) as f:
            lines = [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        return strategy_name, mode_override

    if lines and lines[0] in STRATEGIES:
        strategy_name = lines[0]
    if len(lines) > 1 and lines[1] in VALID_GAME_MODES:
        mode_override = lines[1]

    return strategy_name, mode_override


def get_game_mode(game_state: typing.Dict, mode_override: typing.Optional[str]) -> str:
    """The strategy.txt override wins if present; otherwise auto-detect
    from the real ruleset name Battlesnake sends with every request."""
    ruleset_name = game_state.get("game", {}).get("ruleset", {}).get("name", "standard")
    if ruleset_name not in VALID_GAME_MODES:
        ruleset_name = "standard"

    if mode_override:
        if mode_override != ruleset_name:
            print(
                f"WARNING: strategy.txt forces game_mode='{mode_override}' but the "
                f"real ruleset for this match is '{ruleset_name}'. If this isn't "
                f"intentional (e.g. local CLI testing), remove the second line of "
                f"strategy.txt so it auto-detects correctly."
            )
        return mode_override

    return ruleset_name


def info() -> typing.Dict:
    print("INFO")
    return {
        "apiversion": "1",
        "author": "your-username",
        "color": "#888888",
        "head": "default",
        "tail": "default",
    }


def start(game_state: typing.Dict):
    print("GAME START")
    try:
        with open(LOG_FILE, "w") as f:
            f.write(json.dumps({
                "event": "game_start",
                "game_id": game_state.get("game", {}).get("id"),
                "ruleset": game_state.get("game", {}).get("ruleset", {}).get("name"),
            }) + "\n")
    except OSError as e:
        print(f"WARNING: could not initialize log file: {e}")


def end(game_state: typing.Dict):
    print("GAME OVER\n")


def flood_fill_area(start, board_width, board_height, occupied, max_cells=None):
    """BFS from `start` counting reachable empty cells, treating `occupied`
    coordinates as walls. Returns the count of reachable cells (including
    the start cell if it's not occupied). If max_cells is given, stops
    early once that many cells have been counted (useful for performance
    when you only care whether there's "enough" space, not the exact size)."""
    if (start["x"], start["y"]) in occupied:
        return 0
    if not (0 <= start["x"] < board_width and 0 <= start["y"] < board_height):
        return 0

    visited = {(start["x"], start["y"])}
    queue = [(start["x"], start["y"])]
    count = 0

    while queue:
        x, y = queue.pop()
        count += 1
        if max_cells and count >= max_cells:
            return count
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in visited:
                continue
            if not (0 <= nx < board_width and 0 <= ny < board_height):
                continue
            if (nx, ny) in occupied:
                continue
            visited.add((nx, ny))
            queue.append((nx, ny))

    return count


def compute_safe_moves(game_state: typing.Dict, game_mode: str = "standard"):
    """Hazard logic every strategy needs: bounds, collisions, head-to-head,
    and dead-end (flood fill) avoidance.
    Returns (safe_moves: list[str], candidates: dict[str, {x,y}],
             space_scores: dict[str, int])."""
    is_move_safe = {"up": True, "down": True, "left": True, "right": True}

    my_head = game_state["you"]["body"][0]
    my_body = game_state["you"]["body"]
    board_width = game_state["board"]["width"]
    board_height = game_state["board"]["height"]
    all_snakes = game_state["board"]["snakes"]

    candidates = {
        "up": {"x": my_head["x"], "y": my_head["y"] + 1},
        "down": {"x": my_head["x"], "y": my_head["y"] - 1},
        "left": {"x": my_head["x"] - 1, "y": my_head["y"]},
        "right": {"x": my_head["x"] + 1, "y": my_head["y"]},
    }

    # Don't move backwards into your own neck
    if len(my_body) > 1:
        my_neck = my_body[1]
        if my_neck["x"] < my_head["x"]:
            is_move_safe["left"] = False
        elif my_neck["x"] > my_head["x"]:
            is_move_safe["right"] = False
        elif my_neck["y"] < my_head["y"]:
            is_move_safe["down"] = False
        elif my_neck["y"] > my_head["y"]:
            is_move_safe["up"] = False

    # Bounds
    for direction, coord in candidates.items():
        if not (0 <= coord["x"] < board_width and 0 <= coord["y"] < board_height):
            is_move_safe[direction] = False

    # Self + other snake collisions (full bodies, tails included --
    # conservative for the immediate-collision check)
    occupied_full = set()
    for snake in all_snakes:
        for segment in snake["body"]:
            occupied_full.add((segment["x"], segment["y"]))

    for direction, coord in candidates.items():
        if (coord["x"], coord["y"]) in occupied_full:
            is_move_safe[direction] = False

    # Avoid head-to-head with equal/larger snakes
    my_length = len(my_body)
    for snake in all_snakes:
        if snake["id"] == game_state["you"]["id"]:
            continue
        other_head = snake["body"][0]
        if len(snake["body"]) >= my_length:
            for direction, coord in candidates.items():
                dist = abs(coord["x"] - other_head["x"]) + abs(coord["y"] - other_head["y"])
                if dist == 1:
                    is_move_safe[direction] = False

    safe_moves = [m for m, is_safe in is_move_safe.items() if is_safe]

    # --- Flood fill / dead-end avoidance ---
    # Tails usually vacate next turn, so exclude them from the flood-fill
    # obstacle set -- EXCEPT in constrictor, where snakes never shrink and
    # tails are permanent obstacles.
    tails_vacate = game_mode != "constrictor"
    occupied_for_flood = set()
    for snake in all_snakes:
        body = snake["body"]
        segments = body[:-1] if tails_vacate else body
        for segment in segments:
            occupied_for_flood.add((segment["x"], segment["y"]))

    space_scores = {}
    for direction in safe_moves:
        coord = candidates[direction]
        space_scores[direction] = flood_fill_area(
            coord,
            board_width,
            board_height,
            occupied_for_flood,
            max_cells=my_length * 2,  # early-exit once "clearly enough" room
        )

    # Prefer moves where reachable space >= our length (won't trap us).
    # If every move traps us, fall back to all safe_moves so we at least
    # pick the least-bad option via space_scores in the strategy.
    non_trapping = [m for m in safe_moves if space_scores[m] >= my_length]
    if non_trapping:
        safe_moves = non_trapping

    return safe_moves, candidates, space_scores


def log_turn(game_state, strategy_name, game_mode, safe_moves, space_scores, next_move, strategy):
    """Append one line of JSON describing this turn's decision to LOG_FILE.
    Never allowed to raise -- a logging failure must never break gameplay."""
    try:
        real_ruleset = game_state.get("game", {}).get("ruleset", {}).get("name", "standard")
        record = {
            "event": "turn",
            "turn": game_state.get("turn"),
            "strategy": strategy_name,
            "game_mode": game_mode,
            "real_ruleset": real_ruleset,
            "mode_mismatch": game_mode != real_ruleset,
            "chosen_move": next_move,
            "safe_moves": safe_moves,
            "space_scores": space_scores,
            "my_health": game_state["you"]["health"],
            "my_length": len(game_state["you"]["body"]),
            "my_head": game_state["you"]["body"][0],
            "food": game_state["board"]["food"],
            "hazards": game_state["board"].get("hazards", []),
            "snakes": [
                {
                    "id": s["id"],
                    "health": s["health"],
                    "length": len(s["body"]),
                    "head": s["body"][0],
                }
                for s in game_state["board"]["snakes"]
            ],
            # Populated only by strategies that track it (currently
            # MinimaxStrategy); safely empty for others.
            "diagnostics": getattr(strategy, "last_diagnostics", {}),
        }
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        # Logging must never take down the actual game response.
        print(f"WARNING: failed to write turn log: {e}")


def move(game_state: typing.Dict) -> typing.Dict:
    strategy_name, mode_override = get_current_config()
    game_mode = get_game_mode(game_state, mode_override)

    safe_moves, candidates, space_scores = compute_safe_moves(game_state, game_mode)

    if not safe_moves:
        print(f"MOVE {game_state['turn']}: No safe moves detected! Moving down")
        return {"move": "down"}

    strategy = STRATEGIES[strategy_name]

    try:
        next_move = strategy.choose_move(game_state, safe_moves, candidates, space_scores, game_mode)
        if next_move not in safe_moves:
            # Defensive: a strategy bug returning something outside the
            # precomputed safe set should never take down the response.
            print(f"WARNING: strategy returned '{next_move}', not in safe_moves {safe_moves}; overriding")
            next_move = max(safe_moves, key=lambda m: space_scores.get(m, 0))
    except Exception as e:
        # A crash in strategy logic must never forfeit the turn. Fall back
        # to the safe move with the most open space.
        print(f"WARNING: strategy raised {type(e).__name__}: {e}; falling back to safest move")
        next_move = max(safe_moves, key=lambda m: space_scores.get(m, 0))

    print(f"MOVE {game_state['turn']}: {next_move} ({strategy_name}, {game_mode}) scores={space_scores}")

    log_turn(game_state, strategy_name, game_mode, safe_moves, space_scores, next_move, strategy)

    return {"move": next_move}


if __name__ == "__main__":
    from server import run_server
    run_server({"info": info, "start": start, "move": move, "end": end})