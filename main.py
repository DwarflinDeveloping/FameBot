import asyncio
from copy import deepcopy
import json
from math import ceil

from data import FameUser, load_data, save_data, flags_dir, DATA_PRESET, get_flag, get_banner, get_flag_path, \
    get_banner_path, FameRecap, recaps_dir, users_dir, clear_database, USER_DATA_PRESET, PV_PRESET
from utils import sort_dict, alpha2_to_country, country_to_alpha2, ALTERNATIVE_CNAMES, incr_symbol, \
    millify, get_rank_symbol, CONTINENT_CODE_TO_NAME, points_per_capita, country_to_continent, format_country_ranking, \
    format_cname, POINTS, VOTES, CTYPES, ALPHA2_COUNTRIES, ALPHA2_CONTINENTS

import datetime
import os
from time import time
from dotenv import load_dotenv
from pathlib import Path
from discord import default_permissions, ApplicationContext, Interaction, Button, User, Guild, Member, Option, File, \
    Embed, Colour, ButtonStyle, ui, Bot, Intents, SlashCommandGroup, TextChannel, ClientUser, InputTextStyle
from discord.ext import tasks

from typing import Tuple, List, Iterator, Dict, Any


class FameBot:
    def __init__(self, cooldown: float = 5, daily_votes: int = 30, recap_scopes=None, upload_images: bool = False):
        if recap_scopes is None:
            self.visible_recap_scopes = ['daily', 'weekly', 'seasonal']
            self.recap_scopes = self.visible_recap_scopes + ['alltime']
        else:
            self.recap_scopes = recap_scopes
        self.cooldown = cooldown
        self.daily_votes = daily_votes
        self.upload_images = upload_images

        self.bot: Bot | None = None
        self.data = load_data()
        self.role_checks: List[int] = []
        self.loaded_users: Dict[int, FameUser] = {}
        self.loaded_recaps: Dict[str, FameRecap] = {}

    def save_data(self) -> None:
        save_data(self.data)

    @property
    def total_votes(self) -> int:
        recap = self.get_recap('alltime')
        return sum(recap.get(alpha2)[VOTES] for alpha2 in ALPHA2_COUNTRIES)

    @property
    def total_points(self) -> int:
        recap = self.get_recap('alltime')
        return sum(recap.get(alpha2)[POINTS] for alpha2 in ALPHA2_COUNTRIES)

    @property
    def on_maintenance(self) -> bool:
        return self.data['maintenance']

    @on_maintenance.setter
    def on_maintenance(self, value: bool) -> None:
        self.data['maintenance'] = value

    @property
    def admin_ids(self) -> List[int]:
        return self.data['admins']

    def get_order(self, ctype: CTYPES, recap_scope: str = 'alltime') -> List[str]:
        recap = self.get_recap(recap_scope)
        return list(sort_dict({alpha2: recap.get(alpha2)[ctype] for alpha2 in ALPHA2_COUNTRIES}).keys())

    def get_rank(self, alpha2: str, ctype: CTYPES, recap_scope: str = 'alltime') -> int:
        return self.get_order(ctype, recap_scope).index(alpha2) + 1

    async def eval_country(self, ctx: ApplicationContext, inp: str) -> Tuple[str, str] | None:
        c_inp = inp.upper()
        if c_inp in ALPHA2_COUNTRIES:  # valid alpha2 code
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
            embed = self.get_base_embed(ctx.author,f'Unknown country {inp}!', description=' Please use a 2-letter code or the full name.', error=True)
            embed.add_field(name='Example:', value='*Germany* or *DE*')
            await ctx.respond(embed=embed, ephemeral=True)
            return None

        else:
            return alpha2, alpha2_to_country(alpha2)  # valid country name converted to alpha2

    def get_user(self, user: User | Member) -> FameUser:
        if user.id in self.loaded_users:
            return self.loaded_users[user.id]

        fame_user = FameUser.from_file(user.id)
        self.loaded_users[user.id] = fame_user
        return fame_user

    def get_recap(self, scope: str) -> FameRecap:
        if scope in self.loaded_recaps:
            return self.loaded_recaps[scope]

        recap = FameRecap.from_file(scope)
        self.loaded_recaps[scope] = recap
        return recap

    def get_top_countries(self, scope: str) -> Tuple[Dict[str, int], Dict[str, int]]:
        recap = self.get_recap(scope)

        point_values, vote_values = dict(), dict()
        for alpha2 in ALPHA2_COUNTRIES:
            c_data = recap.get(alpha2)
            point_values[alpha2] = c_data[POINTS]
            vote_values[alpha2] = c_data[VOTES]

        return sort_dict(point_values), sort_dict(vote_values)

    def get_top_continents(self, scope: str) -> Tuple[Dict[str, int], Dict[str, int]]:
        recap = self.get_recap(scope)

        point_values, vote_values = dict(), dict()
        for alpha2 in ALPHA2_COUNTRIES:
            continent = country_to_continent(alpha2)
            if continent not in point_values:
                point_values[continent] = 0
            if continent not in vote_values:
                vote_values[continent] = 0

            c_data = recap.get(alpha2)
            point_values[continent] += c_data[POINTS]
            vote_values[continent] += c_data[VOTES]

        return sort_dict(point_values), sort_dict(vote_values)

    @staticmethod
    def get_base_embed(user: User, title: str, error: bool = False, **kwargs) -> Embed:
        embed = Embed(
            title=title,
            timestamp=datetime.datetime.now(datetime.UTC),
            color=Colour.red() if error else Colour.blurple(),
            **kwargs
        )
        embed.set_footer(
            text=user.name,
            icon_url=user.avatar.url if user.avatar else user.default_avatar.url
        )
        return embed

    def calc_incr_legacy(self, votes_count: int) -> int:
        # old way of calculating point increments
        return sum([self.total_votes+i-1 for i in range(votes_count)])

    def update_recap_ranks(self, prev_order: Tuple[List[str], List[str]], new_order: Tuple[List[str], List[str]]) -> None:
        for scope in self.visible_recap_scopes:
            recap = self.get_recap(scope)
            changes = False

            for alpha2 in ALPHA2_COUNTRIES:
                p_prev, v_prev = prev_order[0].index(alpha2), prev_order[1].index(alpha2)
                p_new, v_new = new_order[0].index(alpha2), new_order[1].index(alpha2)
                dp, dv = p_prev - p_new, v_prev - v_new
                if dp != 0:
                    recap.add(alpha2, dpos_points=dp)
                    changes = True
                if dv != 0:
                    recap.add(alpha2, dpos_votes=dv)
                    changes = True

            if changes:
                recap.save()

    def do_vote(self, user: FameUser, alpha2: str, votes_count: int) -> int:
        prev_order = (self.get_order(POINTS), self.get_order(VOTES))
        old_level = user.points_per_vote

        points_incr = user.points_per_vote * votes_count
        user.total_votes += votes_count
        user.total_points += points_incr

        user.add_country_alltime(alpha2, points=points_incr, votes=votes_count)
        user.save()

        for scope in self.recap_scopes:
            recap = self.get_recap(scope)
            recap.add(alpha2, points=points_incr, votes=votes_count)
            recap.save()

        new_order = (self.get_order(POINTS), self.get_order(VOTES))
        new_level = user.points_per_vote
        self.update_recap_ranks(prev_order, new_order)
        if old_level != new_level:
            self.role_checks.append(user.user_id)
        return points_incr

    def get_country_stats(self, alpha2: str, scope: str = 'alltime') -> Tuple[int, int, int, int]:
        c_data = self.get_recap(scope).get(alpha2)
        return c_data[VOTES], c_data[POINTS], self.get_rank(alpha2, VOTES, scope), self.get_rank(alpha2, POINTS, scope)

    def vote_args(self, alpha2, c_name: str, fame_user: FameUser, user: User):
        fame_user.update_next_vote(self.cooldown)
        fame_user.save()

        vote_args = {}

        points_incr = self.do_vote(self.get_user(user), alpha2, 1)
        vote_count, point_count, vote_rank, points_rank = self.get_country_stats(alpha2)

        embed = self.get_base_embed(
            user, title=f'Vote for {format_cname(alpha2, c_name)} registered! ({incr_symbol(points_incr)}{millify(points_incr)} pt.)'
        )
        embed.add_field(name='Points',
                        value=f'{millify(point_count)} (#{points_rank}{get_rank_symbol(points_rank)})', inline=True)
        embed.add_field(name='Votes',
                        value=f'{millify(vote_count)} (#{vote_rank}{get_rank_symbol(vote_rank)})', inline=True)

        if self.upload_images:
            if get_banner_path(alpha2).exists():
                banner = get_banner(alpha2)
                embed.set_image(url=f'attachment://{alpha2}.jpg')
                vote_args['file'] = banner
            else:
                flag = get_flag(alpha2)
                embed.set_image(url=f'attachment://{alpha2}.jpg')
                vote_args['file'] = flag
        else:
            if get_banner_path(alpha2).exists():
                embed.set_image(url=f'https://raw.githubusercontent.com/DwarflinDeveloping/FameBot/refs/heads/master/banners/{alpha2}.jpg')
            else:
                embed.set_thumbnail(url=f'https://raw.githubusercontent.com/DwarflinDeveloping/FameBot/refs/heads/master/flags/{alpha2}.png')

        class VoteView(ui.View):
            @ui.button(label='Vote again', style=ButtonStyle.primary, custom_id='again',
                               disabled=False if self.cooldown == 0 else True)
            async def button_callback(self2, button: Button, interaction: Interaction):
                if interaction.user.id != user.id:
                    await interaction.respond(embed=self.get_base_embed(user, f'This is {user.name}\'s voting window! Make your own one using /cvote', error=True), ephemeral=True)
                    return

                if not await self.check_permissions(interaction, False):
                    return

                _fame_user = self.get_user(interaction.user)
                if _fame_user.next_vote and not _fame_user.vote_ready:
                    rem = _fame_user.remaining_cooldown
                    embed = self.get_base_embed(
                        interaction.user, 'Slow down!',
                        description=f'Voting is on cooldown for {ceil(rem)} second{"s" if rem > 1 else ""}.',
                        error=True)
                    await interaction.respond(embed=embed, ephemeral=True)
                    button.disabled = True
                    await interaction.message.edit(view=view)
                    return

                button.disabled = True
                await interaction.edit(view=view)

                _vote_args = self.vote_args(alpha2, c_name, _fame_user, user)
                # if interaction.user.id not in self.users_role_checked:
                await self.check_roles(interaction, fame_user)
                new_resp = await interaction.respond(**_vote_args)
                await _fame_user.wait_cooldown()

                _vote_args['view'].set_again_state(True)
                await new_resp.edit(view=_vote_args['view'])

            def set_again_state(self, value: bool):
                for item in self.children:
                    if type(item) == ui.Button and item.custom_id == 'again':
                        item.disabled = not value
                        break

        view = VoteView()
        vote_args = vote_args | {
            'embed': embed,
            'view': view
        }

        return vote_args

    async def check_permissions(self, ctx: ApplicationContext | Interaction, admin_only: bool) -> bool:
        if admin_only and ctx.user.id not in self.admin_ids:
            description = ':no_entry_sign: You need to be Admin to use this command!'
        elif self.on_maintenance and ctx.user.id not in self.admin_ids:
            description = ':tools: The bot is currently under maintenance.'
        else:
            return True

        await ctx.respond(embed=self.get_base_embed(ctx.author, 'Action failed', description=description, error=True), ephemeral=True)
        return False

    async def check_roles(self, ctx: ApplicationContext | Interaction, fame_user: FameUser):
        if fame_user.user_id not in self.role_checks:
            return

        print('checking roles!')
        guild, channel = ctx.guild, ctx.channel
        user = ctx.author if type(ctx) == ApplicationContext else ctx.user

        if type(user) == Member and guild.id == 378587218849300481:  # only role checking on the FAME server
            for role_id in fame_user.roles:
                role = guild.get_role(role_id)
                if role not in user.roles:
                    await user.add_roles(role)
                    await channel.send(f'{ctx.user.mention} has reached {fame_user.total_votes} votes! You are now a {role.name}!')

        self.role_checks.remove(fame_user.user_id)

    def do_recap(self, user: Member | User | ClientUser, scope: str, continents: bool = False) -> Dict[str, Any]:
        recap = self.get_recap(scope)
        is_recap = scope != 'alltime' and not continents
        point_values, vote_values = None, None
        if continents:
            point_values, vote_values = self.get_top_continents(scope)
        point_strs, vote_strs = dict(), dict()

        for alpha2 in ALPHA2_CONTINENTS if continents else ALPHA2_COUNTRIES:
            vote_dpos, point_dpos = None, None

            if continents:
                c_name = CONTINENT_CODE_TO_NAME[alpha2]
                point_count, vote_count = point_values[alpha2], vote_values[alpha2]
                point_rank, vote_rank = list(point_values.keys()).index(alpha2) + 1, list(vote_values.keys()).index(alpha2) + 1

            else:
                c_data = recap.get(alpha2)
                c_name = format_cname(alpha2, alpha2_to_country(alpha2))
                point_count, vote_count = c_data[POINTS], c_data[VOTES]
                point_rank, vote_rank = self.get_rank(alpha2, POINTS, scope), self.get_rank(alpha2, VOTES, scope)
                if is_recap:
                    vote_dpos, point_dpos = c_data['dpos_votes'], c_data['dpos_points']

            if point_count != 0 or continents:
                point_strs[format_country_ranking(c_name, point_rank, point_count, POINTS, point_dpos, is_recap)] = point_count
            if vote_count != 0 or continents:
                vote_strs[format_country_ranking(c_name, vote_rank, vote_count, VOTES, vote_dpos, is_recap)] = vote_count

        point_strs, vote_strs = sort_dict(point_strs), sort_dict(vote_strs)
        point_str, vote_str = '\n'.join(list(point_strs.keys())[:20]), '\n'.join(list(vote_strs.keys())[:20])

        embed = self.get_base_embed(user, title=f'🌍 Top {scope.lower()} {"continents" if continents else "countries"}')
        embed.add_field(name='Points', value=point_str, inline=True)
        embed.add_field(name='Votes', value=vote_str, inline=True)

        return {'embed': embed}

    @tasks.loop(seconds=5)
    async def recap_task(self):
        await self.bot.wait_until_ready()
        dt = datetime.datetime.now()
        if not dt.minute == 0 or not dt.hour == 0:
            return

        recaps = {'daily': 1363171417612353658}
        if dt.weekday() == 0:
            recaps['weekly'] = 1363171435962433768
        if dt.day == 0:
            recaps['monthly'] = 1363171461954670632
        # TODO add seasonal clear here

        for scope, channel_id in recaps.items():
            recaps_channel = self.bot.get_channel(channel_id)
            await recaps_channel.send(**self.do_recap(self.bot.user, scope))
            del self.loaded_recaps[scope]

        await clear_database(recaps=list(recaps.keys()))
        await asyncio.sleep(100)

    def register_cmds(self):
        country_cmds = SlashCommandGroup('country', 'country-related commands')
        top_cmds = SlashCommandGroup('top', 'leaderboards')
        user_cmds = SlashCommandGroup('user', 'user-related commands')

        @self.bot.slash_command(
            name='cvote',
            description='Cast a vote for a country of your choice!'
        )
        @country_cmds.command(
            name='vote',
            description='Cast a vote for a country of your choice!'
        )
        async def vote_cmd(ctx: ApplicationContext, country: Option(str)):
            if not await self.check_permissions(ctx, False):
                return
            user = self.get_user(ctx.author)
            if user.next_vote and not user.vote_ready:
                rem = user.remaining_cooldown
                embed = self.get_base_embed(
                        ctx.author, 'Slow down!',
                        description=f'Voting is on cooldown for {ceil(rem)} second{"s" if rem>1 else ""}.',
                        error=True)
                await ctx.respond(embed=embed, ephemeral=True)
                return

            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            vote_args = self.vote_args(alpha2, c_name, user, ctx.author)
            # if ctx.author.id not in self.users_role_checked:
            await self.check_roles(ctx, user)
            await ctx.respond(**vote_args)

            await user.wait_cooldown()
            vote_args['view'].set_again_state(True)
            await ctx.edit(view=vote_args['view'])

            # sleep(60)  # voting window expires after some time...
            await asyncio.sleep(30)
            vote_args['view'].set_again_state(False)
            await ctx.edit(view=vote_args['view'])

        @self.bot.slash_command(
            name='reset',
            description='Resting data manually'
        )
        @default_permissions(administrator=True)
        async def reset_cmd(ctx: ApplicationContext, scope: Option(str, choices=['everything', 'users'] + self.recap_scopes)):
            if not await self.check_permissions(ctx, True):
                return

            # self.data = deepcopy(DATA_PRESET)
            self.loaded_recaps, self.loaded_users = {}, {}

            kwargs = {}
            if scope == 'everything':
                kwargs['users'], kwargs['recaps'] = True, True
            elif scope == 'users':
                kwargs['users'] = True
            else:
                kwargs['recaps'] = [scope]
            await clear_database(**kwargs)

            await ctx.respond(embed=self.get_base_embed(ctx.author, f'{scope.capitalize()} cleared', description='Hope you know what you are doing!'), ephemeral=True)

        @country_cmds.command(
            name='set',
            description='Sets votes of a country to a specific amount'
        )
        @default_permissions(administrator=True)
        async def cset_cmd(ctx: ApplicationContext,
                           ctype: Option(str, choices=[VOTES, POINTS]),
                           country: Option(str),
                           amount: Option(int)):
            if not await self.check_permissions(ctx, True):
                return
            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            if ctype not in [VOTES, POINTS]:
                await ctx.respond(embed=self.get_base_embed(ctx.author, 'Unknown ctype!', desccription='Use "votes" or "points".'), ephemeral=True)
                return

            recap = self.get_recap('alltime')
            recap.set(alpha2, **{ctype: amount})
            recap.save()
            await ctx.respond(embed=self.get_base_embed(ctx.author, 'Data changed', description=f'{ctype.capitalize()} for {alpha2_to_country(alpha2)} ({alpha2}) set to {amount}!'), ephemeral=True)

        @country_cmds.command(
            name='clear',
            description='Resets votes for a specific country'
        )
        @default_permissions(administrator=True)
        async def cclear_cmd(ctx: ApplicationContext, country: Option(str)):
            if not await self.check_permissions(ctx, True):
                return
            await cset_cmd(ctx, POINTS, country, 0)
            await cset_cmd(ctx, VOTES, country, 0)

        @country_cmds.command(
            name='info',
            description='Information about a country'
        )
        async def cinfo_cmd(ctx: ApplicationContext, country: Option(str)):
            if not await self.check_permissions(ctx, False):
                return
            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            c_data = self.get_recap('alltime').get(alpha2)
            vote_count, point_count = c_data[VOTES], c_data[POINTS]
            vote_rank, points_rank = self.get_rank(alpha2, VOTES), self.get_rank(alpha2, POINTS)

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

            await ctx.respond(**self.do_recap(ctx.user, 'alltime'))

        @top_cmds.command(
            name='continent',
            description='List of the top continents'
        )
        async def contop_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**self.do_recap(ctx.user, 'alltime', continents=True))

        @self.bot.slash_command(
            name='daily',
            description='Give a daily bonus to a country of your choice!'
        )
        async def daily_cmd(ctx: ApplicationContext, country: Option(str)):
            if not await self.check_permissions(ctx, False):
                return

            fame_user = self.get_user(ctx.user)
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

            fame_user = self.get_user(ctx.author)
            points_incr = self.do_vote(fame_user, alpha2, self.daily_votes)
            # if ctx.author.id not in self.users_role_checked:
            await self.check_roles(ctx, fame_user)

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

            await ctx.respond(embed=embed, file=File(Path(flags_dir, alpha2 + '.png'), filename=alpha2 + '.png'))

        @self.bot.slash_command(
            name='maintenance',
            description='Toggle maintainance mode'
        )
        @default_permissions(administrator=True)
        async def daily_cmd(ctx: ApplicationContext, value: Option(bool)):
            if not await self.check_permissions(ctx, True):
                return
            self.on_maintenance = value

            await ctx.respond(embed=self.get_base_embed(
                ctx.author, f'Maintenance {"activated" if value else "disabled"}!',
                description='Only admins are able to use the bot while active.'), ephemeral=True
            )

        @self.bot.slash_command(
            name='recap',
            description='Generates a recap for a given time frame!'
        )
        async def recap_cmd(ctx: ApplicationContext, scope: Option(str, choices=self.visible_recap_scopes)):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**self.do_recap(ctx.user, scope))

        @user_cmds.command(
            name='info',
            description='Displays information on a user'
        )
        async def uinfo_cmd(ctx: ApplicationContext, user: User):
            if not await self.check_permissions(ctx, False):
                return

            fame_user = self.get_user(user)

            embed = self.get_base_embed(ctx.author, title=f'{user.name}\'s Profile')
            embed.add_field(name='Leveling', value=fame_user.leveling_formatted, inline=False)
            embed.add_field(name='Total votes', value=str(fame_user.total_votes), inline=True)
            embed.add_field(name='Total points', value=str(fame_user.total_points), inline=True)
            embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
            await ctx.respond(embed=embed)

        @self.bot.slash_command(
            name='me',
            description='View your own profile!'
        )
        async def me_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await uinfo_cmd(ctx, ctx.user)

        @self.bot.slash_command(
            name='help',
            description='Help for how to use the FAME Bot'
        )
        async def help_cmd(ctx: ApplicationContext):
            embed1 = Embed(title='How to vote?', description='Use the **/cvote** command with your country\'s name or 2-letter code.\n')
            embed1.add_field(name='Example', value='*Germany* or *DE*')
            embed1.set_image(url='https://raw.githubusercontent.com/DwarflinDeveloping/FameBot/refs/heads/master/images/1.png')
            embed2 = Embed(title='How to view my profile?', description='Use the **/me** command to view your own profile.\n')
            embed2.set_image(url='https://raw.githubusercontent.com/DwarflinDeveloping/FameBot/refs/heads/master/images/2.png')
            embed3 = Embed(title='What other commands are there?',
                           description='- */country info* - Information about a country\n'
                                       '- */daily* - Give 10 daily votes to a country\n'
                                       '- */user info* - Gives information on another user\n'
                                       '- */top country* - Lists the top 20 countries\n'
                                       '- */top continents* - Lists stats for all continents\n'
                                       '- */recap* - Generate a recap for a specific time period')
            embed3.add_field(name='Still questions? Found a bug?', value='We are happy to help you in the FAME discord!\n')
            embed4 = Embed(title='Click here to join', url='https://discord.com/invite/VP8yFSYJWw')
            await ctx.respond(embeds=(embed1, embed2, embed3, embed4), ephemeral=True)

        @self.bot.slash_command(
            name='analyse'
        )
        async def analyse_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, True):
                return

            await ctx.defer(ephemeral=True)
            await self.fetch_votes(ctx.channel)
            await ctx.respond('analysis finished!', ephemeral=True)

        self.bot.add_application_command(country_cmds)
        self.bot.add_application_command(top_cmds)
        self.bot.add_application_command(user_cmds)

    async def fetch_votes(self, channel: TextChannel):
        Path('users2').mkdir(exist_ok=True)
        user_data = {}

        bot_id = self.bot.user.id
        for i, message in enumerate(await channel.history(limit=None).flatten()):
            if not message.author.id == bot_id or not message.embeds:
                continue

            embed = message.embeds[0]
            user = message.guild.get_member_named(embed.footer.text)
            title, user_id = embed.title, user.id
            if not 'registered!' in title:
                continue
            cname = title.split('Vote for', maxsplit=1)[1].split(':flag', maxsplit=1)[0].strip()
            points_count = int(title.split('▲', maxsplit=1)[1].split('pt.', maxsplit=1)[0].strip())
            alpha2 = country_to_alpha2(cname)

            if user_id not in user_data:
                user_data[user_id] = deepcopy(USER_DATA_PRESET)
            if alpha2 not in user_data[user_id]['alltime_country']:
                user_data[user_id]['alltime_country'][alpha2] = PV_PRESET.copy()
            user_data[user_id]['total']['votes'] += 1
            user_data[user_id]['total']['points'] += points_count
            user_data[user_id]['alltime_country'][alpha2]['votes'] += 1
            user_data[user_id]['alltime_country'][alpha2]['points'] += points_count

        for user_id, udata in user_data.items():
            Path('users2', f'{user_id}.json').write_text(json.dumps(udata, indent=2))

    def run(self):
        intents = Intents.default()
        self.bot = Bot(intents=intents)
        self.register_cmds()
        self.recap_task.start()
        self.bot.run(os.getenv('TOKEN'))

        # failsafe to prevent data loss
        bot.save_data()
        for obj in list(self.loaded_users.values()) + list(self.loaded_recaps.values()):
            obj.save()

if __name__ == '__main__':
    load_dotenv()
    bot = FameBot()
    bot.run()
