import typing


def compute_voronoi(state: typing.Dict, my_id: str) -> typing.Tuple[int, int]:
    """Multi-source BFS from every snake's head simultaneously. Each open
    cell is claimed by whichever snake's expanding wave reaches it first;
    if two snakes would reach a cell at the same time, it's contested and
    claimed by neither. Returns (my_area, opponents_area).

    In "constrictor" mode, snakes never shrink (tails never vacate), so
    every body segment is a permanent obstacle. In all other modes, tails
    are treated as passable since they usually move out of the way."""
    width, height = state["width"], state["height"]
    snakes = state["snakes"]
    tails_vacate = state.get("mode", "standard") != "constrictor"

    occupied = set()
    for snake in snakes.values():
        segments = snake["body"][:-1] if tails_vacate else snake["body"]
        for seg in segments:
            occupied.add(seg)

    claimed: typing.Dict[typing.Tuple[int, int], typing.Set[str]] = {}
    current_layer: typing.Dict[typing.Tuple[int, int], typing.Set[str]] = {}
    for sid, snake in snakes.items():
        head = snake["body"][0]
        current_layer.setdefault(head, set()).add(sid)

    while current_layer:
        next_layer: typing.Dict[typing.Tuple[int, int], typing.Set[str]] = {}
        for cell, owners in current_layer.items():
            if cell in claimed:
                continue
            claimed[cell] = owners
            x, y = cell
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                ncell = (x + dx, y + dy)
                nx, ny = ncell
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                if ncell in occupied or ncell in claimed:
                    continue
                next_layer.setdefault(ncell, set()).update(owners)
        current_layer = next_layer

    my_area = 0
    opp_area = 0
    for owners in claimed.values():
        if len(owners) == 1:
            (owner,) = owners
            if owner == my_id:
                my_area += 1
            else:
                opp_area += 1
        # contested cells (len(owners) > 1) count for nobody

    return my_area, opp_area