import dataclasses
import random
import string
from abc import ABC, abstractclassmethod
from typing import List, Type, Tuple, Dict, Self, Iterable

from data.prices import GiveawayPrice, XPPrice, TitlePrice
from data.prices.giveaways import PriceList
from data.titles import Title
from data.trivia import TriviaManager, Country
from utils import ALPHA2_ISLAND_NATIONS, ALPHA2_LANDLOCKED, CONTINENT_CODE_TO_NAME, \
    ALPHA2_MICRO_NATIONS, ALPHA2_COUNTRIES, format_cname, alpha2_to_country, POLAR_COUNTRIES, EU_COUNTRIES, \
    WAR_COUNTRIES, DESERT_COUNTRIES


@dataclasses.dataclass()
class Quest(PriceList, ABC):
    id: str
    base_symbol: str
    name: str
    description: str
    requirement: int

    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    def __iter__(self):
        yield 'id', self.id
        yield from super().__iter__()
        if self.target is not None:
            yield 'target', str(self.target)
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
    def generate(cls, trivia: TriviaManager, quest_type: Type[Self] | None = None, *args, **kwargs) -> Self:
        prices = cls.generate_prices(*args, **kwargs)
        if quest_type is None:
            quest_type = random.choice(daily_quests)

        targets = quest_type.get_targets(trivia)
        return quest_type(prices, target=random.choice(list(targets)) if targets else None)

    @classmethod
    def get_targets(self, trivia: TriviaManager) -> Iterable[str] | None:
        return None

    def get_countries(self, trivia: TriviaManager) -> Iterable[str]:
        yield self.target

    def apply(self, user) -> None:
        super().apply(user, is_giveaway=False)
        user.add_quest_completion(self.id)

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
    def formatted_target(self) -> str:
        return self.target

    @property
    def formatted_description(self) -> str:
        return self.description.format(count=self.requirement, target=self.formatted_target)


@dataclasses.dataclass()
class DailyQuest(Quest, ABC):
    id: str
    base_symbol: str
    name: str
    description: str
    requirement: int

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
    description: str = 'Register {count} votes for **island nations**'
    requirement: int = 30

    @classmethod
    def get_countries(cls, trivia: TriviaManager) -> Iterable[str]:
        return ALPHA2_ISLAND_NATIONS

@dataclasses.dataclass()
class LandlockedQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'landlocked'
    base_symbol: str = ':mount_fuji:'
    name: str = 'Mountain Dweller'
    description: str = 'Register {count} votes for **landlocked nations**'
    requirement: int = 25

    @classmethod
    def get_countries(cls, trivia: TriviaManager) -> Iterable[str]:
        return ALPHA2_LANDLOCKED


@dataclasses.dataclass()
class CoastlineQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'coastline'
    base_symbol: str = ':beach:'
    name: str = 'Beach Enjoyer'
    description: str = 'Register {count} votes for **nations with a coastline**'
    requirement: int = 25

    @classmethod
    def get_countries(cls, trivia: TriviaManager) -> Iterable[str]:
        for alpha2 in ALPHA2_COUNTRIES:
            if alpha2 not in ALPHA2_LANDLOCKED:
                yield alpha2


@dataclasses.dataclass()
class PolarQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'landlocked'
    base_symbol: str = ':ice_cube:'
    name: str = 'Polar Explorer'
    description: str = 'Register {count} votes for **landlocked nations**'
    requirement: int = 25

    @classmethod
    def get_countries(cls, trivia: TriviaManager) -> Iterable[str]:
        return POLAR_COUNTRIES


@dataclasses.dataclass()
class MicroQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'micro'
    base_symbol: str = ':golf:'
    name: str = 'Singapura'
    description: str = 'Register {count} votes for **micronations**'
    requirement: int = 30

    @classmethod
    def get_countries(cls, trivia: TriviaManager) -> Iterable[str]:
        return ALPHA2_MICRO_NATIONS


@dataclasses.dataclass()
class AmericasQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'americas'
    base_symbol: str = ':earth_americas:'
    name: str = 'Americo'
    description: str = 'Register {count} votes for countries in **North or South America**'
    requirement: int = 30

    @classmethod
    def get_targets(cls, trivia: TriviaManager) -> Iterable[str]:
        yield 'North America'
        yield 'South America'

    def get_countries(self, trivia: TriviaManager) -> Iterable[str]:
        for alpha2 in ALPHA2_COUNTRIES:
            if trivia.get_base_country(alpha2, 'Continent') in self.get_targets(trivia):
                yield alpha2


