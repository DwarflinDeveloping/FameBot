import asyncio
import dataclasses
import json
from copy import deepcopy
from math import floor
from pathlib import Path
from time import time
from typing import Self, List, Any, Iterator, Tuple, Dict, Type

from discord import User

from data import users_dir, USER_DATA_PRESET, PV_PRESET
from data.boosters import StarterBooster, Booster


@dataclasses.dataclass
class FameUser:
    data: dict
    user_id: int
    start_xp: int = 100
    xp_leveling_factor = .018
    cached_user: User | None = None

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
                elif key in ['leveling']:
                    for subkey, subval in preset_val.items():
                        if subkey not in user_data[key]:
                            user_data[key][subkey] = subval
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

    @property
    def daily_votes(self) -> int:
        return self.data['daily_votes']

    @daily_votes.setter
    def daily_votes(self, value: int) -> None:
        self.data['daily_votes'] = value

    @property
    def daily_streak(self) -> int:
        return self.data['daily_streak']

    @daily_streak.setter
    def daily_streak(self, value: int) -> None:
        self.data['daily_streak'] = value

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
    def giveaway_xp(self) -> int:
        return self.data['leveling']['giveaway_xp']

    @giveaway_xp.setter
    def giveaway_xp(self, value: int) -> None:
        self.data['leveling']['giveaway_xp'] = value

    @property
    def gift_xp(self) -> int:
        return self.data['leveling']['gift_xp']

    @gift_xp.setter
    def gift_xp(self, value: int) -> None:
        self.data['leveling']['gift_xp'] = value

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

    def add_booster(self, booster: Type[Booster], count: int = 1):
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

    @property
    def last_booster(self) -> int:
        return self.data['last_booster']

    @last_booster.setter
    def last_booster(self, value: int) -> None:
        self.data['last_booster'] = value

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
        self.add_booster(StarterBooster)
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
        return self.start_xp + self.vote_xp + self.giveaway_xp + self.gift_xp + self.additional_xp

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

    def get_role(self, progressions: Dict[int, int]) -> int | None:
        top_role = None
        for requirement, role in progressions.items():
            if requirement > self.leveling:
                return top_role
            else:
                top_role = role
        return None

    @property
    def leveling_formatted(self) -> str:
        return f'**Lvl. {floor(self.leveling)}** ({floor((self.leveling % 1 + 1e-5)*100)}% progress)'

