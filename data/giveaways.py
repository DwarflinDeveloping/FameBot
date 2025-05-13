import dataclasses
from abc import ABC, abstractmethod, abstractclassmethod, abstractproperty, abstractstaticmethod
import random
from math import floor
from typing import Type, List, Self, Tuple, Dict, Optional

from data.boosters import Booster, DailyBooster, GoldBooster, BronzeBooster, SilverBooster
from data.titles import Title
from utils import CONTINENT_CODE_TO_NAME, ALPHA2_COUNTRIES, format_cname, alpha2_to_country


@dataclasses.dataclass(frozen=True)
class GiveawayPrice(ABC):
    @abstractmethod
    def __str__(self) -> str:
        ...

    @abstractmethod
    def __iter__(self):
        yield 'name', self.__class__.__name__

    @abstractmethod
    def apply(self, user) -> None:
        ...

    @abstractclassmethod
    def from_dict(cls, data: dict) -> Self:
        ...

    @classmethod
    def find_from_dict(self, value: dict):
        for p_type in price_types:
            if p_type.__name__ == value['name']:
                return p_type.from_dict(value)
        raise AssertionError()


@dataclasses.dataclass(frozen=True)
class XPPrice(GiveawayPrice):
    value: int

    def __str__(self) -> str:
        return f'{self.value}xp'

    def __iter__(self):
        yield from super().__iter__()
        yield 'value', self.value

    def apply(self, user) -> None:
        user.giveaway_xp += self.value

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(data['value'])

@dataclasses.dataclass(frozen=True)
class BoosterPrice(GiveawayPrice):
    booster: Type[Booster]
    amount: int = 1

    def __str__(self) -> str:
        return self.booster.format_name(self.amount)

    def __iter__(self):
        yield from super().__iter__()
        yield 'booster', dict(self.booster.cls_dict())
        yield 'amount', self.amount

    def apply(self, user) -> None:
        user.add_booster(self.booster, self.amount)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        booster = Booster.from_dict(data['booster']).__class__
        return cls(booster, data['amount'])

@dataclasses.dataclass(frozen=True)
class TitlePrice(GiveawayPrice):
    title: Title

    def __str__(self) -> str:
        return f'{self.title.formatted_rarity} Title: {self.title.name}'

    def __iter__(self):
        yield from super().__iter__()
        yield 'title', dict(self.title)

    def apply(self, user) -> None:
        user.add_title(self.title)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(Title(data['title']['name'], data['title']['rarity']))

price_types = (BoosterPrice, XPPrice, TitlePrice)

@dataclasses.dataclass()
class PriceList(ABC):
    prices: List[Type[GiveawayPrice]]

    @abstractstaticmethod
    def random_prices(*args, **kwargs) -> Tuple[Dict[GiveawayPrice | None, int], ...]:
        ...

    @classmethod
    def generate(cls, *args, **kwargs) -> Self:
        prices = []
        for category in cls.random_prices(*args, **kwargs):
            price = random.choices(list(category.keys()), weights=list(category.values()), k=1)[0]
            if price:
                prices.append(price)
        return cls(prices)

    @classmethod
    def from_dict(cls, value: dict) -> Self:
        return cls([GiveawayPrice.find_from_dict(price) for price in value['prices']])

    def __str__(self) -> str:
        return '\n'.join([f'- {price}' for price in self.prices])

    def __iter__(self):
        yield 'prices', [dict(price) for price in self.prices]

    def apply(self, user) -> None:
        for price in self.prices:
            price.apply(user)


@dataclasses.dataclass()
class Giveaway(PriceList):
    prices: List[Type[GiveawayPrice]]

    @staticmethod
    def random_prices(titles: List[Title]) -> Tuple[Dict[GiveawayPrice | None, int], ...]:
        viable_titles = [title for title in titles if title.rarity not in ('COMMON', 'RARE')]
        return \
            {XPPrice(500): 7, XPPrice(750): 6, XPPrice(1000): 5, XPPrice(1500): 3, XPPrice(2500): 1}, \
            {BoosterPrice(Booster.get_random([BronzeBooster, SilverBooster, GoldBooster])): 1}, \
            {BoosterPrice(DailyBooster): 1}, \
            {TitlePrice(title): int(title.spawn_chance * 10000) for title in viable_titles}


@dataclasses.dataclass()
class StreakReward(PriceList):
    prices: List[Type[GiveawayPrice]]

    @staticmethod
    def random_prices(daily_streak: int, titles: List[Title]) -> Tuple[Dict[GiveawayPrice | None, int], ...]:
        viable_titles = [title for title in titles if title.rarity not in ('COMMON', 'RARE')]
        cum_title_chances = sum(title.spawn_chance * 20 for title in viable_titles)
        return (
            {XPPrice(floor(100 * (daily_streak ** .8))): 7, XPPrice(floor(150 * (daily_streak ** .8))): 6, XPPrice(floor(200 * (daily_streak ** .8))): 5, XPPrice(floor(250 * (daily_streak ** .8))): 3, XPPrice(floor(500 * (daily_streak ** .8))): 1},
            {None: 5, BoosterPrice(GoldBooster, 1): 1},
            {None: 1, BoosterPrice(DailyBooster): 1},
            {None: 1 - cum_title_chances} | {TitlePrice(title): title.spawn_chance * 20 for title in viable_titles}
        )


