import asyncio
import datetime
import json
import os
from time import time, sleep
from typing import Tuple, Literal, Optional
from millify import millify as _millify
import pypopulation
from dotenv import load_dotenv
from pathlib import Path
import pycountry
import pycountry_convert
import discord
from discord import default_permissions, ApplicationContext, Interaction, Button, User
from pycountry_convert import country_alpha2_to_continent_code

load_dotenv()

data_path = Path('data.json')
flags_dir = Path('flags')

def sort_dict(inp_dict: dict) -> dict:
    return dict(sorted(inp_dict.items(), key=lambda item: item[1], reverse=True))

COUNTRIES_NAME_LIST = [country.name for country in pycountry.countries]
ALPHA2_TO_COUNTRY = {country.alpha_2: country.name for country in pycountry.countries}
print(ALPHA2_TO_COUNTRY)
DATA_PRESET = {
    'counts': {country.alpha_2: {'votes': 0, 'points': 0} for country in pycountry.countries},
    'daily_claims': {}
}

ALTERNATIVE_CNAMES = {
    'Turkey': 'TR'
}

def alpha2_to_country(alpha2: str) -> str:
    return ALPHA2_TO_COUNTRY[alpha2]

def country_to_alpha2(country_name: str) -> str:
    return list(ALPHA2_TO_COUNTRY.keys())[list(ALPHA2_TO_COUNTRY.values()).index(country_name)]

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

def incr_symbol(incr: int) -> str:
    symbol = '▼' if incr < 0 else '▲' if incr > 0 else ''
    return symbol

def load_data() -> dict:
    if data_path.exists():
        return json.loads(data_path.read_text())
    else:
        return DATA_PRESET

