import dataclasses
from abc import ABC, abstractmethod, abstractclassmethod, abstractproperty, abstractstaticmethod
import random
from math import floor
from typing import Type, List, Self, Tuple, Dict

from data.boosters import Booster, DailyBooster, TurboBooster, VoteBooster
from data.titles import Title
from data.users import FameUser


@dataclasses.dataclass(frozen=True)
class GiveawayPrice(ABC):
    @abstractmethod
    def __str__(self) -> str:
        ...

    @abstractmethod
    def __iter__(self):
        yield 'name', self.__class__.__name__

    @abstractmethod
    def apply(self, user: FameUser) -> None:
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
        return f'{self.value} XP'

    def __iter__(self):
        yield from super().__iter__()
        yield 'value', self.value

    def apply(self, user: FameUser) -> None:
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

    def apply(self, user: FameUser) -> None:
        user.add_booster(self.booster, self.amount)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        booster = Booster.from_dict(data['booster']).__class__
        return cls(booster, data['amount'])

@dataclasses.dataclass(frozen=True)
class TitlePrice(GiveawayPrice):
    title: Title

    def __str__(self) -> str:
        return self.title.name

    def __iter__(self):
        yield from super().__iter__()
        yield 'title', dict(self.title)

    def apply(self, user: FameUser) -> None:
        user.add_title(self.title)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(Title(data['name'], data['rarity']))

price_types = (BoosterPrice, XPPrice)

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

    def apply(self, user: FameUser) -> None:
        for price in self.prices:
            price.apply(user)


@dataclasses.dataclass()
class Giveaway(PriceList):
    prices: List[Type[GiveawayPrice]]

    @staticmethod
    def random_prices() -> Tuple[Dict[GiveawayPrice | None, int], ...]:
        return \
            {XPPrice(500): 7, XPPrice(750): 6, XPPrice(1000): 5, XPPrice(1500): 3, XPPrice(2500): 1}, \
            {None: 5, BoosterPrice(TurboBooster, 1): 3, BoosterPrice(TurboBooster, 3): 1}, \
            {BoosterPrice(VoteBooster, 1): 3, BoosterPrice(VoteBooster, 2): 3, BoosterPrice(VoteBooster, 3): 1}, \
            {BoosterPrice(DailyBooster): 1}


@dataclasses.dataclass()
class StreakReward(PriceList):
    prices: List[Type[GiveawayPrice]]

    @staticmethod
    def random_prices(daily_streak: int, titles: List[Title]) -> Tuple[Dict[GiveawayPrice | None, int], ...]:
        viable = [title for title in titles if title.rarity not in ('COMMON', 'RARE')]
        return \
            {XPPrice(floor(100 * (daily_streak ** .8))): 7, XPPrice(floor(150 * (daily_streak ** .8))): 6, XPPrice(floor(200 * (daily_streak ** .8))): 5, XPPrice(floor(250 * (daily_streak ** .8))): 3, XPPrice(floor(500 * (daily_streak ** .8))): 1}, \
            {None: 5, BoosterPrice(TurboBooster, 1): 1}, \
            {None: 1, BoosterPrice(DailyBooster): 1}, \
            {None: 1 - sum(title.spawn_chance * 20 for title in viable)} | {TitlePrice(title): title.spawn_chance * 20 for title in viable}
