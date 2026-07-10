import os
import typing

from strategies.random_safe import RandomSafeStrategy
from strategies.food_seeker import FoodSeekerStrategy

STRATEGIES = {
    "random_safe": RandomSafeStrategy(),
    "food_seeker": FoodSeekerStrategy(),
    # add more as you build them: "flood_fill", "minimax", etc.
}

STRATEGY_FILE = os.environ.get("STRATEGY_FILE", "/home/ubuntu/Battlesnake_first_attempt/strategy.txt")
DEFAULT_STRATEGY = "food_seeker"
def get_current_strategy_name() -> str:
    try:
        with open(STRATEGY_FILE) as f:
            name = f.read().strip()
            if name in STRATEGIES:
                return name
    except FileNotFoundError:
        pass
    return DEFAULT_STRATEGY

STRATEGY_NAME = get_current_strategy_name()



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


def compute_safe_moves(game_state: typing.Dict):
    """Hazard logic every strategy needs: bounds, collisions, head-to-head.
    Returns (safe_moves: list[str], candidates: dict[str, {x,y}])."""
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

    # Self + other snake collisions
    occupied = set()
    for snake in all_snakes:
        for segment in snake["body"]:
            occupied.add((segment["x"], segment["y"]))

    for direction, coord in candidates.items():
        if (coord["x"], coord["y"]) in occupied:
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
    return safe_moves, candidates


def move(game_state: typing.Dict) -> typing.Dict:
    safe_moves, candidates = compute_safe_moves(game_state)

    if not safe_moves:
        print(f"MOVE {game_state['turn']}: No safe moves detected! Moving down")
        return {"move": "down"}

    strategy_name = get_current_strategy_name()
    strategy = STRATEGIES[strategy_name]
    next_move = strategy.choose_move(game_state, safe_moves, candidates)

    print(f"MOVE {game_state['turn']}: {next_move} ({strategy_name})")
    return {"move": next_move}

if __name__ == "__main__":
    from server import run_server
    run_server({"info": info, "start": start, "move": move, "end": end})