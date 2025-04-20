import asyncio

from data import FameUser, load_data, save_data, flags_dir, DATA_PRESET, get_flag, get_banner
from utils import sort_dict, alpha2_to_country, country_to_alpha2, ALTERNATIVE_CNAMES, incr_symbol, \
    millify, get_rank_symbol, CONTINENT_CODE_TO_NAME, points_per_capita, country_to_continent, format_country_ranking, \
    format_cname

import datetime
import os
from time import time
from typing import Tuple, Literal, List, Iterator
from dotenv import load_dotenv
from pathlib import Path
import discord
from discord import default_permissions, ApplicationContext, Interaction, Button, User

class FameBot:
    def __init__(self, cooldown: float = 3, daily_votes: int = 10, recap_scopes=None):
        if recap_scopes is None:
            self.recap_scopes = ['daily', 'weekly', 'monthly']
        else:
            self.recap_scopes = recap_scopes
        self.cooldown = cooldown
        self.daily_votes = daily_votes

        self.bot: discord.Bot | None = None
        self.data = load_data()
        self.user_data = {}

    def save_data(self) -> None:
        save_data(self.data)

    @property
    def total_votes(self) -> int:
        return sum(self.data['total'][country]['votes'] for country in self.data['total'])

    @property
    def users(self) -> Iterator[FameUser]:
        for user_id in self.data['users']:
            yield FameUser(self.data['users'][user_id], user_id)

    def get_order(self, ctype: Literal['points', 'votes'], recap_scope: str | None = None) -> List[str]:
        data = self.data['total'] if recap_scope is None else self.data['recap'][recap_scope]
        return list(sort_dict({c: data[c][ctype] for c in data}).keys())

    def get_rank(self, alpha2: str, ctype: Literal['points', 'votes'], recap_scope: str | None = None) -> int:
        return self.get_order(ctype, recap_scope).index(alpha2) + 1

    async def eval_country(self, ctx, c_inp: str) -> Tuple[str, str] | None:
        c_inp = c_inp.upper()
        if c_inp in self.data['total']:  # valid alpha2 code
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

    def calc_incr_legacy(self, votes_count: int) -> int:
        # old way of calculating point increments
        return sum([self.total_votes+i-1 for i in range(votes_count)])

    def update_recap_ranks(self, prev_order: Tuple[List[str], List[str]], new_order: Tuple[List[str], List[str]]) -> None:
        for scope in self.recap_scopes:
            for alpha2 in self.data['recap'][scope]:
                p_prev, v_prev = prev_order[0].index(alpha2), prev_order[1].index(alpha2)
                p_new, v_new = new_order[0].index(alpha2), new_order[1].index(alpha2)
                self.data['recap'][scope][alpha2]['dpos_points'] += p_prev - p_new
                self.data['recap'][scope][alpha2]['dpos_votes'] += v_prev - v_new

    def do_vote(self, user: FameUser, alpha2: str, votes_count: int) -> int:
        prev_order = (self.get_order('points'), self.get_order('votes'))

        self.data['total'][alpha2]['votes'] += votes_count
        user.total_votes += votes_count
        user.data['country'][alpha2]['votes'] += votes_count

        # points_incr = self.calc_incr(votes_count)
        points_incr = user.points_per_vote * votes_count
        self.data['total'][alpha2]['points'] += points_incr
        user.total_points += points_incr
        user.data['country'][alpha2]['points'] += points_incr
        user.save()

        new_order = (self.get_order('points'), self.get_order('votes'))
        self.update_recap_ranks(prev_order, new_order)

        for scope in self.recap_scopes:
            self.data['recap'][scope][alpha2]['votes'] += votes_count
            self.data['recap'][scope][alpha2]['points'] += points_incr

        self.save_data()
        return points_incr

    def get_country_stats(self, alpha2: str) -> Tuple[int, int, int, int]:
        return self.data['total'][alpha2]['votes'], self.data['total'][alpha2]['points'], \
               self.get_rank(alpha2, 'votes'), self.get_rank(alpha2, 'points')

    def vote_args(self, alpha2, c_name: str, user: User):
        fame_user = FameUser.from_file(user.id)
        fame_user.update_next_vote(self.cooldown)
        fame_user.save()

        points_incr = self.do_vote(FameUser.from_file(user.id), alpha2, 1)
        vote_count, point_count, vote_rank, points_rank = self.get_country_stats(alpha2)

        embed = self.get_base_embed(
            user, title=f'Vote for {format_cname(alpha2, c_name)} registered! ({incr_symbol(points_incr)}{millify(points_incr)} pt.)'
        )
        embed.add_field(name='Points',
                        value=f'{millify(point_count)} (#{points_rank}{get_rank_symbol(points_rank)})', inline=True)
        embed.add_field(name='Votes',
                        value=f'{millify(vote_count)} (#{vote_rank}{get_rank_symbol(vote_rank)})', inline=True)

        flag, banner = get_flag(alpha2), get_banner(alpha2)
        if banner:
            embed.set_image(url=f'attachment://{alpha2}.jpg')
        else:
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
                fame_user.wait_cooldown()
                vote_args['view'].set_again_state(True)
                await new_resp.edit(view=vote_args['view'])

            def set_again_state(self, value: bool):
                for item in self.children:
                    if type(item) == discord.ui.Button and item.custom_id == 'again':
                        item.disabled = not value
                        break

        view = VoteView()
        return {
            'embed': embed,
            'file': banner if banner else flag,
            'view': view
        }

    async def check_permissions(self, ctx: ApplicationContext, admin_only: bool) -> bool:
        if admin_only and ctx.user.id not in self.data['admins']:
            description = ':no_entry_sign: You need to be Admin to use this command!'
        elif self.data['maintenance'] and ctx.user.id not in self.data['admins']:
            description = ':tools: The bot is currently under maintenance.'
        else:
            return True

        await ctx.respond(embed=self.get_base_embed(ctx.author, 'Action failed', description=description, error=True), ephemeral=True)
        return False

    def register_cmds(self):
        country_cmds = discord.SlashCommandGroup('country', 'country-related commands')
        top_cmds = discord.SlashCommandGroup('top', 'leaderboards')
        user_cmds = discord.SlashCommandGroup('user', 'user-related commands')

        @self.bot.slash_command(
            name='cvote',
            description='Cast a vote for a country of your choice!'
        )
        @country_cmds.command(
            name='vote',
            description='Cast a vote for a country of your choice!'
        )
        async def vote_cmd(ctx: ApplicationContext, country: discord.Option(str)):
            if not await self.check_permissions(ctx, False):
                return
            await ctx.defer()
            user = FameUser.from_file(ctx.author.id)
            if not user.vote_ready:
                await ctx.respond(
                    embed=self.get_base_embed(
                        ctx.author, 'On cooldown!',
                        description=f'Wait a few seconds before you can vote again.',
                        error=True),
                    ephemeral=True
                )
                return

            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            vote_args = self.vote_args(alpha2, c_name, ctx.author)
            await ctx.respond(**vote_args)

            user.wait_cooldown()
            vote_args['view'].set_again_state(True)
            await ctx.edit(view=vote_args['view'])

            # sleep(60)  # voting window expires after some time...
            await asyncio.sleep(10)
            vote_args['view'].set_again_state(False)
            await ctx.edit(view=vote_args['view'])

        @self.bot.slash_command(
            name='dbclear',
            description='Clears the entire database'
        )
        @default_permissions(administrator=True)
        async def dbclear_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, True):
                return
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
            if not await self.check_permissions(ctx, True):
                return
            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            if ctype not in ['votes', 'points']:
                await ctx.respond(embed=self.get_base_embed(ctx.author, 'Unknown ctype!', desccription='Use "votes" or "points".'), ephemeral=True)
                return

            self.data['total'][alpha2][ctype] = amount
            self.save_data()
            await ctx.respond(embed=self.get_base_embed(ctx.author, 'Data changed', description=f'{ctype.capitalize()} for {alpha2_to_country(alpha2)} ({alpha2}) set to {amount}!'), ephemeral=True)

        @country_cmds.command(
            name='clear',
            description='Resets votes for a specific country'
        )
        @default_permissions(administrator=True)
        async def cclear_cmd(ctx: ApplicationContext, country: discord.Option(str)):
            if not await self.check_permissions(ctx, True):
                return
            await cset_cmd(ctx, 'points', country, 0)
            await cset_cmd(ctx, 'votes', country, 0)

        @country_cmds.command(
            name='info',
            description='Information about a country'
        )
        async def cinfo_cmd(ctx: ApplicationContext, country: discord.Option(str)):
            if not await self.check_permissions(ctx, False):
                return
            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            vote_count, point_count = self.data['total'][alpha2]['votes'], self.data['total'][alpha2]['points']
            vote_rank, points_rank = self.get_rank(alpha2, 'votes'), self.get_rank(alpha2, 'points')

            embed = self.get_base_embed(ctx.author, title=format_cname(alpha2, c_name))
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
                file=get_flag(alpha2)
            )

        @top_cmds.command(
            name='country',
            description='List of the top countries'
        )
        async def ctop_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            point_values = {c: self.data['total'][c]['points'] for c in self.data['total']}
            point_values = sort_dict(point_values)
            vote_values = {c: self.data['total'][c]['votes'] for c in self.data['total']}
            vote_values = sort_dict(vote_values)

            point_str, vote_str = str(), str()
            for alpha2 in point_values:
                c_name = alpha2_to_country(alpha2)
                point_count = self.data['total'][alpha2]['points']
                point_rank = self.get_rank(alpha2, 'points')
                if point_count == 0: continue
                point_str += format_country_ranking(format_cname(alpha2, c_name), point_rank, point_count, 'points') + '\n'

            for alpha2 in vote_values:
                c_name = alpha2_to_country(alpha2)
                vote_count = self.data['total'][alpha2]['votes']
                vote_rank = self.get_rank(alpha2, 'votes')
                if vote_count == 0: continue
                vote_str += format_country_ranking(format_cname(alpha2, c_name), vote_rank, vote_count, 'votes') + '\n'

            embed = self.get_base_embed(ctx.author, title='Top countries')
            embed.add_field(name='Points', value=point_str, inline=True)
            embed.add_field(name='Votes', value=vote_str, inline=True)
            await ctx.respond(embed=embed)

        @top_cmds.command(
            name='continent',
            description='List of the top continents'
        )
        async def contop_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return
            point_values = {}
            vote_values = {}

            for alpha2 in self.data['total']:
                continent = country_to_continent(alpha2)
                if continent not in point_values:
                    point_values[continent] = 0
                if continent not in vote_values:
                    vote_values[continent] = 0

                point_values[continent] += self.data['total'][alpha2]['points']
                vote_values[continent] += self.data['total'][alpha2]['votes']

            point_values, vote_values = sort_dict(point_values), sort_dict(vote_values)
            point_str = '\n'.join([format_country_ranking(CONTINENT_CODE_TO_NAME[con], n, point_values[con], 'points') \
                                   for n, con in enumerate(point_values, 1)])
            vote_str = '\n'.join([format_country_ranking(CONTINENT_CODE_TO_NAME[con], n, vote_values[con], 'votes') \
                                  for n, con in enumerate(vote_values, 1)])

            embed = self.get_base_embed(ctx.author, title='Top continents')
            embed.add_field(name='Points', value=point_str, inline=True)
            embed.add_field(name='Votes', value=vote_str, inline=True)
            await ctx.respond(embed=embed)

        @self.bot.slash_command(
            name='daily',
            description='Give a daily bonus to a country of your choice!'
        )
        async def daily_cmd(ctx: ApplicationContext, country: discord.Option(str)):
            if not await self.check_permissions(ctx, False):
                return

            fame_user = FameUser.from_file(ctx.user.id)
            if fame_user.daily_claim:
                next_claim = fame_user.daily_claim + 60*60*20
                dt = next_claim - time()
                if dt > 0:
                    await ctx.respond(
                        embed=self.get_base_embed(ctx.author, 'Too early!', description=f'Wait {round(dt/60/60, 1)} hours before claiming your daily award again.', error=True),
                        ephemeral=True)
                    return

            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            fame_user = FameUser.from_file(ctx.author.id)
            points_incr = self.do_vote(fame_user, alpha2, self.daily_votes)
            self.save_data()

            vote_count, point_count, vote_rank, points_rank = self.get_country_stats(alpha2)
            fame_user.update_daily_claim()
            fame_user.save()

            embed = self.get_base_embed(
                ctx.author, title=f'{self.daily_votes} daily votes registered for {format_cname(alpha2, c_name)}! ({incr_symbol(points_incr)}{millify(points_incr)} pt.)'
            )
            embed.add_field(name='Points',
                            value=f'{millify(point_count)} (#{points_rank}{get_rank_symbol(points_rank)})', inline=True)
            embed.add_field(name='Votes',
                            value=f'{millify(vote_count)} (#{vote_rank}{get_rank_symbol(vote_rank)})', inline=True)
            embed.set_thumbnail(url=f'attachment://{alpha2}.png')

            await ctx.respond(embed=embed, file=discord.File(Path(flags_dir, alpha2 + '.png'), filename=alpha2 + '.png'))

        @self.bot.slash_command(
            name='maintenance',
            description='Toggle maintainance mode'
        )
        @default_permissions(administrator=True)
        async def daily_cmd(ctx: ApplicationContext, value: discord.Option(bool)):
            if not await self.check_permissions(ctx, True):
                return
            self.data['maintenance'] = value

        @self.bot.slash_command(
            name='recap',
            description='Generates a recap for a given time frame!'
        )
        async def recap_cmd(ctx: ApplicationContext, scope: discord.Option(str, choices=self.recap_scopes)):
            if not await self.check_permissions(ctx, False):
                return

            point_values = {c: self.data['recap'][scope][c]['points'] for c in self.data['recap'][scope]}
            point_values = sort_dict(point_values)
            vote_values = {c: self.data['recap'][scope][c]['votes'] for c in self.data['recap'][scope]}
            vote_values = sort_dict(vote_values)

            point_str, vote_str = str(), str()
            for alpha2 in point_values:
                c_name = alpha2_to_country(alpha2)
                c_data = self.data['recap'][scope][alpha2]
                point_count, point_dpos = c_data['points'], c_data['dpos_points']
                point_rank = self.get_rank(alpha2, 'points', scope)
                if point_count == 0: continue
                point_str += format_country_ranking(c_name, point_rank, point_count, 'points', point_dpos, True) + '\n'

            for alpha2 in vote_values:
                c_name = alpha2_to_country(alpha2)
                c_data = self.data['recap'][scope][alpha2]
                vote_count, vote_dpos = c_data['votes'], c_data['dpos_votes']
                vote_rank = self.get_rank(alpha2, 'votes', scope)
                if vote_count == 0: continue
                vote_str += format_country_ranking(c_name, vote_rank, vote_count, 'votes', vote_dpos, True) + '\n'

            embed = self.get_base_embed(ctx.author, title=f'Top {scope.lower()} countries')
            embed.add_field(name='Points', value=point_str, inline=True)
            embed.add_field(name='Votes', value=vote_str, inline=True)
            await ctx.respond(embed=embed)

        @user_cmds.command(
            name='info',
            description='Displays information on a user'
        )
        async def uinfo_cmd(ctx: ApplicationContext, user: discord.User):
            if not await self.check_permissions(ctx, False):
                return

            fame_user = FameUser.from_file(user.id)

            embed = self.get_base_embed(ctx.author, title=f'{user.name}\'s Profile')
            embed.add_field(name='Leveling', value=fame_user.leveling_formatted, inline=False)
            embed.add_field(name='Total votes', value=str(fame_user.total_votes), inline=True)
            embed.add_field(name='Total points', value=str(fame_user.total_points), inline=True)
            embed.set_thumbnail(url=ctx.author.avatar.url)
            await ctx.respond(embed=embed)

        self.bot.add_application_command(country_cmds)
        self.bot.add_application_command(top_cmds)
        self.bot.add_application_command(user_cmds)

        @self.bot.slash_command(
            name='me',
            description='View your own profile!'
        )
        async def me_cmd(ctx: ApplicationContext):
            await uinfo_cmd(ctx, ctx.user)

    def run(self):
        self.bot = discord.Bot(intents=discord.Intents.default())
        self.register_cmds()
        self.bot.run(os.getenv('TOKEN'))
        bot.save_data()  # failsafe to prevent data loss

if __name__ == '__main__':
    load_dotenv()
    bot = FameBot()
    bot.run()
