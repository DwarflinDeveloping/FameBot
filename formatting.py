import datetime

from discord import Embed, User, Colour

from data.boosters import Booster
from data.prices.giveaways import StreakReward
from data.titles import Title


def get_base_embed(user: User, title: str, error: bool = False, **kwargs) -> Embed:
    embed = Embed(
        title=title,
        timestamp=datetime.datetime.now(datetime.UTC),
        color=kwargs['color'] if 'color' in kwargs else Colour.red() if error else Colour.light_grey(),
        **kwargs
    )
    embed.set_footer(
        text=user.name,
        icon_url=user.avatar.url if user.avatar else user.default_avatar.url
    )
    return embed

def get_booster_embed(booster: Booster) -> Embed:
    embed = Embed(
        title=f':mag_right: You have found a {booster.format_name()} ({booster.format_boost()})!',
        colour=booster.color,
        description=f'This booster lasts for {booster.format_duration()} votes.\n'
                    'View your boosters using **/boosters**'
    )
    return embed

def get_title_embed(title: Title, compensation: bool = False) -> Embed:
    if compensation:
        descr1 = f'Since you already have this title, you instead get {title.compensation}xp.'
    else:
        descr1 = f'This title will make you gain {title.xp_incr} more xp per vote permanently.'
    embed = Embed(
        title=f':speech_balloon: You have found a {title.formatted_rarity} title: {title.name}!',
        colour=title.color,
        description=descr1 + '\nView your title collection using **/titles**'
    )
    return embed

def get_streak_embed(reward: StreakReward) -> Embed:
    return Embed(
        title=f':gift: Daily streak completed!',
        description=f'You have been granted the following rewards:\n{reward}'
    )
