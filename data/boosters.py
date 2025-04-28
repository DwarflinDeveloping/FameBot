import dataclasses
from math import floor
from typing import Type

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

    def __iter__(self):
        yield 'name', self.name
        yield 'left_duration', self.left_duration

    @classmethod
    def from_name(cls, name: str) -> Type['Booster'] | None:
        for booster in boosters:
            if booster.name == name:
                return booster
        return None

    @classmethod
    def format_boost(cls):
        return f'{floor(cls.boost * 100)}%'

class StarterBooster(Booster):
    name = 'Starter Booster'
    symbol = '🔥'
    boost = 4.00
    duration = 50
    spawn_chance = 0
    color = Color.dark_red()

class RoleUpBooster(Booster):
    name = 'Role Up Booster'
    symbol = '⏫'
    boost = 1.00
    duration = 20
    spawn_chance = 0
    color = Color.yellow()

class VoteBooster(Booster):
    name = 'Voting Booster'
    symbol = '⬆️'
    boost = 0.50
    duration = 20
    spawn_chance = 0.015
    color = Color.blue()

class TurboBooster(Booster):
    name = 'Turbo Booster'
    symbol = '💎'
    boost = 1.50
    duration = 30
    spawn_chance = 0.005
    color = Color.red()

boosters = (StarterBooster, RoleUpBooster, VoteBooster, TurboBooster)
