import dataclasses
from math import floor
from typing import Type, Self

from discord import Color


@dataclasses.dataclass
class Booster:
    name: str
    boost: float
    duration: int
    spawn_chance: int
    color: Color
    symbol: str = ''

    def __init__(self, left_duration: int = None):
        self.left_duration = left_duration if left_duration is not None else self.duration

    @classmethod
    def cls_dict(cls):
        yield 'name', cls.name

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
    def format_name(cls, amount: int = None) -> str:
        amount_prefix = f'{amount}x ' if amount else ''
        return f'{amount_prefix}{cls.symbol} {cls.name}'

class StarterBooster(Booster):
    name = 'Starter Firepower'
    symbol = '🔥'
    boost = 3.00
    duration = 50
    spawn_chance = 0
    color = Color.dark_red()

class RoleUpBooster(Booster):
    name = 'Role Up Firepower'
    symbol = '⏫'
    boost = 1.00
    duration = 20
    spawn_chance = 0
    color = Color.yellow()

class VoteBooster(Booster):
    name = 'Voting Firepower'
    symbol = '⬆️'
    boost = 0.50
    duration = 20
    spawn_chance = 0.015
    color = Color.blue()

class TurboBooster(Booster):
    name = 'Turbo Firepower'
    symbol = '💎'
    boost = 1.50
    duration = 30
    spawn_chance = 0.005
    color = Color.red()

class DailyBooster(Booster):
    name = 'Daily Firepower'
    symbol = '🎁'
    boost = 1.50
    duration = 30
    spawn_chance = 0.005
    color = Color.red()

boosters = (StarterBooster, RoleUpBooster, VoteBooster, TurboBooster, DailyBooster)
