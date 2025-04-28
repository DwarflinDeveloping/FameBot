import csv
import dataclasses
import json
import os
from copy import deepcopy
from pathlib import Path
from time import time
from typing import Self

from data import recaps_dir, RECAP_DATA_PRESET, COUNTRY_DATA_PRESET, DPV_PRESET, exports_dir
from utils import alpha2_to_country


@dataclasses.dataclass
class FameRecap:
    data: dict
    scope: str

    @classmethod
    def from_file(cls, scope: str) -> Self:
        file_path = Path(recaps_dir, f'{scope}.json')
        if file_path.is_file():
            recap_data = json.loads(file_path.read_text())
            for key, preset_val in RECAP_DATA_PRESET.items():
                if key not in recap_data:
                    recap_data[key] = deepcopy(preset_val)
        else:
            recap_data = deepcopy(RECAP_DATA_PRESET)
            if scope == 'alltime':
                recap_data['country'] = deepcopy(COUNTRY_DATA_PRESET)
            recap_data['start_timestamp'] = time()
        return cls(recap_data, scope)

    @property
    def file_path(self) -> Path:
        return Path(recaps_dir, f'{self.scope}.json')

    def save(self):
        self.file_path.write_text(json.dumps(self.data, indent=2))

    @property
    def start_timestamp(self) -> float:
        return self.data['start_timestamp']

    @start_timestamp.setter
    def start_timestamp(self, value: float) -> None:
        self.data['start_timestamp'] = value

    def get(self, alpha2: str):
        return self.data['country'][alpha2] if alpha2 in self.data['country'] else DPV_PRESET.copy()

    def add(self, alpha2: str, points: int = 0, votes: int = 0, **kwargs):
        c_data = self.get(alpha2)
        c_data['votes'] += votes
        c_data['points'] += points
        for a, b in kwargs.items():
            c_data[a] += b
        self.data['country'][alpha2] = c_data

    def set(self, alpha2: str, points: int = 0, votes: int = 0, **kwargs):
        c_data = self.get(alpha2)
        c_data['votes'] = votes
        c_data['points'] = points
        for a, b in kwargs.items():
            c_data[a] = b
        self.data['country'][alpha2] = c_data

def save_data(scope: str, name: str | int, data: dict) -> None:
    folder = Path(exports_dir, scope)
    os.makedirs(folder, exist_ok=True)

    json_path, csv_path = Path(folder, f'{name}.json'), Path(folder, f'{name}.csv')
    json_path.write_text(json.dumps(data, indent=2))

    with open(csv_path, 'w+', newline='') as f:
        w = csv.DictWriter(f, ['alpha2', 'cname'] + list(list(data['country'].values())[0].keys()))
        w.writeheader()
        for alpha2 in data['country']:
            cname = alpha2_to_country(alpha2)
            w.writerow({'alpha2': alpha2, 'cname': cname} | data['country'][alpha2])
