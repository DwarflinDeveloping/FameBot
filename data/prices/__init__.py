import dataclasses
import random
from abc import ABC, abstractmethod, abstractclassmethod, abstractstaticmethod
from typing import Self, Type, List, Tuple, Dict

from data.boosters import Booster
from data.titles import Title


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
        if not user.has_title(self.title.name):
            user.add_title(self.title)
        else:
            user.title_dupl_xp += self.title.compensation

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
