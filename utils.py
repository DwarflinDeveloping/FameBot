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

ALPHA2_TO_COUNTRY = {country.alpha_2: country.name for country in pycountry.countries}
ALPHA2_COUNTRIES, CNAMES = list(ALPHA2_TO_COUNTRY.keys()), list(ALPHA2_TO_COUNTRY.values())

ALTERNATIVE_CNAMES = {
    'Turkey': 'TR',
    'Russia': 'RU',
    'Bosnia': 'BA',
    'BES Islands': 'BQ',
    'Micronesia': 'FM',
    'Iran': 'IR',
    'North Korea': 'KP',
    'South Korea': 'KR',
    'Moldova': 'MD',
    'Palestine': 'PS',
    'Tanzania': 'TZ',
    'Venezuela': 'VE',
    'Bolivia': 'BO',
    'DR Congo': 'CD',
    'China (PRC)': 'CN',
    'Taiwan (ROC)': 'TW',
}

def alpha2_to_country(alpha2: str) -> str:
    return ALPHA2_TO_COUNTRY[alpha2]

def country_to_alpha2(country_name: str) -> str:
    alpha2 = country_converter.convert(names=(country_name,), to='ISO2')
    if alpha2 == 'not found':
        raise ValueError('Country not found!')
    return alpha2

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
ALPHA2_CONTINENTS = list(CONTINENT_CODE_TO_NAME.keys())

ALPHA2_ISLAND_NATIONS = [
    'AI', 'AS', 'AG', 'AU', 'AX', 'AW', 'BB', 'BM', 'BN', 'BS', 'CC', 'CK', 'CV', 'CX', 'CY', 'DM', 'DO', 'FJ', 'FK', 'FM', 'FO', 'GD', 'GL', 'GS', 'GU', 'HK', 'HM', 'ID', 'IE', 'IM', 'IS', 'IT', 'JM', 'JP', 'KI', 'KN', 'KR', 'LC', 'LK', 'MH', 'ML', 'MM', 'MP', 'MQ', 'MS', 'MT', 'MU', 'MV', 'NC', 'NF', 'NR', 'NU', 'NZ', 'PG', 'PH', 'PM', 'PN', 'PR', 'PW', 'RE', 'SB', 'SC', 'SG', 'SH', 'SJ', 'SL', 'SM', 'ST', 'SX', 'TC', 'TF', 'TH', 'TK', 'TL', 'TO', 'TT', 'TV', 'TW', 'UM', 'VC', 'VG', 'VI', 'VU', 'WF', 'WS'
]

ALPHA2_MICRO_NATIONS = [
    'AD', 'AG', 'FM', 'GD', 'KN', 'LC', 'LI', 'LU', 'MC', 'MH', 'MT', 'NR', 'SC', 'SM', 'ST', 'TV', 'VA', 'VC', 'WS'
]

ALPHA2_LANDLOCKED = [
    'BI', 'BW', 'BF', 'CF', 'TD', 'ET', 'LS', 'MW', 'ML', 'NE', 'RW', 'SS', 'SZ', 'UG', 'ZM', 'ZW', 'AD', 'AT', 'BY', 'CZ', 'HU', 'LI', 'LU', 'MD', 'MK', 'RS', 'SK', 'CH', 'SM', 'VA', 'AF', 'AM', 'AZ', 'BT', 'KZ', 'KG', 'LA', 'MN', 'NP', 'TJ', 'TM', 'UZ', 'BO', 'PY', 'XK',
]

POLAR_COUNTRIES = [
    'AQ', 'TF', 'GS', 'RU', 'NO', 'IS', 'FI', 'SE', 'GL', 'US', 'CA', 'DK'
]

EU_COUNTRIES = [
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
]

WAR_COUNTRIES = [
    'UA', 'PS', 'MM', 'SD', 'ET', 'SO', 'SY', 'CD', 'ML', 'BF', 'NG', 'YE', 'PK', 'HT', 'RU', 'IL'
]

DESERT_COUNTRIES = [
    'SA', 'QA', 'AE', 'OM', 'KW', 'BH', 'LY', 'EG', 'DZ', 'MR', 'NE', 'TD', 'SD', 'YE', 'IR', 'TM', 'UZ', 'KZ', 'AU', 'NA', 'BW',
]

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

def format_user_ranking(c_name: str, rank: int, count: float, ctype: str):
    rank_symbol = get_rank_symbol(rank).lstrip()
    rank_str = rank_symbol if rank_symbol else f'\u200b {rank}.'
    count_str = millify(count) if ctype == POINTS else str(count)
    amount_suffix = ' pt.' if ctype == POINTS else ' vt.' if ctype == VOTES else ''
    return f'{rank_str} {c_name} (Lvl. {count_str}{amount_suffix})'

def format_country_ranking(c_name: str, rank: int, count: float, ctype: str, dpos: int | None = None):
    is_recap = dpos is not None
    has_dpos = bool(dpos)
    rank_symbol = get_rank_symbol(rank).lstrip()
    rank_str = rank_symbol if rank_symbol else f'\u200b {rank}.'
    dpos_str = f' {incr_symbol(dpos)}{abs(dpos)}' if has_dpos else ''
    amount_prefix = '+' if is_recap else ''
    count_str = millify(count) if ctype == POINTS else str(count)
    amount_suffix = ' pt.' if ctype == POINTS else ' vt.' if ctype == VOTES else ''
    return f'{rank_str} {c_name} ({amount_prefix}{count_str}{amount_suffix}){dpos_str}'

CNAME_IMPROVEMENTS = {
    'Russian Federation': 'Russia',
    'Bonaire, Sint Eustatius and Saba': 'BES Islands',
    'Micronesia, Federated States of': 'Micronesia',
    'Iran, Islamic Republic of': 'Iran',
    'Korea, Democratic People\'s Republic of': 'North Korea',
    'Korea, Republic of': 'South Korea',
    'Moldova, Republic of': 'Moldova',
    'Palestine, State of': 'Palestine',
    'Tanzania, United Republic of': 'Tanzania',
    'Venezuela, Bolivarian Republic of': 'Venezuela',
    'Bolivia, Plurinational State of': 'Bolivia',
    'Congo, The Democratic Republic of the': 'DR Congo',
    'China': 'China (PRC)',
    'Taiwan, Province of China': 'Taiwan (ROC)'
}
def improve_cname(cname: str):
    return CNAME_IMPROVEMENTS[cname] if cname in CNAME_IMPROVEMENTS else cname

def format_cname(alpha2: str, cname: str) -> str:
    return f'{improve_cname(cname)} :flag_{alpha2.lower()}:'

def incr_symbol(incr: int) -> str:
    symbol = '▼' if incr < 0 else '▲' if incr > 0 else ''
    return symbol
