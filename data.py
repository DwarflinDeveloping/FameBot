import asyncio
import json
from math import floor
from pathlib import Path
import dataclasses
from time import time, sleep
from typing import Dict, Self, Iterator, List
from xml.etree.ElementTree import indent

import discord
import pycountry

data_path = Path('data.json')
flags_dir = Path('flags')
banners_dir = Path('banners')
users_dir = Path('users')
images_dir = Path('users')
for path in flags_dir, banners_dir, users_dir, images_dir:
    path.mkdir(exist_ok=True)

PV_PRESET = {'votes': 0, 'points': 0}
COUNTRY_DATA_PRESET = {country.alpha_2: PV_PRESET.copy() for country in pycountry.countries}

DATA_PRESET = {
    'total': COUNTRY_DATA_PRESET,
    'recap': {scope: {country.alpha_2: {'votes': 0, 'points': 0, 'dpos_votes': 0, 'dpos_points': 0} for country in pycountry.countries} for scope in ['daily', 'weekly', 'seasonal']},
    'daily_claims': {},
    'users': {},
    'maintenance': False,
    'admins': [784473264755834880]
}

USER_DATA_PRESET = {
    'total': PV_PRESET.copy(),
    'alltime_country': {},
    'additional_xp': 0,
    'next_vote': None,
    'daily_claim': None
}

PROGRESSION_ROLES = {
    0: 1363309917926064210,
    30: 1363310545108996238,
    60: 1363310802060447804,
    100: 1363310895580709017,
    130: 1363311104364773596,
    160: 1363311311924101180,
    200: 1363311794533437540,
    250: 1363312217298305304,
    300: 1363312348424568932,
    375: 1363312436232323123,
    450: 1363312587449569551,
    525: 1363312813531070595,
    600: 1363312962009301202,
    800: 1363313105165095175,
    1000: 1363313333511389296
}

@dataclasses.dataclass
class FameUser:
    data: dict
    user_id: int

    @classmethod
    def from_file(cls, user_id: int) -> Self:
        file_path = Path(users_dir, f'{user_id}.json')
        if file_path.is_file():
            user_data = json.loads(file_path.read_text())
        else:
            user_data = USER_DATA_PRESET
        return cls(user_data, user_id)

    @property
    def file_path(self) -> Path:
        return Path(users_dir, f'{self.user_id}.json')

    def save(self):
        self.file_path.write_text(json.dumps(self.data, indent=2))

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
        return self.data['additional_xp']

    @additional_xp.setter
    def additional_xp(self, value: int) -> None:
        self.data['additional_xp'] = value

    @property
    def daily_claim(self) -> int | None:
        return self.data['daily_claim']

    @daily_claim.setter
    def daily_claim(self, value: int | None) -> None:
        self.data['daily_claim'] = value

    def update_daily_claim(self):
        self.daily_claim = time()

    @property
    def next_vote(self) -> int | None:
        return self.data['next_vote']

    @property
    def vote_ready(self):
        return self.next_vote - time() <= 0

    @property
    def remaining_cooldown(self) -> float:
        return max(0, self.next_vote - time())

    async def wait_cooldown(self) -> None:
        duration = self.remaining_cooldown if self.next_vote else 0
        await asyncio.sleep(duration)

    @next_vote.setter
    def next_vote(self, value: int | None) -> None:
        self.data['next_vote'] = value

    def update_next_vote(self, cooldown: float):
        self.next_vote = time() + cooldown

    @property
    def leveling(self) -> float:
        return 1 + (self.total_votes * 10 + self.additional_xp) / 100

    @property
    def points_per_vote(self) -> int:
        return floor(self.leveling)

    def get_country(self, alpha2: str) -> Dict[str, int]:
        return self.data['country'][alpha2]

    @property
    def roles(self) -> Iterator[int]:
        for requirement in PROGRESSION_ROLES:
            if self.leveling >= requirement:
                yield PROGRESSION_ROLES[requirement]
            break

    @property
    def leveling_formatted(self) -> str:
        return f'**Lvl. {floor(self.leveling)}** ({floor((self.leveling%1)*100)}% progress)'

def load_data() -> dict:
    if data_path.exists():
        return json.loads(data_path.read_text())
    else:
        return DATA_PRESET

def save_data(value: dict) -> None:
    data_path.write_text(json.dumps(value, indent=2))

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
