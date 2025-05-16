import dataclasses
from functools import lru_cache
from typing import Dict, List

import requests
from pandas import DataFrame, read_csv

from data import trivia_path
from utils import alpha2_to_country, ALPHA2_TO_COUNTRY, format_cname, CNAME_IMPROVEMENTS


@dataclasses.dataclass(frozen=True)
class Country:
    alpha2: str
    rog3: str = None
    alpha3: str = None
    base_name: str = None
    population: int = None
    # CntPeoples: str = None
    # CntPeoplesLR: str = None
    # PoplPeoplesLR: str = None
    # JPScaleCtry: str = None
    language_code: str = None
    language: str = None
    religion_code: int = None
    religion: str = None
    christian_portion: float = None
    evangelical_portion: float = None
    # 10_40Window: str = None
    rog2: str = None
    continent: str = None
    region_code: int = None
    region: str = None
    urbanized_portion: float = None
    literacy_rate: float = None
    # WorkersNeeded: str = None

    def __str__(self):
        return self.alpha2

    @property
    def name(self) -> str:
        return ALPHA2_TO_COUNTRY.get(self.alpha2, 'unknown')

    @property
    def improved_cname(self) -> str:
        return CNAME_IMPROVEMENTS[self.name] if self.name in CNAME_IMPROVEMENTS else self.name

    @property
    def visual_name(self) -> str:
        return f'{self.improved_cname} :flag_{self.alpha2.lower()}:'


class TriviaManager:
    def __init__(self):
        self.df = self.load_data()
        self.countries: Dict[str, Country] = {}
        self.mappings = {}
        self.key_to_vals = {}

        self.update()

    @staticmethod
    def load_data() -> DataFrame:
        if not trivia_path.is_file():
            print('Downloading trivia file...')
            csv_text = requests.get('https://joshuaproject.net/resources/datasets/4').text
            if 'Joshua Project People Group Data' in csv_text.splitlines()[0]:
                csv_text = '\n'.join(csv_text.splitlines()[2:])
            trivia_path.write_text(csv_text)
        return read_csv(trivia_path)

    def get_country(self, alpha2: str) -> Country:
        if alpha2 in self.countries:
            return self.countries.get(alpha2)

        kwargs = {
            'alpha2': 'ISO2',
            'rog3': 'ROG3',
            'alpha3': 'ISO3',
            'base_name': 'Ctry',
            'population': 'PoplPeoples',
            # 'CntPeoples': 'CntPeoples',
            # 'CntPeoplesLR': 'CntPeoplesLR',
            # 'PoplPeoplesLR': 'PoplPeoplesLR',
            # 'JPScaleCtry': 'JPScaleCtry',
            'language_code': 'ROL3OfficialLanguage',
            'language': 'OfficialLang',
            'religion_code': 'RLG3Primary',
            'religion': 'ReligionPrimary',
            'christian_portion': 'PercentChristianity',
            'evangelical_portion': 'PercentEvangelical',
            'rog2': 'ROG2',
            'continent': 'Continent',
            'region_code': 'RegionCode',
            'region': 'RegionName',
            'urbanized_portion': 'PercentUrbanized',
            'literacy_rate': 'LiteracyRate',
            # 'WorkersNeeded': 'WorkersNeeded',
        }
        for field in dataclasses.fields(Country):
            category = kwargs.get(field.name, None)
            val = self.get_base_country(alpha2, category)
            if category is None or val is None:
                continue
            kwargs[field.name] = field.type(self.get_base_country(alpha2, category))

        country = Country(**kwargs)
        self.countries[alpha2] = country
        return country

    def generate_mappings(self, category: str) -> Dict[Country, str]:
        return self.df.groupby('ISO2')[category].agg(
            lambda x: x.value_counts().idxmax() if not x.dropna().empty else None
        ).to_dict()

    def get_mappings(self, category: str) -> Dict[Country, str]:
        return self.mappings.get(category)

    def get_values(self, category: str) -> List[str]:
        return self.key_to_vals.get(category)

    def get_base_country(self, alpha2: str, category: str):
        return self.mappings.get(category).get(alpha2, None)

    def update(self):
        for category in self.df.keys():
            self.mappings[category] = self.generate_mappings(category)

        for category, values in self.mappings.items():
            self.key_to_vals[category] = set(values.values())
