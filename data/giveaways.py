import dataclasses
from abc import ABC, abstractmethod, abstractclassmethod
import random
from typing import Type, List, Self

from data.boosters import Booster, DailyBooster, TurboBooster, VoteBooster
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

price_types = (BoosterPrice, XPPrice)

XP_PRICES = {XPPrice(500): 7, XPPrice(750): 6, XPPrice(1000): 5, XPPrice(1500): 3, XPPrice(2500): 1}
BOOSTER_PRICES_1 = {None: 5, BoosterPrice(TurboBooster, 1): 3, BoosterPrice(TurboBooster, 3): 1}
BOOSTER_PRICES_2 = {BoosterPrice(VoteBooster, 1): 3, BoosterPrice(VoteBooster, 2): 3, BoosterPrice(VoteBooster, 3): 1}
BOOSTER_PRICES_3 = {BoosterPrice(DailyBooster): 1}

RANDOM_PRICES = (XP_PRICES, BOOSTER_PRICES_1, BOOSTER_PRICES_2, BOOSTER_PRICES_3)

def generate_prices() -> List[Type[GiveawayPrice]]:
    prices = []
    for category in RANDOM_PRICES:
        price = random.choices(list(category.keys()), weights=list(category.values()), k=1)[0]
        if price:
            prices.append(price)
    return prices


@dataclasses.dataclass()
class Giveaway:
    prices: List[Type[GiveawayPrice]]

    @classmethod
    def generate(cls) -> Self:
        return cls(generate_prices())

    def __str__(self) -> str:
        return '\n'.join([f'- {price}' for price in self.prices])

    def __iter__(self):
        yield 'prices', [dict(price) for price in self.prices]

    @classmethod
    def from_dict(cls, value: dict) -> Self:
        return cls([GiveawayPrice.find_from_dict(price) for price in value['prices']])

    def apply(self, user: FameUser) -> None:
        for price in self.prices:
            price.apply(user)
