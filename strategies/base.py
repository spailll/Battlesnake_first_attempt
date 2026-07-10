import typing


class Strategy:
    def choose_move(
        self,
        game_state: typing.Dict,
        safe_moves: typing.List[str],
        candidates: typing.Dict[str, typing.Dict],
        space_scores: typing.Dict[str, int],
    ) -> str:
        """
        game_state:    the full raw game state dict from Battlesnake
        safe_moves:    list of direction strings, e.g. ["up", "left"],
                       already filtered for bounds/collision/head-to-head
                       and (where possible) dead-end avoidance
        candidates:    dict mapping each direction to the {x, y} coord
                       your head would land on if you took that move
        space_scores:  dict mapping each safe direction to the number of
                       reachable open cells from that move (flood fill);
                       higher is more open space. Only contains entries
                       for directions in safe_moves.
        Must return a single direction string from safe_moves.
        """
        raise NotImplementedError