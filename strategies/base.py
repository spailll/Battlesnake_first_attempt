import typing


class Strategy:
    def choose_move(
        self,
        game_state: typing.Dict,
        safe_moves: typing.List[str],
        candidates: typing.Dict[str, typing.Dict],
        space_scores: typing.Dict[str, int],
        game_mode: str = "standard",
    ) -> str:
        """game_mode is one of "standard", "constrictor", "royale"."""
        raise NotImplementedError