import asyncio
import json
import math
import os
from copy import deepcopy
from math import floor
from os import PathLike
from pathlib import Path
import dataclasses
from time import time
from typing import Dict, Self, Iterator, List, Any, Type, Tuple

import discord
import pycountry

data_path = Path('data.json')

flags_dir = Path('flags')
banners_dir = Path('banners')
images_dir = Path('images')

users_dir = Path('users')
recaps_dir = Path('recaps')

for path in flags_dir, banners_dir, users_dir, images_dir, recaps_dir:
    path.mkdir(exist_ok=True)

PV_PRESET = {'votes': 0, 'points': 0}
DPV_PRESET = PV_PRESET | {'dpos_votes': 0, 'dpos_points': 0}
COUNTRY_DATA_PRESET = {country.alpha_2: PV_PRESET.copy() for country in pycountry.countries}

DATA_PRESET = {
    'maintenance': False,
    'admins': [784473264755834880]
}

USER_DATA_PRESET = {
    'total': deepcopy(PV_PRESET),
    'alltime_country': {},
    'leveling': {
        'vote_xp': 0,
        'additional_xp': 0,
    },
    'next_vote': None,
    'daily_claim': None,
    'claims': [],
    'boosters': {},
    'active_booster': None
}

RECAP_DATA_PRESET = {
    'start_timestamp': None,
    'country': {}
}

PROGRESSION_ROLES = {
    0: 1363309917926064210,   # Bronze 1
    10: 1363920859953103140,  # Bronze 2
    20: 1363921907497308314,  # Bronze 3
    30: 1363310545108996238,  # Silver 1
    40: 1363922324612448469,  # Silver 2
    50: 1363922416111321478,  # Silver 3
    60: 1363310802060447804,  # Gold 1
    70: 1363310895580709017,  # Gold 2
    80: 1363311104364773596,  # Gold 3
    90: 1363311311924101180,  # Diamond 1
    100: 1363311794533437540, # Diamond 2
    110: 1363312217298305304, # Diamond 3
    120: 1363312348424568932, # Mythic 1
    130: 1363312436232323123, # Mythic 2
    140: 1363312587449569551, # Mythic 3
    150: 1363312813531070595, # Legendary 1
    170: 1363312962009301202, # Legendary 2
    190: 1363313105165095175, # Legendary 3
    210: 1363313333511389296, # Masters 1
    230: 1363922924066832504, # Masters 2
    250: 1363923020774641916, # Masters 3
    270: 1363323340764479620  # Pro Member
}

@dataclasses.dataclass
class Booster:
    name: str
    boost: float
    duration: int
    spawn_chance: int
    color: discord.Color
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
    color = discord.Color.dark_red()

class RoleUpBooster(Booster):
    name = 'Role Up Booster'
    symbol = '⏫'
    boost = 1.00
    duration = 20
    spawn_chance = 0
    color = discord.Color.yellow()

class VoteBooster(Booster):
    name = 'Voting Booster'
    symbol = '⬆️'
    boost = 0.50
    duration = 20
    spawn_chance = 0.015
    color = discord.Color.blue()

class TurboBooster(Booster):
    name = 'Turbo Booster'
    symbol = '💎'
    boost = 1.50
    duration = 30
    spawn_chance = 0.005
    color = discord.Color.red()

boosters = (StarterBooster, RoleUpBooster, VoteBooster, TurboBooster)

@dataclasses.dataclass
class FameRecap:
    data: dict
    scope: str

    @classmethod
    def from_file(cls, scope: str) -> Self:
        file_path = Path(recaps_dir, f'{scope}.json')
        if file_path.is_file():
            recap_data = json.loads(file_path.read_text())
            for key, preset_val in RECAP_DATA_PRESET.items():
                if key not in recap_data:
                    recap_data[key] = deepcopy(preset_val)
        else:
            recap_data = deepcopy(RECAP_DATA_PRESET)
            if scope == 'alltime':
                recap_data['country'] = deepcopy(COUNTRY_DATA_PRESET)
            recap_data['start_timestamp'] = time()
        return cls(recap_data, scope)

    @property
    def file_path(self) -> Path:
        return Path(recaps_dir, f'{self.scope}.json')

    def save(self):
        self.file_path.write_text(json.dumps(self.data, indent=2))

    @property
    def start_timestamp(self) -> float:
        return self.data['start_timestamp']

    @start_timestamp.setter
    def start_timestamp(self, value: float) -> None:
        self.data['start_timestamp'] = value

    def get(self, alpha2: str):
        return self.data['country'][alpha2] if alpha2 in self.data['country'] else DPV_PRESET.copy()

    def add(self, alpha2: str, points: int = 0, votes: int = 0, **kwargs):
        c_data = self.get(alpha2)
        c_data['votes'] += votes
        c_data['points'] += points
        for a, b in kwargs.items():
            c_data[a] += b
        self.data['country'][alpha2] = c_data

    def set(self, alpha2: str, points: int = 0, votes: int = 0, **kwargs):
        c_data = self.get(alpha2)
        c_data['votes'] = votes
        c_data['points'] = points
        for a, b in kwargs.items():
            c_data[a] = b
        self.data['country'][alpha2] = c_data

