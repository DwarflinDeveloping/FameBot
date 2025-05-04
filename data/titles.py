import dataclasses
from typing import Literal

from discord import Color

RARITIES = Literal['COMMON', 'RARE', 'SUPER_RARE', 'MYTHIC', 'LEGENDARY', 'SPECIAL']

RARITY_COLORS = {
    'COMMON': Color.greyple(),
    'RARE': Color.blue(),
    'SUPER_RARE': Color.dark_blue(),
    'MYTHIC': Color.fuchsia(),
    'LEGENDARY': Color.gold(),
    'SPECIAL': Color.dark_purple()
}

RARITY_XP = {
    'COMMON': 1,
    'RARE': 2,
    'SUPER_RARE': 3,
    'MYTHIC': 4,
    'LEGENDARY': 5,
    'SPECIAL': 8
}

RARITY_CHANCES = {
    'COMMON': .0100,
    'RARE': .0050,
    'SUPER_RARE': .0025,
    'MYTHIC': .0010,
    'LEGENDARY': .0005,
    'SPECIAL': 0
}


@dataclasses.dataclass(frozen=True)
class Title:
    name: str
    rarity: RARITIES

    def __iter__(self):
        yield 'name', self.name
        yield 'rarity', self.rarity

    def __str__(self) -> str:
        return self.name

    @property
    def formatted_rarity(self) -> str:
        return ' '.join([s.capitalize() for s in self.rarity.lower().split('_')])

    @property
    def color(self) -> Color | None:
        return RARITY_COLORS.get(self.rarity, None)

    @property
    def xp_incr(self) -> int:
        return RARITY_XP.get(self.rarity, 0)

    @property
    def compensation(self) -> int:
        return self.xp_incr * 100

    @property
    def spawn_chance(self) -> float:
        return RARITY_CHANCES.get(self.rarity, 0)
