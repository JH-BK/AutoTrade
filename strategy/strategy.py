"""Auto trading stretegy module."""
from typing import List


class Stretegy:
    """Base class for automatic trading stretegy."""

    def __init__(self, codes: List[str]):
        self.codes = codes

    def get_data(self) -> bool:
        raise NotImplementedError

    def get_target_price(self) -> int:
        raise NotImplementedError

    def get_sell_price(self) -> int:
        raise NotImplementedError

    def check_condition(self) -> bool:
        raise NotImplementedError
