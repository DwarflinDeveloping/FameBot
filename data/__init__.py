import json
import os
from copy import deepcopy
from typing import List
import pycountry
from pathlib import Path

PV_PRESET = {'votes': 0, 'points': 0}
DPV_PRESET = PV_PRESET | {'dpos_votes': 0, 'dpos_points': 0}
COUNTRY_DATA_PRESET = {country.alpha_2: PV_PRESET.copy() for country in pycountry.countries}

APP_DATA_PRESET = {
    'maintenance': False,
    'admins': [784473264755834880],
    'progression_roles': {
        0: 1363309917926064210,   # Bronze 1
        10: 1363920859953103140,  # Bronze 2
        20: 1363921907497308314,  # Bronze 3
        30: 1363310545108996238,  # Silver 1
        40: 1363922324612448469,  # Silver 2
        50: 1363922416111321478,  # Silver 3
        60: 1363310802060447804,  # Gold 1
        70: 1363310895580709017,  # Gold 2
        80: 1363311104364773596,  # Gold 3
        90: 1363311311924101180,  # Diamond 1
        100: 1363311794533437540, # Diamond 2
        110: 1363312217298305304, # Diamond 3
        120: 1363312348424568932, # Mythic 1
        130: 1363312436232323123, # Mythic 2
        140: 1363312587449569551, # Mythic 3
        150: 1363312813531070595, # Legendary 1
        170: 1363312962009301202, # Legendary 2
        190: 1363313105165095175, # Legendary 3
        210: 1363313333511389296, # Masters 1
        230: 1363922924066832504, # Masters 2
        250: 1363923020774641916, # Masters 3
        270: 1363323340764479620  # Pro Member
    },
    'recap_channels': {
        'daily': 1363171417612353658,
        'weekly': 1363171435962433768,
        'seasonal': 1363171461954670632
    }
}

USER_DATA_PRESET = {
    'total': deepcopy(PV_PRESET),
    'alltime_country': {},
    'leveling': {
        'vote_xp': 0,
        'additional_xp': 0,
    },
    'next_vote': None,
    'daily_claim': None,
    'claims': [],
    'boosters': {},
    'active_booster': None
}

RECAP_DATA_PRESET = {
    'start_timestamp': None,
    'country': {}
}

data_path = Path('data.json')
trivia_path = Path('trivia.csv')

flags_dir = Path('flags')
banners_dir = Path('banners')
images_dir = Path('images')

users_dir = Path('users')
recaps_dir = Path('recaps')
exports_dir = Path('exports')

all_dirs = (flags_dir, banners_dir, users_dir, images_dir, recaps_dir, exports_dir)

def make_dirs() -> None:
    for dir_path in all_dirs:
        dir_path.mkdir(exist_ok=True)

def load_app_data() -> dict:
    if data_path.exists():
        return json.loads(data_path.read_text())
    else:
        return deepcopy(APP_DATA_PRESET)

def save_app_data(value: dict) -> None:
    data_path.write_text(json.dumps(value, indent=2))

def clear_folder(dir_path: os.PathLike):
    for file in os.listdir(dir_path):
        os.remove(Path(dir_path, file))

def clear_database(users: bool = False, recaps: List[str] | bool = False):
    if users is True:
        clear_folder(users_dir)
    if type(recaps) == bool and recaps is True:
        clear_folder(recaps_dir)
    elif type(recaps) == list:
        for scope in recaps:
            Path(recaps_dir, f'{scope}.json').unlink(missing_ok=True)
