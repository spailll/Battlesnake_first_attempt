class Strategy:
    def choose_move(self, game_state, safe_moves, candidates):
        """
        game_state: the full raw game state dict from Battlesnake
        safe_moves: list of direction strings, e.g. ["up", "left"]
        candidates: dict mapping each direction to the {x, y} coord
                    your head would land on if you took that move
                    e.g. {"up": {"x":3,"y":4}, "down": {...}, ...}
        Must return a single direction string.
        """
        raise NotImplementedError