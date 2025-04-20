import json
from pathlib import Path
import pycountry

data_path = Path('data.json')
flags_dir = Path('flags')

DATA_PRESET = {
    'total': {country.alpha_2: {'votes': 0, 'points': 0} for country in pycountry.countries},
    'recap': {scope: {country.alpha_2: {'votes': 0, 'points': 0, 'dpos_votes': 0, 'dpos_points': 0} for country in pycountry.countries} for scope in ['daily', 'weekly', 'monthly']},
    'daily_claims': {},
    'maintenance': False,
    'admins': [784473264755834880]
}

def load_data() -> dict:
    if data_path.exists():
        return json.loads(data_path.read_text())
    else:
        return DATA_PRESET

def save_data(value: dict) -> None:
    data_path.write_text(json.dumps(value, indent=2))
