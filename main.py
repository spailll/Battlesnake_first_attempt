import os
import typing

from strategies.random_safe import RandomSafeStrategy
from strategies.food_seeker import FoodSeekerStrategy

STRATEGY_FILE = os.environ.get(
    "STRATEGY_FILE", "/home/ubuntu/Battlesnake_first_attempt/strategy.txt"
)
DEFAULT_STRATEGY = "food_seeker"

STRATEGIES = {
    "random_safe": RandomSafeStrategy(),
    "food_seeker": FoodSeekerStrategy(),
    # add more as you build them: "flood_fill", "minimax", etc.
}


def get_current_strategy_name() -> str:
    try:
        with open(STRATEGY_FILE) as f:
            name = f.read().strip()
            if name in STRATEGIES:
                return name
    except FileNotFoundError:
        pass
    return DEFAULT_STRATEGY


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


def compute_safe_moves(game_state: typing.Dict):
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

    # Self + other snake collisions (full bodies, tails included —
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
    # obstacle set. This is a simplification (a snake that just ate won't
    # shrink), but it's a reasonable default.
    occupied_for_flood = set()
    for snake in all_snakes:
        body = snake["body"]
        for segment in body[:-1]:  # exclude tail
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


def move(game_state: typing.Dict) -> typing.Dict:
    safe_moves, candidates, space_scores = compute_safe_moves(game_state)

    if not safe_moves:
        print(f"MOVE {game_state['turn']}: No safe moves detected! Moving down")
        return {"move": "down"}

    strategy_name = get_current_strategy_name()
    strategy = STRATEGIES[strategy_name]
    next_move = strategy.choose_move(game_state, safe_moves, candidates, space_scores)

    print(f"MOVE {game_state['turn']}: {next_move} ({strategy_name}) scores={space_scores}")
    return {"move": next_move}


if __name__ == "__main__":
    from server import run_server
    run_server({"info": info, "start": start, "move": move, "end": end})