@dataclasses.dataclass
class FameUser:
    data: dict
    user_id: int
    start_xp: int = 100
    xp_leveling_factor = .018
    cached_user: discord.User | None = None

    def __post_init__(self):
        self.update_legacy()

    @classmethod
    def from_file(cls, user_id: int) -> Self:
        file_path = Path(users_dir, f'{user_id}.json')
        if file_path.is_file():
            user_data = json.loads(file_path.read_text())
            for key, preset_val in USER_DATA_PRESET.items():
                if key not in user_data:
                    user_data[key] = deepcopy(preset_val)
        else:
            user_data = deepcopy(USER_DATA_PRESET)
        return cls(user_data, user_id)

    @property
    def file_path(self) -> Path:
        return Path(users_dir, f'{self.user_id}.json')

    def save(self) -> None:
        self.file_path.write_text(json.dumps(self.data, indent=2))

    def update_legacy(self) -> None:
        if self.total_votes > 0 and self.vote_xp == 0:
            self.vote_xp = self.total_votes * 10

        if 'additional_xp' in self.data:
            self.additional_xp = self.data['additional_xp']
            del self.data['additional_xp']

    @property
    def total_votes(self) -> int:
        return self.data['total']['votes']

    @total_votes.setter
    def total_votes(self, value: int) -> None:
        self.data['total']['votes'] = value

    @property
    def total_points(self) -> int:
        return self.data['total']['points']

    @total_points.setter
    def total_points(self, value: int) -> None:
        self.data['total']['points'] = value

    def get_country_alltime(self, alpha2: str):
        return self.data['alltime_country'][alpha2] if alpha2 in self.data['alltime_country'] else PV_PRESET.copy()

    def add_country_alltime(self, alpha2: str, points: int = 0, votes: int = 0):
        c_alltime = self.get_country_alltime(alpha2)
        c_alltime['votes'] += votes
        c_alltime['points'] += points
        self.data['alltime_country'][alpha2] = c_alltime

    @property
    def additional_xp(self) -> int:
        return self.data['leveling']['additional_xp']

    @additional_xp.setter
    def additional_xp(self, value: int) -> None:
        self.data['leveling']['additional_xp'] = value

    @property
    def vote_xp(self) -> int:
        return self.data['leveling']['vote_xp']

    @vote_xp.setter
    def vote_xp(self, value: int) -> None:
        self.data['leveling']['vote_xp'] = value

    @property
    def daily_claim(self) -> int | None:
        return self.data['daily_claim']

    @daily_claim.setter
    def daily_claim(self, value: int | None) -> None:
        self.data['daily_claim'] = value

    def update_daily_claim(self):
        self.daily_claim = time()

    @property
    def claims(self) -> List[Any]:
        return self.data['claims']

    @claims.setter
    def claims(self, value: List[Any]) -> None:
        self.data['claims'] = value

    @property
    def boosters(self) -> Iterator[Tuple[Booster, int]]:
        for name, count in self.data['boosters'].items():
            if count != 0:
                yield Booster.from_name(name), count

    def add_booster(self, booster: Booster, count: int = 1):
        if booster.name not in self.data['boosters']:
            self.data['boosters'][booster.name] = 0
        self.data['boosters'][booster.name] += count

    @property
    def active_booster(self) -> Booster | None:
        data = self.data['active_booster']
        if not data:
            return None

        booster = Booster.from_name(data['name'])()
        booster.left_duration = data['left_duration']
        return booster

    @active_booster.setter
    def active_booster(self, booster: Booster | None) -> None:
        self.data['active_booster'] = dict(booster) if booster is not None else None

    def activate_booster(self, booster: Booster):
        if booster.name not in [b.name for b, _ in self.boosters]:
            return
        self.data['boosters'][booster.name] -= 1
        if self.data['boosters'][booster.name] == 0:
            del self.data['boosters'][booster.name]
        self.active_booster = booster

    def do_vote(self, vote_count: int, alpha2: str, booster_applies: bool = True,
                gives_xp: bool = True) -> Tuple[int, int]:
        points_gained, xp_gained = 0, 0
        for _ in range(vote_count):
            points_incr = self.points_per_vote
            xp_incr = self.xp_per_vote if gives_xp else 0

            if booster_applies and self.has_active_booster:
                booster = self.active_booster
                points_incr *= 1 + booster.boost
                xp_incr *= 1 + booster.boost
                points_incr, xp_incr = floor(points_incr), floor(xp_incr)
                booster.left_duration -= 1
                if booster.left_duration <= 0:
                    self.active_booster = None
                else:
                    self.data['active_booster'] = dict(booster)

            points_gained += points_incr
            xp_gained += xp_incr
            self.total_votes += 1
            self.total_points += points_gained
            self.vote_xp += xp_gained
            self.add_country_alltime(alpha2, points=points_incr, votes=1)

        self.save()
        return points_gained, xp_gained

    @property
    def has_active_booster(self):
        return self.active_booster is not None

    @property
    def next_vote(self) -> int | None:
        return self.data['next_vote']

    @property
    def vote_ready(self):
        return self.next_vote - time() <= 0

    @property
    def remaining_cooldown(self) -> float:
        return max(0, self.next_vote - time())

    @property
    def has_claimed_starter_booster(self) -> bool:
        return 'Starter Booster' in self.claims

    def check_starter_booster(self) -> None:
        if self.has_claimed_starter_booster or self.level > 60:
            return
        self.add_booster(StarterBooster())
        self.claims.append('Starter Booster')
        self.save()

    @property
    def boosters_available(self) -> bool:
        return sum(self.data['boosters'].values()) > 0

    async def wait_cooldown(self) -> None:
        duration = self.remaining_cooldown if self.next_vote else 0
        await asyncio.sleep(duration)

    @next_vote.setter
    def next_vote(self, value: int | None) -> None:
        self.data['next_vote'] = value

    def update_next_vote(self, cooldown: float):
        self.next_vote = time() + cooldown

    @property
    def total_xp(self):
        return self.start_xp + self.vote_xp + self.additional_xp

    @property
    def next_level_xp(self) -> float:
        xp_threshold = self.start_xp
        for _ in range(self.level):
            xp_threshold *= 1 + self.xp_leveling_factor
        return xp_threshold

    @property
    def leveling(self) -> float:
        level = 0
        xp_threshold = self.start_xp  # XP required for level 1
        xp = self.total_xp
        while xp >= xp_threshold:
            level += 1
            xp -= xp_threshold
            xp_threshold *= 1 + self.xp_leveling_factor
        return level + xp / xp_threshold

    @property
    def xp_until_next_level(self) -> float:
        current_level_xp = 0
        xp_threshold = self.start_xp
        for _ in range(self.level):
            current_level_xp += xp_threshold
            xp_threshold *= 1 + self.xp_leveling_factor

        # Calculate the difference between next level's threshold and current XP
        return self.next_level_xp - (self.total_xp - current_level_xp)

    @property
    def level(self) -> int:
        return floor(self.leveling)

    @property
    def points_per_vote(self) -> int:
        return self.level

    @property
    def xp_per_vote(self) -> int:
        return 10

    def get_country(self, alpha2: str) -> Dict[str, int]:
        return self.data['country'][alpha2]

    @property
    def roles(self) -> Iterator[int]:
        for requirement in PROGRESSION_ROLES:
            if self.leveling >= requirement:
                yield PROGRESSION_ROLES[requirement]
            else:
                break

    @property
    def leveling_formatted(self) -> str:
        return f'**Lvl. {floor(self.leveling)}** ({floor((self.leveling % 1 + 1e-5)*100)}% progress)'

