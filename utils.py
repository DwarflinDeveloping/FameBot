import enum
from typing import Literal
import pycountry
import country_converter
from millify import millify as _millify
import pypopulation
from pycountry_convert import country_alpha2_to_continent_code

POINTS = 'points'
VOTES = 'votes'
CTYPES = Literal[POINTS, VOTES]

def sort_dict(inp_dict: dict) -> dict:
    return dict(sorted(inp_dict.items(), key=lambda item: item[1], reverse=True))

COUNTRIES_NAME_LIST = [country.name.lower() for country in pycountry.countries]
ALPHA2_TO_COUNTRY = {country.alpha_2: country.name for country in pycountry.countries}

ALTERNATIVE_CNAMES = {
    'Turkey': 'TR',
    'Russia': 'RU',
    'Bosnia': 'BA',
    'BES Islands': 'BQ'
}

def alpha2_to_country(alpha2: str) -> str:
    return ALPHA2_TO_COUNTRY[alpha2]

def country_to_alpha2(*country_names: str) -> str:
    return country_converter.convert(names=country_names, to='ISO2')

CONTINENT_CORRECTIONS = {
    'GE': 'EU',
    'VA': 'EU',
    'AQ': 'AN',
    'TF': 'AN',
    'HM': 'AN',
    'EH': 'AF',
    'PN': 'OC',
    'SX': 'NA',
    'TL': 'AS',
    'UM': 'OC'
}
def country_to_continent(alpha2: str) -> str:
    if alpha2 in CONTINENT_CORRECTIONS:
        return CONTINENT_CORRECTIONS[alpha2]
    else:
        return country_alpha2_to_continent_code(alpha2)

CONTINENT_CODE_TO_NAME = {
    'EU': 'Europe',
    'AS': 'Asia',
    'NA': 'North America',
    'SA': 'South America',
    'OC': 'Australasia',
    'AF': 'Africa',
    'AN': 'Antarctic Territories'
}

def points_per_capita(alpha2: str, point_count: int) -> float:
    pop = pypopulation.get_population_a2(alpha2)
    if pop is None:
        pop = 50
    return round(point_count / pop, 5)

def millify(n: float):
    return _millify(n, precision=3)

RANK_SYMBOLS = {1: '🥇', 2: '🥈', 3: '🥉'}
def get_rank_symbol(rank: int) -> str:
    if rank in RANK_SYMBOLS:
        return ' ' + RANK_SYMBOLS[rank]
    else:
        return ''

def format_country_ranking(c_name: str, rank: int, count: int, ctype: str, dpos: int | None = None, recap: bool = False):
    rank_symbol = get_rank_symbol(rank).lstrip()
    rank_str = rank_symbol if rank_symbol else f'\u200b {rank}.'
    dpos_str = f' {incr_symbol(dpos)}{abs(dpos)}' if dpos else ''
    amount_prefix = '+' if recap else ''
    count_str = millify(count) if ctype == POINTS else str(count)
    amount_suffix = ' pt.' if ctype == POINTS else ' vt.' if ctype == VOTES else ''
    return f'{rank_str} {c_name} ({amount_prefix}{count_str}{amount_suffix}){dpos_str}'

CNAME_IMPROVEMENTS = {
    'Russian Federation': 'Russia',
    'Bonaire, Sint Eustatius and Saba': 'BES Islands'
}
def improve_cname(cname: str):
    return CNAME_IMPROVEMENTS[cname] if cname in CNAME_IMPROVEMENTS else cname

def format_cname(alpha2: str, cname: str) -> str:
    return f'{improve_cname(cname)} :flag_{alpha2.lower()}:'

def incr_symbol(incr: int) -> str:
    symbol = '▼' if incr < 0 else '▲' if incr > 0 else ''
    return symbol
