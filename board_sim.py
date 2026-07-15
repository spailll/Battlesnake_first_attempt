import typing

DIRECTIONS = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}

# Extra health lost per turn for standing in a hazard cell (royale's shrinking
# damage zone). Battlesnake's default is 14; adjust here if your competition
# uses a different ruleset setting.
ROYALE_HAZARD_DAMAGE = 14


def state_from_game_state(game_state: typing.Dict, mode: str = "standard") -> typing.Dict:
    """Convert the raw Battlesnake JSON into a lightweight simulation state
    used for lookahead search. Coordinates are plain (x, y) tuples.

    mode: "standard", "constrictor", or "royale". Affects how apply_moves
    simulates growth/health, and how Voronoi/flood-fill treat tails."""
    snakes = {}
    for snake in game_state["board"]["snakes"]:
        snakes[snake["id"]] = {
            "body": [(seg["x"], seg["y"]) for seg in snake["body"]],
            "health": snake["health"],
        }
    food = {(f["x"], f["y"]) for f in game_state["board"]["food"]}
    hazards = {(h["x"], h["y"]) for h in game_state["board"].get("hazards", [])}
    return {
        "width": game_state["board"]["width"],
        "height": game_state["board"]["height"],
        "food": food,
        "hazards": hazards,
        "snakes": snakes,
        "mode": mode,
    }


def legal_moves(state: typing.Dict, snake_id: str) -> typing.List[str]:
    """Directions that don't immediately reverse into the snake's own neck.
    This does NOT rule out every death (that's handled by apply_moves plus
    the evaluation function) -- it just trims the obviously-pointless
    reversal move to reduce how much the search has to explore."""
    if snake_id not in state["snakes"]:
        return []
    body = state["snakes"][snake_id]["body"]
    head = body[0]
    moves = list(DIRECTIONS.keys())
    if len(body) > 1:
        neck = body[1]
        delta = (neck[0] - head[0], neck[1] - head[1])
        for d, ddelta in list(DIRECTIONS.items()):
            if ddelta == delta:
                moves.remove(d)
                break
    return moves


def apply_moves(state: typing.Dict, moves: typing.Dict[str, str]) -> typing.Dict:
    """Advance the simulation by one turn given a direction for every
    currently-alive snake included in `moves`. Returns a NEW state dict
    (does not mutate the input). Handles: movement, eating/growth, health
    decay, starvation, wall collisions, body collisions, head-to-head
    resolution (shorter snake dies; equal length, both die), and mode-
    specific rules:
      - "constrictor": every snake grows every turn regardless of food,
        and health never decreases (there's no starvation in this mode).
      - "royale": standing in a hazard cell costs extra health on top of
        normal decay.
      - "standard": normal food/health rules."""
    width, height = state["width"], state["height"]
    mode = state.get("mode", "standard")
    old_food = set(state["food"])
    hazards = state.get("hazards", set())
    new_snakes = {}
    new_heads = {}

    # Step 1: move each snake's head independently, handle food/health/growth
    for sid, snake in state["snakes"].items():
        direction = moves.get(sid)
        if direction is None:
            continue  # snake not given a move this turn (e.g. already dead)
        dx, dy = DIRECTIONS[direction]
        head = snake["body"][0]
        new_head = (head[0] + dx, head[1] + dy)

        if mode == "constrictor":
            # Always grows, tail never vacates, health is not a concern.
            ate = True
            new_body = [new_head] + snake["body"]
            new_health = 100
        else:
            ate = new_head in old_food
            if ate:
                new_body = [new_head] + snake["body"]  # tail stays, snake grows
                new_health = 100
            else:
                new_body = [new_head] + snake["body"][:-1]  # tail vacates
                new_health = snake["health"] - 1

            if mode == "royale" and new_head in hazards:
                new_health -= ROYALE_HAZARD_DAMAGE

        new_snakes[sid] = {"body": new_body, "health": new_health}
        new_heads[sid] = new_head

    if mode == "constrictor":
        new_food = set()  # constrictor never has food
    else:
        eaten = {h for sid, h in new_heads.items() if h in old_food}
        new_food = old_food - eaten

    # Step 2: resolve deaths using the fully-updated positions
    alive = {}
    for sid, snake in new_snakes.items():
        head = snake["body"][0]

        # Out of bounds
        if not (0 <= head[0] < width and 0 <= head[1] < height):
            continue

        # Starvation (never triggers in constrictor since health stays 100)
        if snake["health"] <= 0:
            continue

        # Body collision: hitting any snake's body, excluding heads
        # (head-on-head is handled separately below with length rules)
        died = False
        for other_sid, other_snake in new_snakes.items():
            body_to_check = other_snake["body"][1:]
            if head in body_to_check:
                died = True
                break
        if died:
            continue

        # Head-to-head: shorter snake dies; equal length, both die
        for other_sid, other_snake in new_snakes.items():
            if other_sid == sid:
                continue
            if other_snake["body"][0] == head:
                if len(other_snake["body"]) >= len(snake["body"]):
                    died = True
                    break
        if died:
            continue

        alive[sid] = snake

    return {
        "width": width,
        "height": height,
        "food": new_food,
        "hazards": hazards,
        "snakes": alive,
        "mode": mode,
    }