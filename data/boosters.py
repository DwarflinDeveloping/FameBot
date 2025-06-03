import dataclasses
from math import floor, ceil
from random import randint, choices
from typing import Type, Self, Tuple, List

from discord import Color
from discord.utils import classproperty


@dataclasses.dataclass
class Booster:
    name: str
    boost: float
    base_duration: int
    spawn_chance: int
    color: Color
    symbol: str = ''
    firedust_cost: int | None = None
    boosts_xp: bool = False
    id: str = None

    def __init__(self, left_duration: int = None):
        self.left_duration = left_duration if left_duration is not None else self.get_rand_duration()

    @classmethod
    def cls_dict(cls):
        yield 'name', cls.name

    @classmethod
    def duration_boundaries(cls) -> Tuple[int, int]:
        return floor(cls.base_duration / 2), ceil(cls.base_duration * 3/2)

    @classmethod
    def get_rand_duration(cls) -> int:
        a = randint(*cls.duration_boundaries())
        return a

    def __iter__(self):
        yield from self.cls_dict()
        yield 'left_duration', self.left_duration

    @classmethod
    def from_name(cls, name: str) -> Type[Self] | None:
        for booster in boosters:
            if booster.name == name:
                return booster
        return None

    @classmethod
    def get_random(cls, excluded: List[Type[Self]] = None) -> Type[Self]:
        if excluded is None:
            excluded = []

        viable_boosters = [booster for booster in boosters if booster not in excluded]
        chances = [booster.spawn_chance for booster in viable_boosters]
        total = sum(chances)
        if total == 0:
            return None  # avoid division by 0
        normalized_chances = [c / total for c in chances]
        return choices(viable_boosters, weights=normalized_chances, k=1)[0]

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        left_duration = data.get('left_duration', None)
        return cls.from_name(data['name'])(left_duration)

    @classmethod
    def format_boost(cls):
        return f'{floor(cls.boost * 100)}%'

    @classmethod
    def format_duration(cls):
        return ' - '.join([str(val) for val in cls.duration_boundaries()])

    @classproperty
    def formatted_name(cls) -> str:
        return f'{cls.symbol} {cls.name}'

    @classmethod
    def format_name(cls, amount: int = None) -> str:
        amount_prefix = f'{amount}x ' if amount else ''
        return f'{amount_prefix}{cls.formatted_name}'

class StarterBooster(Booster):
    name = 'Starter Firepower'
    symbol = '🔥'
    boost = 3.00
    base_duration = 50
    spawn_chance = 0
    boosts_xp = True
    color = Color.dark_red()
    id = 'st'

class RoleUpBooster(Booster):
    name = 'Role Up Firepower'
    symbol = '⏫'
    boost = 1.00
    base_duration = 20
    spawn_chance = 0
    color = Color.yellow()
    id = 'ru'

class BronzeBooster(Booster):
    name = 'Bronze Firepower'
    symbol = '🟫'
    boost = 0.25
    base_duration = 20
    spawn_chance = 110
    color = Color.from_rgb(140, 85, 65)
    firedust_cost = 5
    id = 'br'

class SilverBooster(Booster):
    name = 'Silver Firepower'
    symbol = '🩶'
    boost = 0.50
    base_duration = 30
    spawn_chance = 80
    color = Color.greyple()
    firedust_cost = 10
    id = 'sv'

class GoldBooster(Booster):
    name = 'Gold Firepower'
    symbol = '⚜️'
    boost = 1.00
    base_duration = 50
    spawn_chance = 50
    color = Color.gold()
    firedust_cost = 20
    id = 'gd'

class DiamondBooster(Booster):
    name = 'Diamond Firepower'
    symbol = '💎'
    boost = 2.50
    base_duration = 70
    spawn_chance = 25
    color = Color.blue()
    firedust_cost = 40
    id = 'di'

class MythicBooster(Booster):
    name = 'Mythic Firepower'
    symbol = '🦄'
    boost = 4.00
    base_duration = 140
    spawn_chance = 8
    color = Color.nitro_pink()
    firedust_cost = 120
    id = 'my'

class LegendaryBooster(Booster):
    name = 'Legendary Firepower'
    symbol = '🐲'
    boost = 8.00
    base_duration = 250
    spawn_chance = 4
    color = Color.dark_green()
    firedust_cost = 300
    id = 'le'

class MastersBooster(Booster):
    name = 'Masters Firepower'
    symbol = '❤️'
    boost = 16.00
    base_duration = 500
    spawn_chance = 1
    color = Color.brand_red()
    firedust_cost = 600
    id = 'ma'

class ProBooster(Booster):
    name = 'Pro Firepower'
    symbol = '🏆'
    boost = 32.00
    base_duration = 1000
    spawn_chance = .5
    color = Color.dark_gold()
    firedust_cost = 1250
    id = 'pr'

class SeasonalBooster(Booster):
    name = 'Seasonal Firepower'
    symbol = '🌸'
    boost = 4.00
    base_duration = 500
    spawn_chance = 0
    color = Color.purple()
    id = 'ss'

class MysteryBooster(Booster):
    name = 'Mystery Firepower'
    symbol = '🌌'
    boost = 1.50
    base_duration = 30
    spawn_chance = 0
    color = Color.dark_blue()
    id = 'my'

class DailyBooster(Booster):
    name = 'Daily Firepower'
    symbol = '1️⃣'
    boost = 2.00
    base_duration = 80
    spawn_chance = 0
    color = Color.red()
    id = 'da'


boosters = (StarterBooster, RoleUpBooster, BronzeBooster, SilverBooster, GoldBooster, DiamondBooster, MythicBooster,
            LegendaryBooster, MastersBooster, ProBooster, SeasonalBooster, MysteryBooster, DailyBooster)

booster_name_to_cls = {b.name: b for b in boosters}
booster_names = list(booster_name_to_cls.keys())