@dataclasses.dataclass()
class Quest(PriceList, ABC):
    prices: List[Type[GiveawayPrice]]
    name: str = 'Quest'
    description: str = ''
    requirement: int = 0
    target: Tuple[str, Optional[str]] | None = None
    progress: int = 0
    claimed: bool = False

    def __iter__(self):
        yield from super().__iter__()
        yield 'name', self.name
        yield 'description', self.description
        yield 'requirement', self.requirement
        yield 'target', self.target
        yield 'progress', self.progress
        yield 'claimed', self.claimed

    @classmethod
    def from_dict(cls, value: dict) -> Self:
        return cls([GiveawayPrice.find_from_dict(price) for price in value['prices']], value['name'], value['description'], value['requirement'], value['target'], value['progress'], value['claimed'])

    @classmethod
    def generate(cls, *args, **kwargs) -> Self:
        obj = super().generate(*args, **kwargs)
        for key, val in random.choice(cls.quest_types()).items():
            setattr(obj, key, val)
        return obj

    @abstractclassmethod
    def quest_types(cls):
        ...

    @property
    def finished(self) -> bool:
        return self.progress >= self.requirement

    @property
    def id(self):
        return self.target[0]

    @property
    def target_info(self):
        return self.target[1]


@dataclasses.dataclass()
class DailyQuest(Quest):
    prices: List[Type[GiveawayPrice]]
    name: str = 'Daily Quest'
    description: str = ''
    requirement: int = 0
    target: Tuple[str, Optional[str]] | None = None
    progress: int = 0
    claimed: bool = False

    @staticmethod
    def random_prices(daily_streak: int, titles: List[Title]) -> Tuple[Dict[GiveawayPrice | None, int], ...]:
        viable_titles = [title for title in titles if title.rarity not in ('COMMON',)]
        cum_title_chances = sum(title.spawn_chance * 20 for title in viable_titles)
        return (
            {XPPrice(100): 7, XPPrice(150): 6, XPPrice(200): 5, XPPrice(250): 3, XPPrice(500): 1},
            {None: 1 - cum_title_chances} | {TitlePrice(title): title.spawn_chance * 20 for title in viable_titles}
        )

    @classmethod
    def quest_types(cls):
        con_key, con_val = random.choice(list(CONTINENT_CODE_TO_NAME.items()))
        cot_alpha2 = random.choice(list(ALPHA2_COUNTRIES))
        cot_cname = format_cname(cot_alpha2, alpha2_to_country(cot_alpha2))
        return [
            {
                'name': ':island: Island Dweller',
                'description': 'Register 30 votes for island nations',
                'requirement': 30,
                'target': ('island', None)
            },
            {
                'name': ':black_small_square: Singapura',
                'description': 'Register 30 votes for micronations',
                'requirement': 30,
                'target': ('micro', None)
            },
            {
                'name': ':earth_americas: Americo',
                'description': 'Register 20 votes for North or South American countries',
                'requirement': 20,
                'target': ('america', None)
            },
            {
                'name': ':airplane: Broad Traveller',
                'description': f'Register 20 votes for countries in {con_val}',
                'requirement': 20,
                'target': ('continent', con_key)
            },
            {
                'name': ':airplane_small: Traveller',
                'description': f'Register 20 votes for {cot_cname}',
                'requirement': 20,
                'target': ('country', cot_alpha2)
            }
        ]


@dataclasses.dataclass()
class WeeklyQuest(Quest):
    prices: List[Type[GiveawayPrice]]
    name: str = 'Weekly Quest'
    description: str = ''
    requirement: int = 0
    target: Tuple[str, Optional[str]] | None = None
    progress: int = 0
    claimed: bool = False

    @staticmethod
    def random_prices(daily_streak: int, titles: List[Title]) -> Tuple[Dict[GiveawayPrice | None, int], ...]:
        viable_titles = [title for title in titles if title.rarity not in ('COMMON',)]
        cum_title_chances = sum(title.spawn_chance * 20 for title in viable_titles)
        return (
            {XPPrice(floor(100 * (daily_streak ** .8))): 7, XPPrice(floor(150 * (daily_streak ** .8))): 6, XPPrice(floor(200 * (daily_streak ** .8))): 5, XPPrice(floor(250 * (daily_streak ** .8))): 3, XPPrice(floor(500 * (daily_streak ** .8))): 1},
            {None: 1 - cum_title_chances} | {TitlePrice(title): title.spawn_chance * 20 for title in viable_titles}
        )