@dataclasses.dataclass()
class ContinentQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'continent'
    base_symbol: str = ':airplane:'
    name: str = 'Traveller'
    description: str = 'Register {count} votes for countries in **{target}**'
    requirement: int = 20

    @classmethod
    def get_targets(cls, trivia: TriviaManager) -> Iterable[str]:
        return trivia.get_values('Continent')

    def get_countries(self, trivia: TriviaManager) -> Iterable[str]:
        for alpha2 in ALPHA2_COUNTRIES:
            if trivia.get_base_country(alpha2, 'Continent') == self.target:
                yield alpha2

@dataclasses.dataclass()
class CountryQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'country'
    base_symbol: str = ':small_airplane:'
    name: str = 'Visitor'
    description: str = 'Register {count} votes for countries for **{target}**'
    requirement: int = 15

    @property
    def formatted_target(self) -> str:
        return format_cname(self.target, alpha2_to_country(self.target))

    @classmethod
    def get_targets(cls, trivia: TriviaManager) -> Iterable[str]:
        return ALPHA2_COUNTRIES


@dataclasses.dataclass()
class ReligionQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'religion'
    base_symbol: str = ':church:'
    name: str = 'Missionary'
    description: str = 'Register {count} votes for countries with the religion **{target}**'
    requirement: int = 30

    @property
    def symbol(self) -> str:
        if self.target == 'Christianity':
            return ':church:'
        elif self.target == 'Islam':
            return ':star_and_crescent:'
        return self.base_symbol

    @classmethod
    def get_targets(cls, trivia: TriviaManager) -> Iterable[str]:
        for religion in trivia.get_values('ReligionPrimary'):
            if religion not in ('Ethnic Religions',):
                yield religion

    def get_countries(self, trivia: TriviaManager) -> Iterable[str]:
        for alpha2 in ALPHA2_COUNTRIES:
            if trivia.get_base_country(alpha2, 'ReligionPrimary') == self.target:
                yield alpha2


@dataclasses.dataclass()
class EUQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'eu'
    base_symbol: str = ':flag_eu:'
    name: str = 'Europaya'
    description: str = 'Register {count} votes for member nations of the **European Union (EU)**'
    requirement: int = 30

    def get_countries(self, trivia: TriviaManager) -> Iterable[str]:
        return EU_COUNTRIES


@dataclasses.dataclass()
class WarQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'war'
    base_symbol: str = ':briefcase:'
    name: str = 'Diplomat'
    description: str = 'Register {count} votes for countries that are currently **at war**'
    requirement: int = 30

    def get_countries(self, trivia: TriviaManager) -> Iterable[str]:
        return WAR_COUNTRIES


@dataclasses.dataclass()
class DesertQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'desert'
    base_symbol: str = ':desert:'
    name: str = 'Desert Fox'
    description: str = 'Register {count} votes for countries that are mostly covered with **deserts**'
    requirement: int = 35

    def get_countries(self, trivia: TriviaManager) -> Iterable[str]:
        return DESERT_COUNTRIES


@dataclasses.dataclass()
class LetterQuest(DailyQuest):
    prices: List[Type[GiveawayPrice]]
    progress: int = 0
    claimed: bool = False
    target: str | None = None

    id: str = 'letter'
    base_symbol: str = ':regional_indicator_a:'
    name: str = 'Picky Voter'
    description: str = 'Register {count} votes for countries that start with the letter **{target}**'
    requirement: int = 30

    @property
    def symbol(self) -> str:
        return f':regional_indicator_{self.target.lower()}:'

    @classmethod
    def get_targets(cls, trivia: TriviaManager) -> Iterable[str]:
        return string.ascii_uppercase

    def get_countries(self, trivia: TriviaManager) -> Iterable[str]:
        for alpha2 in ALPHA2_COUNTRIES:
            if alpha2.upper().startswith(self.target):
                yield alpha2


daily_quests = IslandQuest, LandlockedQuest, MicroQuest, AmericasQuest, ContinentQuest, CountryQuest, ReligionQuest, \
               EUQuest, WarQuest, DesertQuest, LetterQuest, PolarQuest, CoastlineQuest

S2_W1_DATA = {
    'sunbather': (':sunrise: Sunbather', 'Use the /daily command 20 times on countries affected by the **Solar Flare**', 20),
    'firedust_shop': (':sparkles: Shopping Spree', 'Purchase boosters worth 5,000 :sparkles: Fire Dust', 5000),
    'firepower_master': (':thunder_cloud_rain: Master of Disaster', 'Use 10 Masters Firepowers', 10),
}
