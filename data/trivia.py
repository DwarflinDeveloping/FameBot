from functools import lru_cache
from typing import Dict

import requests
from pandas import DataFrame, read_csv

from data import trivia_path


def load_trivia() -> DataFrame:
    if not trivia_path.is_file():
        print('Downloading trivia file...')
        csv_text = requests.get('https://joshuaproject.net/resources/datasets/4').text
        if 'Joshua Project People Group Data' in csv_text.splitlines()[0]:
            csv_text = '\n'.join(csv_text.splitlines()[2:])
        trivia_path.write_text(csv_text)
    return read_csv(trivia_path)

def get_mappings(df: DataFrame, category: str) -> Dict[str, str]:
    return df.groupby('ISO2')[category].agg(lambda x: x.value_counts().idxmax() if not x.dropna().empty else None).to_dict()
