import os
from pathlib import Path
from discord import File, Embed

from data import banners_dir, flags_dir
from data.boosters import Booster

COLORED_DIR = Path(banners_dir, 'colored')
LEGACY_DIR = Path(banners_dir, 'legacy')


def get_flag_path(alpha2: str) -> Path:
    return Path(flags_dir, alpha2 + '.png')

def get_legacy_path(alpha2: str) -> Path:
    return Path(LEGACY_DIR, alpha2 + '.jpg')

def get_colored_path(alpha2: str, booster: Booster | None = None) -> Path:
    if booster is None:
        return Path(COLORED_DIR, alpha2 + '.png')
    return Path(COLORED_DIR, f'{alpha2}_{booster.id}.png')

def get_flag(alpha2: str) -> File | None:
    flag_path = get_flag_path(alpha2)
    if not flag_path.exists():
        return None
    return File(flag_path, filename=alpha2 + '.png')

def get_legacy_banner(alpha2: str) -> File | None:
    banner_path = get_legacy_path(alpha2)
    if not banner_path.exists():
        return None
    return File(banner_path, filename=alpha2 + '.jpg')

def get_banner(alpha2: str, booster: Booster | None = None) -> Path:
    colored, legacy = get_colored_path(alpha2.lower()), get_legacy_path(alpha2)
    if colored.is_file():
        booster_specific = get_colored_path(alpha2.lower(), booster)
        if booster is not None and booster_specific.is_file():
            return booster_specific
        return colored
    elif legacy.is_file():
        return legacy

    return get_flag_path(alpha2)

def format_embed(vote_args: dict, embed: Embed, alpha2: str, upload: bool = True, booster: Booster | None = None):
    banner_path = get_banner(alpha2, booster)
    if upload:
        embed.set_image(url=f'attachment://{banner_path.name}')
        vote_args['file'] = File(banner_path, filename=banner_path.name)
    else:
        embed.set_thumbnail(url=f'https://raw.githubusercontent.com/DwarflinDeveloping/FameBot/refs/heads/master/{banner_path}')
