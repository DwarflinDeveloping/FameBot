import dataclasses
from abc import ABC, abstractmethod, abstractclassmethod, abstractproperty, abstractstaticmethod
import random
from math import floor
from typing import Type, List, Self, Tuple, Dict, Optional

from pandas.core.interchange.dataframe_protocol import DataFrame

from data.boosters import Booster, DailyBooster, GoldBooster, BronzeBooster, SilverBooster
from data.titles import Title
from data.trivia import get_mappings
from utils import CONTINENT_CODE_TO_NAME, ALPHA2_COUNTRIES, format_cname, alpha2_to_country, ALPHA2_ISLAND_NATIONS, \
    ALPHA2_MICRO_NATIONS, country_to_continent, ALPHA2_LANDLOCKED


@dataclasses.dataclass(frozen=True)
class GiveawayPrice(ABC):
    @abstractmethod
    def __str__(self) -> str:
        ...

    @abstractmethod
    def __iter__(self):
        yield 'name', self.__class__.__name__

    @abstractmethod
    def apply(self, user, **kwargs) -> None:
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

    def apply(self, user, is_giveaway: bool) -> None:
        if is_giveaway:
            user.giveaway_xp += self.value
        else:
            user.quest_xp += self.value

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

    def apply(self, user, *_) -> None:
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

    def apply(self, user, *_) -> None:
        user.add_title(self.title)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(Title(data['title']['name'], data['title']['rarity']))

price_types = (BoosterPrice, XPPrice, TitlePrice)

@dataclasses.dataclass()
class PriceList(ABC):
    prices: List[Type[GiveawayPrice]]

    @abstractclassmethod
    def from_dict(cls, value: dict) -> Self:
        ...

    @abstractstaticmethod
    def random_prices(*args, **kwargs) -> Tuple[Dict[GiveawayPrice | None, int], ...]:
        ...

    @classmethod
    def generate_prices(cls, *args, **kwargs) -> List[Type[GiveawayPrice]]:
        prices = []
        for category in cls.random_prices(*args, **kwargs):
            price = random.choices(list(category.keys()), weights=list(category.values()), k=1)[0]
            if price:
                prices.append(price)
        return prices

    @classmethod
    def generate(cls, *args, **kwargs):
        return cls(cls.generate_prices(*args, **kwargs))

    def __str__(self) -> str:
        return '\n'.join([f'- {price}' for price in self.prices])

    def __iter__(self):
        yield 'prices', [dict(price) for price in self.prices]

    def apply(self, user, is_giveaway: bool = True) -> None:
        for price in self.prices:
            price.apply(user, is_giveaway)


@dataclasses.dataclass()
class Giveaway(PriceList):
    prices: List[Type[GiveawayPrice]]

    @classmethod
    def from_dict(cls, value: dict) -> Self:
        return cls([GiveawayPrice.find_from_dict(price) for price in value['prices']])

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

    @classmethod
    def from_dict(cls, value: dict) -> Self:
        return cls([GiveawayPrice.find_from_dict(price) for price in value['prices']])

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
    id: str
    base_symbol: str
    name: str
    description: str
    requirement: int
    random_values: List[str]

    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    def __iter__(self):
        yield 'id', self.id
        yield from super().__iter__()
        if self.target is not None:
            yield 'target', self.target
        yield 'progress', self.progress
        yield 'claimed', self.claimed

    @classmethod
    def find_from_dict(cls, value: dict) -> Type[Self]:
        return daily_quests[[quest.id for quest in daily_quests].index(value['id'])]

    @classmethod
    def from_dict(cls, value: dict) -> Self:
        return cls.find_from_dict(value)(prices=[GiveawayPrice.find_from_dict(price) for price in value['prices']],
                                         target=value.get('target', None),
                                         progress=value['progress'],
                                         claimed=value['claimed'],)

    @classmethod
    def generate(cls, df: DataFrame, quest_type: Type[Self] | None = None, *args, **kwargs) -> Self:
        prices = cls.generate_prices(*args, **kwargs)
        if quest_type is None:
            quest_type = random.choice(daily_quests)

        if quest_type == IslandQuest:
            random_values = ALPHA2_ISLAND_NATIONS
        elif quest_type == LandlockedQuest:
            random_values = ALPHA2_LANDLOCKED
        elif quest_type == MicroQuest:
            random_values = ALPHA2_MICRO_NATIONS
        elif quest_type == ContinentQuest:
            random_values = list(CONTINENT_CODE_TO_NAME.keys())
        elif quest_type == CountryQuest:
            random_values = ALPHA2_COUNTRIES
        elif quest_type == ReligionQuest:
            random_values = [key for key in set(get_mappings(df, 'ReligionPrimary').values()) if key not in ('Ethnic Religions',)]
        elif quest_type == AmericasQuest:
            random_values = [alpha2 for alpha2 in ALPHA2_COUNTRIES if country_to_continent(alpha2) in ['NA', 'SA']]
        else:
            random_values = None
        return quest_type(prices, target = random.choice(random_values) if random_values else None)

    def apply(self, user) -> None:
        super().apply(user, is_giveaway=False)

    @property
    def finished(self) -> bool:
        return self.progress >= self.requirement

    @property
    def symbol(self) -> str:
        return self.base_symbol

    @property
    def formatted_name(self) -> str:
        return ' '.join((self.symbol, self.name))

    @property
    def formatted_description(self) -> str:
        return self.description


