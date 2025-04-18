import json
import os
from typing import Tuple, Literal, Optional

from dotenv import load_dotenv
from pathlib import Path
import pycountry
import discord
from discord import default_permissions

load_dotenv()

data_path = Path('data.json')
flags_dir = Path('flags')

COUNTRIES_NAME_LIST = [country.name for country in pycountry.countries]
ALPHA2_TO_COUNTRY = {country.alpha_2: country.name for country in pycountry.countries}
DATA_PRESET = {'counts': {country.alpha_2: {'votes': 0, 'points': 0} for country in pycountry.countries}}

def alpha2_to_country(alpha2_str: str) -> str:
    return ALPHA2_TO_COUNTRY[alpha2_str]

def country_to_alpha2(country_name: str) -> str:
    return list(ALPHA2_TO_COUNTRY.keys())[list(ALPHA2_TO_COUNTRY.values()).index(country_name)]

RANK_SYMBOLS = {1: '🥇', 2: '🥈', 3: '🥉'}
def get_rank_symbol(rank: int) -> str:
    if rank in RANK_SYMBOLS:
        return ' ' + RANK_SYMBOLS[rank]
    else:
        return ''

def load_data():
    if data_path.exists():
        return json.loads(data_path.read_text())
    else:
        return DATA_PRESET

class FameBot:
    def __init__(self):
        self.voting = None
        self.tree = None
        self.bot = None
        self.country_imgs = None
        self.data = load_data()

    def save_data(self):
        data_path.write_text(json.dumps(self.data, indent=2))

    @property
    def total_votes(self) -> int:
        return sum(self.data['counts'][country]['votes'] for country in self.data['counts'])

    def get_rank(self, alpha2: str, ctype: Literal['points', 'votes']) -> int:
        values = [self.data['counts'][c][ctype] for c in self.data['counts']]
        values.sort(reverse=True)
        return values.index(self.data['counts'][alpha2][ctype]) + 1

    async def eval_country(self, ctx, c_inp: str) -> Tuple[str, str] | None:
        c_inp = c_inp.upper()
        if c_inp in self.data['counts']:  # valid alpha2 code
            return c_inp, alpha2_to_country(c_inp)

        c_inp = c_inp.lower().capitalize()
        try:
            alpha2 = country_to_alpha2(c_inp)

        except ValueError:
            await ctx.respond(f'Unknown country {c_inp}! Please use a 2-letter code or the full name.\n'
                              f'Example: *Germany*, *DE*')
            return None

        else:
            return alpha2, alpha2_to_country(alpha2)  # valid country name converted to alpha2

    def get_base_embed(self, title: str, error: bool = False, **kwargs) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            color=discord.Colour.red() if error else discord.Colour.blurple(),
            **kwargs
        )
        embed.set_footer(
            text=self.__class__.__name__,
            icon_url='https://cdn.discordapp.com/avatars/1071362480347041802/ebd5ff4cadb4ab015f00c967d9f2852a?size=512'
        )
        return embed

    def register_cmds(self):
        @self.bot.slash_command(
            name='cvote',
            description='Cast a vote for a country of your choice!'
        )
        async def vote_cmd(ctx, country: discord.Option(str)):
            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            points_incr = self.total_votes
            self.data['counts'][alpha2]['votes'] += 1
            self.data['counts'][alpha2]['points'] += points_incr
            self.save_data()

            vote_count, point_count = self.data['counts'][alpha2]['votes'], self.data['counts'][alpha2]['points']
            vote_rank, points_rank = self.get_rank(alpha2, 'votes'), self.get_rank(alpha2, 'points')

            embed = self.get_base_embed(title=f'Vote for {c_name} registered! (▲{points_incr} pt.)')
            embed.add_field(name='Points',
                            value=f'{point_count} (#{points_rank}{get_rank_symbol(points_rank)})', inline=True)
            embed.add_field(name='Votes',
                            value=f'{vote_count} (#{vote_rank}{get_rank_symbol(vote_rank)})', inline=True)
            embed.set_thumbnail(url=f'attachment://{alpha2}.png')
            await ctx.respond(
                embed=embed,
                file=discord.File(Path(flags_dir, alpha2 + '.png'), filename=alpha2 + '.png')
            )

        @self.bot.slash_command(
            name='dbclear',
            description='Clears the entire database'
        )
        @default_permissions(administrator=True)
        async def dbclear_cmd(ctx):
            self.data = DATA_PRESET.copy()
            await ctx.respond('Database cleared! Hope you know what you are doing.')

        country_cmds = discord.SlashCommandGroup('country', 'country-related commands')

        @country_cmds.command(
            name='set',
            description='Sets votes of a country to a specific amount'
        )
        @default_permissions(administrator=True)
        async def cset_cmd(ctx,
                           ctype: discord.Option(str, choices=['votes', 'points']),
                           country: discord.Option(str),
                           amount: discord.Option(int)):
            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            if ctype not in ['votes', 'points']:
                await ctx.respond('Unknown ctype! Use "votes" or "points".')
                return

            self.data['counts'][alpha2][ctype] = amount
            self.save_data()
            await ctx.respond(f'{ctype.capitalize()} for {alpha2_to_country(alpha2)} ({alpha2}) set to {amount}!')

        @country_cmds.command(
            name='clear',
            description='Resets votes for a specific country'
        )
        @default_permissions(administrator=True)
        async def cclear_cmd(ctx, country: discord.Option(str)):
            await cset_cmd(ctx, 'points', country, 0)
            await cset_cmd(ctx, 'votes', country, 0)

        self.bot.add_application_command(country_cmds)

    def run(self):
        self.bot = discord.Bot(intents=discord.Intents.default(), command_prefix='&')
        self.register_cmds()
        self.bot.run(os.getenv('TOKEN'))
        bot.save_data()  # failsafe for data loss

if __name__ == '__main__':
    bot = FameBot()
    bot.run()
