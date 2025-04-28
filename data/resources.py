from pathlib import Path
from discord import File

from data import banners_dir, flags_dir


def get_flag_path(alpha2: str):
    return Path(flags_dir, alpha2 + '.png')

def get_banner_path(alpha2: str):
    return Path(banners_dir, alpha2 + '.jpg')

def get_flag(alpha2: str) -> File | None:
    flag_path = get_flag_path(alpha2)
    if not flag_path.exists():
        return None
    return File(flag_path, filename=alpha2 + '.png')

def get_banner(alpha2: str) -> File | None:
    banner_path = get_banner_path(alpha2)
    if not banner_path.exists():
        return None
    return File(banner_path, filename=alpha2 + '.jpg')