@dataclasses.dataclass()
class DailyQuest(Quest):
    id: str
    base_symbol: str
    name: str
    description: str
    requirement: int
    random_values: List[str]

    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    @staticmethod
    def random_prices(daily_streak: int, titles: List[Title]) -> Tuple[Dict[GiveawayPrice | None, int], ...]:
        viable_titles = [title for title in titles if title.rarity not in ('COMMON',)]
        cum_title_chances = sum(title.spawn_chance * 20 for title in viable_titles)
        return (
            {XPPrice(100): 7, XPPrice(150): 6, XPPrice(200): 5, XPPrice(250): 3, XPPrice(500): 1},
            {None: 1 - cum_title_chances} | {TitlePrice(title): title.spawn_chance * 20 for title in viable_titles}
        )


@dataclasses.dataclass()
class IslandQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'island'
    base_symbol: str = ':map:'
    name: str = 'Island Dweller'
    description: str = 'Register 30 votes for **island nations**'
    requirement: int = 30
    random_values: List[str] = None


@dataclasses.dataclass()
class LandlockedQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'landlocked'
    base_symbol: str = ':mount_fuji:'
    name: str = 'Mainland Dweller'
    description: str = 'Register 25 votes for **landlocked nations**'
    requirement: int = 25
    random_values: List[str] = None


@dataclasses.dataclass()
class MicroQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'micro'
    base_symbol: str = ':island:'
    name: str = 'Singapura'
    description: str = 'Register 30 votes for **micronations**'
    requirement: int = 30
    random_values: List[str] = dataclasses.field(default_factory=lambda: ALPHA2_MICRO_NATIONS)


@dataclasses.dataclass()
class AmericasQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'americas'
    base_symbol: str = ':earth_americas:'
    name: str = 'Americo'
    description: str = 'Register 30 votes for countries in **North or South America**'
    requirement: int = 30
    random_values: List[str] = None


@dataclasses.dataclass()
class ContinentQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'continent'
    base_symbol: str = ':airplane:'
    name: str = 'Broad Traveller'
    description: str = 'Register 30 votes for countries in **{}**'
    requirement: int = 30
    random_values: List[str] = None

    @property
    def formatted_description(self) -> str:
        return self.description.format(CONTINENT_CODE_TO_NAME.get(self.target, 'unknown'))

@dataclasses.dataclass()
class CountryQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'country'
    base_symbol: str = ':small_airplane:'
    name: str = 'Traveller'
    description: str = 'Register 20 votes for countries for **{}**'
    requirement: int = 20
    random_values: List[str] = None

    @property
    def formatted_description(self) -> str:
        return self.description.format(format_cname(self.target, alpha2_to_country(self.target)))


@dataclasses.dataclass()
class ReligionQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'religion'
    base_symbol: str = ':church:'
    name: str = 'Missionary'
    description: str = 'Register 30 votes for countries with {}'
    requirement: int = 30
    random_values: List[str] = None

    @property
    def symbol(self) -> str:
        if self.target == 'Christianity':
            return ':church:'
        elif self.target == 'Islam':
            return ':star_and_crescent:'
        return self.base_symbol

    @property
    def formatted_description(self):
        return self.description.format(CONTINENT_CODE_TO_NAME.get(self.target, ''))

daily_quests = IslandQuest, LandlockedQuest, MicroQuest, AmericasQuest, ContinentQuest, CountryQuest, ReligionQuest
