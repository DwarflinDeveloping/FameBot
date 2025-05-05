import dataclasses
from math import floor, ceil
from random import randint
from typing import Type, Self, Tuple

from discord import Color


@dataclasses.dataclass
class Booster:
    name: str
    boost: float
    base_duration: int
    spawn_chance: int
    color: Color
    symbol: str = ''

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
    def from_name(cls, name: str) -> Type['Booster'] | None:
        for booster in boosters:
            if booster.name == name:
                return booster
        return None

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

    @classmethod
    def format_name(cls, amount: int = None) -> str:
        amount_prefix = f'{amount}x ' if amount else ''
        return f'{amount_prefix}{cls.symbol} {cls.name}'

class StarterBooster(Booster):
    name = 'Starter Firepower'
    symbol = '🔥'
    boost = 3.00
    base_duration = 50
    spawn_chance = 0
    color = Color.dark_red()

class RoleUpBooster(Booster):
    name = 'Role Up Firepower'
    symbol = '⏫'
    boost = 1.00
    base_duration = 20
    spawn_chance = 0
    color = Color.yellow()

class BronzeBooster(Booster):
    name = 'Bronze Firepower'
    symbol = '🟫'
    boost = 0.25
    base_duration = 20
    spawn_chance = 100
    color = Color.from_rgb(140, 85, 65)

class SilverBooster(Booster):
    name = 'Silver Firepower'
    symbol = '🩶'
    boost = 0.50
    base_duration = 35
    spawn_chance = 75
    color = Color.greyple()

class GoldBooster(Booster):
    name = 'Gold Firepower'
    symbol = '⚜️'
    boost = 1.00
    base_duration = 50
    spawn_chance = 50
    color = Color.gold()

class DiamondBooster(Booster):
    name = 'Diamond Firepower'
    symbol = '💎'
    boost = 2.50
    base_duration = 80
    spawn_chance = 25
    color = Color.blue()

class MythicBooster(Booster):
    name = 'Mythic Firepower'
    symbol = '🦄'
    boost = 5.00
    base_duration = 160
    spawn_chance = 10
    color = Color.nitro_pink()

class LegendaryBooster(Booster):
    name = 'Legendary Firepower'
    symbol = '🐲'
    boost = 10.00
    base_duration = 330
    spawn_chance = 5
    color = Color.dark_green()

class MastersBooster(Booster):
    name = 'Masters Firepower'
    symbol = '❤️'
    boost = 25.00
    base_duration = 700
    spawn_chance = 1
    color = Color.brand_red()

class ProBooster(Booster):
    name = 'Pro Firepower'
    symbol = '🏆'
    boost = 50.00
    base_duration = 1300
    spawn_chance = .5
    color = Color.dark_gold()

class SeasonalBooster(Booster):
    name = 'Seasonal Firepower'
    symbol = '🌸'
    boost = 4.00
    base_duration = 500
    spawn_chance = 0
    color = Color.purple()

class MysteryBooster(Booster):
    name = 'Mystery Firepower'
    symbol = '🫆'
    boost = 1.50
    base_duration = 30
    spawn_chance = 0
    color = Color.dark_blue()

class DailyBooster(Booster):
    name = 'Daily Firepower'
    symbol = '1️⃣'
    boost = 1.00
    base_duration = 50
    spawn_chance = 0
    color = Color.red()


boosters = (StarterBooster, RoleUpBooster, BronzeBooster, SilverBooster, GoldBooster, DiamondBooster, MythicBooster,
            LegendaryBooster, MastersBooster, ProBooster, SeasonalBooster, MysteryBooster, DailyBooster)