class FameBot:
    def __init__(self, cooldown: float = 0, daily_votes: int = 10):
        self.cooldown = cooldown
        self.daily_votes = daily_votes
        self.voting = None
        self.tree = None
        self.bot: discord.Bot = None
        self.data = load_data()
        self.user_cooldowns = {}

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
            alpha2 = ALTERNATIVE_CNAMES[c_inp]
            return alpha2, alpha2_to_country(alpha2)
        except KeyError:
            pass

        try:
            alpha2 = country_to_alpha2(c_inp)
        except ValueError:
            embed = self.get_base_embed(ctx.author,f'Unknown country {c_inp}!', description=' Please use a 2-letter code or the full name.', error=True)
            embed.add_field(name='Example:', value='*Germany* or *DE*')
            await ctx.respond(embed=embed, ephemeral=True)
            return None

        else:
            return alpha2, alpha2_to_country(alpha2)  # valid country name converted to alpha2

    @staticmethod
    def get_base_embed(user: User, title: str, error: bool = False, **kwargs) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            timestamp=datetime.datetime.now(datetime.UTC),
            color=discord.Colour.red() if error else discord.Colour.blurple(),
            **kwargs
        )
        embed.set_footer(
            text=f'{user.name}',
            icon_url=user.avatar.url
        )
        return embed

    def wait_cooldown(self, user_id: int):
        if user_id in self.user_cooldowns:
            next_vote = self.user_cooldowns[user_id]
            duration = max(0, next_vote - time())
        else:
            duration = 0
        sleep(duration)

    def calc_incr(self, votes_count: int) -> int:
        return sum([self.total_votes+i-1 for i in range(votes_count)])

    def do_vote(self, alpha2: str, votes_count: int) -> int:
        self.data['counts'][alpha2]['votes'] += votes_count
        points_incr = self.calc_incr(votes_count)
        self.data['counts'][alpha2]['points'] += points_incr
        self.save_data()
        return points_incr

    def get_country_stats(self, alpha2: str) -> Tuple[int, int, int, int]:
        return self.data['counts'][alpha2]['votes'], self.data['counts'][alpha2]['points'], \
               self.get_rank(alpha2, 'votes'), self.get_rank(alpha2, 'points')

    def vote_args(self, alpha2, c_name, user: User):
        self.user_cooldowns[user.id] = time() + self.cooldown
        points_incr = self.do_vote(alpha2, 1)
        vote_count, point_count, vote_rank, points_rank = self.get_country_stats(alpha2)

        embed = self.get_base_embed(
            user, title=f'Vote for {c_name} registered! ({incr_symbol(points_incr)}{millify(points_incr)} pt.)'
        )
        embed.add_field(name='Points',
                        value=f'{millify(point_count)} (#{points_rank}{get_rank_symbol(points_rank)})', inline=True)
        embed.add_field(name='Votes',
                        value=f'{millify(vote_count)} (#{vote_rank}{get_rank_symbol(vote_rank)})', inline=True)
        embed.set_thumbnail(url=f'attachment://{alpha2}.png')

        class VoteView(discord.ui.View):
            @discord.ui.button(label='Vote again', style=discord.ButtonStyle.primary, custom_id='again',
                               disabled=False if self.cooldown == 0 else True)
            async def button_callback(self2, button: Button, interaction: Interaction):
                if interaction.user.id != user.id:
                    await interaction.respond(embed=self.get_base_embed(user, f'This is {user.name}\'s voting window! Make your own one using /cvote', error=True), ephemeral=True)
                    return

                button.disabled = True
                await interaction.edit(view=view)
                vote_args = self.vote_args(alpha2, c_name, user)
                new_resp = await interaction.respond(**vote_args)
                self.wait_cooldown(user.id)
                vote_args['view'].enable_btn()
                await new_resp.edit(view=vote_args['view'])

            def enable_btn(self):
                for item in self.children:
                    if type(item) == discord.ui.Button and item.custom_id == 'again':
                        item.disabled = False
                        break

        view = VoteView()
        return {
            'embed': embed,
            'file': discord.File(Path(flags_dir, alpha2 + '.png'), filename=alpha2 + '.png'),
            'view': view
        }

    def register_cmds(self):
        country_cmds = discord.SlashCommandGroup('country', 'country-related commands')
        top_cmds = discord.SlashCommandGroup('top', 'leaderboard for all countries')

        @self.bot.slash_command(
            name='cvote',
            description='Cast a vote for a country of your choice!'
        )
        @country_cmds.command(
            name='vote',
            description='Cast a vote for a country of your choice!'
        )
        async def vote_cmd(ctx: ApplicationContext, country: discord.Option(str)):
            await ctx.defer()
            self.wait_cooldown(ctx.user.id)
            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            vote_args = self.vote_args(alpha2, c_name, ctx.author)
            await ctx.respond(**vote_args)

            self.wait_cooldown(ctx.author.id)
            vote_args['view'].enable_btn()
            await ctx.edit(view=vote_args['view'])

        @self.bot.slash_command(
            name='dbclear',
            description='Clears the entire database'
        )
        @default_permissions(administrator=True)
        async def dbclear_cmd(ctx: ApplicationContext):
            self.data = DATA_PRESET.copy()
            await ctx.respond(embed=self.get_base_embed(ctx.author, 'Database cleared', description='Hope you know what you are doing!'), ephemeral=True)

        @country_cmds.command(
            name='set',
            description='Sets votes of a country to a specific amount'
        )
        @default_permissions(administrator=True)
        async def cset_cmd(ctx: ApplicationContext,
                           ctype: discord.Option(str, choices=['votes', 'points']),
                           country: discord.Option(str),
                           amount: discord.Option(int)):
            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            if ctype not in ['votes', 'points']:
                await ctx.respond(embed=self.get_base_embed(ctx.author, 'Unknown ctype!', desccription='Use "votes" or "points".'), ephemeral=True)
                return

            self.data['counts'][alpha2][ctype] = amount
            self.save_data()
            await ctx.respond(embed=self.get_base_embed(ctx.author, 'Data changed', description=f'{ctype.capitalize()} for {alpha2_to_country(alpha2)} ({alpha2}) set to {amount}!'), ephemeral=True)

        @country_cmds.command(
            name='clear',
            description='Resets votes for a specific country'
        )
        @default_permissions(administrator=True)
        async def cclear_cmd(ctx: ApplicationContext, country: discord.Option(str)):
            await cset_cmd(ctx, 'points', country, 0)
            await cset_cmd(ctx, 'votes', country, 0)

        @country_cmds.command(
            name='info',
            description='Information about a country'
        )
        async def cinfo_cmd(ctx: ApplicationContext, country: discord.Option(str)):
            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            vote_count, point_count = self.data['counts'][alpha2]['votes'], self.data['counts'][alpha2]['points']
            vote_rank, points_rank = self.get_rank(alpha2, 'votes'), self.get_rank(alpha2, 'points')

            embed = self.get_base_embed(ctx.author, title=c_name)
            embed.add_field(name='Points',
                            value=f'{millify(point_count)} (#{points_rank}{get_rank_symbol(points_rank)})', inline=True)
            embed.add_field(name='Votes',
                            value=f'{millify(vote_count)} (#{vote_rank}{get_rank_symbol(vote_rank)})', inline=True)
            embed.add_field(name='Points per capita',
                            value=millify(points_per_capita(alpha2, point_count)), inline=True)
            embed.add_field(name='2-letter code',
                            value=alpha2, inline=True)
            embed.add_field(name='Continent',
                            value=CONTINENT_CODE_TO_NAME[country_to_continent(alpha2)], inline=True)
            embed.set_thumbnail(url=f'attachment://{alpha2}.png')
            await ctx.respond(
                embed=embed,
                file=discord.File(Path(flags_dir, alpha2 + '.png'), filename=alpha2 + '.png')
            )

        @top_cmds.command(
            name='country',
            description='List of the top countries'
        )
        async def ctop_cmd(ctx: ApplicationContext):
            points_str, votes_str = '', ''
            point_values = {c: self.data['counts'][c]['points'] for c in self.data['counts']}
            point_values = sort_dict(point_values)
            vote_values = {c: self.data['counts'][c]['votes'] for c in self.data['counts']}
            vote_values = sort_dict(vote_values)

            for alpha2 in point_values:
                c_name = alpha2_to_country(alpha2)
                point_count = self.data['counts'][alpha2]['points']
                if point_count == 0: continue
                points_rank = self.get_rank(alpha2, 'points')
                points_str += f'{points_rank}. {get_rank_symbol(points_rank).lstrip()}{c_name} ({point_count} pt.)\n'

            for alpha2 in vote_values:
                c_name = alpha2_to_country(alpha2)
                vote_count = self.data['counts'][alpha2]['votes']
                if vote_count == 0: continue
                vote_rank = self.get_rank(alpha2, 'votes')
                votes_str += f'{vote_rank}. {get_rank_symbol(vote_rank).lstrip()}{c_name} ({vote_count} vt.)\n'

            embed = self.get_base_embed(ctx.author, title='Top countries')
            embed.add_field(name='Points', value=points_str, inline=True)
            embed.add_field(name='Votes', value=votes_str, inline=True)
            await ctx.respond(embed=embed)

        @top_cmds.command(
            name='continent',
            description='List of the top continents'
        )
        async def contop_cmd(ctx: ApplicationContext):
            point_values = {}
            vote_values = {}

            for alpha2 in self.data['counts']:
                continent = country_to_continent(alpha2)
                if continent not in point_values:
                    point_values[continent] = 0
                if continent not in vote_values:
                    vote_values[continent] = 0

                point_values[continent] += self.data['counts'][alpha2]['points']
                vote_values[continent] += self.data['counts'][alpha2]['votes']

            point_values, vote_values = sort_dict(point_values), sort_dict(vote_values)
            point_str = '\n'.join([f'{i}. {CONTINENT_CODE_TO_NAME[con]} ({point_values[con]})' for i, con in enumerate(point_values, 1)])
            vote_str = '\n'.join([f'{i}. {CONTINENT_CODE_TO_NAME[con]} ({vote_values[con]})' for i, con in enumerate(vote_values, 1)])

            embed = self.get_base_embed(ctx.author, title='Top continents')
            embed.add_field(name='Points', value=point_str, inline=True)
            embed.add_field(name='Votes', value=vote_str, inline=True)
            await ctx.respond(embed=embed)

        @self.bot.slash_command(
            name='daily',
            description='Give a daily bonus to a country of your choice!'
        )
        async def daily_cmd(ctx: ApplicationContext, country: discord.Option(str)):
            if str(ctx.author.id) in self.data['daily_claims']:
                next_claim = self.data['daily_claims'][str(ctx.author.id)] + 60*60*20
                dt = next_claim - time()
                print(dt)
                if dt > 0:
                    await ctx.respond(
                        embed=self.get_base_embed(ctx.author, 'Too early!', description=f'Wait {round(dt/60/60, 1)} hours before claiming your daily award again.', error=True),
                        ephemeral=True)
                    return

            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            points_incr = self.do_vote(alpha2, self.daily_votes)
            vote_count, point_count, vote_rank, points_rank = self.get_country_stats(alpha2)
            self.data['daily_claims'][str(ctx.author.id)] = time()
            self.save_data()

            embed = self.get_base_embed(
                ctx.author, title=f'{self.daily_votes} daily votes {c_name} registered for {c_name}! ({incr_symbol(points_incr)}{millify(points_incr)} pt.)'
            )
            embed.add_field(name='Points',
                            value=f'{millify(point_count)} (#{points_rank}{get_rank_symbol(points_rank)})', inline=True)
            embed.add_field(name='Votes',
                            value=f'{millify(vote_count)} (#{vote_rank}{get_rank_symbol(vote_rank)})', inline=True)
            embed.set_thumbnail(url=f'attachment://{alpha2}.png')

            await ctx.respond(embed=embed, file=discord.File(Path(flags_dir, alpha2 + '.png'), filename=alpha2 + '.png'))

        self.bot.add_application_command(top_cmds)
        self.bot.add_application_command(country_cmds)

    def run(self):
        self.bot = discord.Bot(intents=discord.Intents.default(), command_prefix='&')
        self.register_cmds()
        self.bot.run(os.getenv('TOKEN'))
        bot.save_data()  # failsafe for data loss

if __name__ == '__main__':
    bot = FameBot()
    bot.run()