def load_data() -> dict:
    if data_path.exists():
        return json.loads(data_path.read_text())
    else:
        return DATA_PRESET

def save_data(value: dict) -> None:
    data_path.write_text(json.dumps(value, indent=2))

def clear_folder(dir_path: PathLike):
    for file in os.listdir(dir_path):
        os.remove(Path(dir_path, file))

async def clear_database(users: bool = False, recaps: List[str] | bool = False):
    if users is True:
        clear_folder(users_dir)
    if type(recaps) == bool and recaps is True:
        clear_folder(recaps_dir)
    elif type(recaps) == list:
        for scope in recaps:
            Path(recaps_dir, f'{scope}.json').unlink(missing_ok=True)

def get_flag_path(alpha2: str):
    return Path(flags_dir, alpha2 + '.png')

def get_banner_path(alpha2: str):
    return Path(banners_dir, alpha2 + '.jpg')

def get_flag(alpha2: str) -> discord.File | None:
    flag_path = get_flag_path(alpha2)
    if not flag_path.exists():
        return None
    return discord.File(flag_path, filename=alpha2 + '.png')

def get_banner(alpha2: str) -> discord.File | None:
    banner_path = get_banner_path(alpha2)
    if not banner_path.exists():
        return None
    return discord.File(banner_path, filename=alpha2 + '.jpg')
