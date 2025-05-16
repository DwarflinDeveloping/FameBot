import dataclasses
from math import floor
from typing import Type, List, Self, Tuple, Dict

from data.boosters import Booster, DailyBooster, GoldBooster, BronzeBooster, SilverBooster
from data.prices import BoosterPrice, XPPrice, TitlePrice, PriceList, GiveawayPrice
from data.titles import Title

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
