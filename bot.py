import asyncio
import datetime
import json
import os
import random
from copy import deepcopy
from functools import cached_property
from math import ceil, floor
from pathlib import Path
from pyexpat.errors import messages
from time import time
from typing import Tuple, List, Dict, Any, Iterator, Literal, Optional

import discord
from discord import default_permissions, ApplicationContext, Interaction, Button, User, Member, Option, File, \
    Embed, ButtonStyle, ui, Bot, Intents, SlashCommandGroup, TextChannel, ClientUser, Role, Colour
from discord.ext import tasks
import discord.ui

from data import load_app_data, save_game_data, flags_dir, users_dir, clear_database, USER_DATA_PRESET, \
    PV_PRESET, make_dirs, load_game_data, save_app_data
from data.boosters import RoleUpBooster, Booster, boosters, booster_names, booster_name_to_cls
from data.prices.giveaways import Giveaway, StreakReward
from data.recaps import save_data, FameRecap
from data.resources import get_legacy_path, get_legacy_banner, get_flag, format_embed
from data.titles import RARITY_CHANCES, Title, RARITY_XP
from data.trivia import TriviaManager
from data.users import FameUser
from formatting import get_base_embed, get_title_embed, get_booster_embed, get_streak_embed, get_firedust_embed, \
    get_maxed_titles_embed
from utils import sort_dict, alpha2_to_country, country_to_alpha2, ALTERNATIVE_CNAMES, incr_symbol, \
    millify, get_rank_symbol, CONTINENT_CODE_TO_NAME, points_per_capita, country_to_continent, format_country_ranking, \
    format_cname, POINTS, VOTES, CTYPES, ALPHA2_COUNTRIES, format_user_ranking


class FameBot:
    def __init__(self, cooldown: float = 5, daily_votes: int = 30, recap_scopes: List[str] = None,
                 leaderboard_topics: List[str] = None, upload_images: bool = False, min_daily_votes: int = 30,
                 daily_boost_count: int = 5, daily_boost_factor: float = 1, max_equipped_titles: int = 5,
                 title_daily_limit: int = 100):
        if recap_scopes is None:
            self.visible_recap_scopes = ['daily', 'weekly', 'seasonal']
            self.recap_scopes = self.visible_recap_scopes + ['alltime']
        else:
            self.recap_scopes = recap_scopes

        if leaderboard_topics is None:
            self.leaderboard_topics = ['users', 'countries', 'continents']
        else:
            self.leaderboard_topics = leaderboard_topics

        self.cooldown = cooldown
        self.daily_votes = daily_votes
        self.upload_images = upload_images
        self.min_daily_votes = min_daily_votes
        self.daily_boost_count = daily_boost_count
        self.daily_boost_factor = daily_boost_factor
        self.max_equipped_titles = max_equipped_titles
        self.title_daily_limit = title_daily_limit

        self.bot: Bot | None = None
        self.title_roles = None
        self.app_data = load_app_data()
        self.game_data = load_game_data()
        self.trivia = TriviaManager()
        self.role_checks: List[int] = []
        self.loaded_users: Dict[int, FameUser] = {}
        self.cached_users: Dict[int, discord.User] = {}
        self.loaded_recaps: Dict[str, FameRecap] = {}

        make_dirs()

    @property
    def token(self) -> str:
        return os.getenv('TOKEN')

    @property
    def is_test_build(self) -> bool:
        is_test = os.getenv('TESTING')
        return is_test.lower().capitalize() == str(True) if is_test is not None else False

    @property
    def users(self) -> Iterator[FameUser]:
        for file in os.listdir(users_dir):
            user_id = int(file.split('.')[0])
            yield self.get_user(user_id)

    @property
    def total_votes(self) -> int:
        recap = self.get_recap('alltime')
        return sum(recap.get(alpha2)[VOTES] for alpha2 in ALPHA2_COUNTRIES)

    @property
    def total_points(self) -> int:
        recap = self.get_recap('alltime')
        return sum(recap.get(alpha2)[POINTS] for alpha2 in ALPHA2_COUNTRIES)

    def save(self) -> None:
        self.save_game_data()
        self.save_app_data()

        for obj in list(self.loaded_users.values()) + list(self.loaded_recaps.values()):
            obj.save()

    def save_game_data(self) -> None:
        save_game_data(self.game_data)

    def save_app_data(self) -> None:
        save_app_data(self.app_data)

    @property
    def daily_giveaway(self) -> Giveaway | None:
        giveaway = self.game_data['daily_giveaway']
        if giveaway is None:
            return None
        return Giveaway.from_dict(giveaway)

    @daily_giveaway.setter
    def daily_giveaway(self, value: Giveaway) -> None:
        self.game_data['daily_giveaway'] = dict(value) if value is not None else None
        self.save_game_data()

    @property
    def daily_boosted_countries(self) -> List[str]:
        boosted = self.game_data['daily_boosted_countries']
        return [] if not boosted else boosted

    @daily_boosted_countries.setter
    def daily_boosted_countries(self, value: List[str]) -> None:
        self.game_data['daily_boosted_countries'] = value
        self.save_game_data()

    @property
    def on_maintenance(self) -> bool:
        return self.game_data['maintenance']

    @on_maintenance.setter
    def on_maintenance(self, value: bool) -> None:
        self.game_data['maintenance'] = value

    @property
    def admin_guilds(self) -> List[int]:
        return self.app_data['admin_guilds']

    @property
    def main_guild(self) -> int:
        return self.app_data['main_guild']

    @cached_property
    def giveaway_channel(self) -> TextChannel:
        return self.bot.get_channel(self.app_data['giveaway_channel'])

    @cached_property
    def role_up_channel(self) -> TextChannel:
        return self.bot.get_channel(self.app_data['role_up_channel'])

    @cached_property
    def daily_boosts_channel(self) -> TextChannel:
        return self.bot.get_channel(self.app_data['daily_boosts_channel'])

    @property
    def admin_ids(self) -> List[int]:
        return self.app_data['admins']

    @property
    def progression_roles(self) -> Dict[int, int]:
        return {int(key): val for key, val in self.app_data['progression_roles'].items()}

    @property
    def title_role_ids(self) -> Dict[str, List[int]]:
        return self.app_data['title_roles']

    @property
    def titles(self) -> Iterator[Title]:
        for rarity, titles in self.title_roles.items():
            for title_role in titles:
                yield Title(title_role.name, rarity)

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
            embed = get_base_embed(ctx.author,f'Unknown country {inp}!', description=' Please use a 2-letter code or the full name.', error=True)
            embed.add_field(name='Example:', value='*Germany* or *DE*')
            await ctx.respond(embed=embed, ephemeral=True)
            return None

        else:
            return alpha2, alpha2_to_country(alpha2)  # valid country name converted to alpha2

    def get_user(self, user_id: int) -> FameUser:
        if user_id in self.loaded_users:
            return self.loaded_users[user_id]

        fame_user = FameUser.from_file(user_id)
        self.loaded_users[user_id] = fame_user
        return fame_user

    async def fetch_dc_user(self, user_id: int) -> discord.User:
        if user_id in self.cached_users:
            return self.cached_users[user_id]

        user = await self.bot.fetch_user(user_id)
        self.cached_users[user_id] = user
        return user

    def get_recap(self, scope: str) -> FameRecap:
        if scope in self.loaded_recaps:
            return self.loaded_recaps[scope]

        recap = FameRecap.from_file(scope)
        self.loaded_recaps[scope] = recap
        return recap

    def get_top_users(self) -> Dict[int, int]:
        level_values = dict()
        for user in self.users:
            level_values[user.user_id] = user.leveling

        return sort_dict(level_values)

    def get_top_countries(self, scope: str) -> Tuple[Dict[str, int], Dict[str, int]]:
        recap = self.get_recap(scope)

        point_values, vote_values = dict(), dict()
        for alpha2 in ALPHA2_COUNTRIES:
            c_data = recap.get(alpha2)
            point_values[alpha2] = c_data[POINTS]
            vote_values[alpha2] = c_data[VOTES]

        return sort_dict(point_values), sort_dict(vote_values)

    def get_top_trivia(self, scope: str, category: str) -> Tuple[Dict[str, int], Dict[str, int]]:
        mappings = self.trivia.get_mappings(category)
        recap = self.get_recap(scope)

        point_values, vote_values = dict(), dict()
        for alpha2 in ALPHA2_COUNTRIES:
            key = mappings.get(alpha2, None)
            if not key:
                continue
            if category == 'OfficialLang' and ',' in key:
                key = key.split(',', maxsplit=1)[0]

            if key not in point_values:
                point_values[key] = 0
            if key not in vote_values:
                vote_values[key] = 0

            c_data = recap.get(alpha2)
            point_values[key] += c_data[POINTS]
            vote_values[key] += c_data[VOTES]

        return sort_dict(point_values), sort_dict(vote_values)

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

    def get_random_title(self) -> Tuple[Role, str]:
        roles = []
        weights = []

        if self.title_roles is None:
            print('Bot not ready!')
            raise AssertionError

        for rarity, role_list in self.title_roles.items():
            chance = RARITY_CHANCES.get(rarity)
            per_role_weight = chance / len(role_list)
            roles.extend([(role, rarity) for role in role_list])
            weights.extend([per_role_weight] * len(role_list))

        roles.append(None)
        weights.append(1 - sum(weights))

        return random.choices(roles, weights=weights, k=1)[0]

    def spawn_titles(self, user: FameUser) -> Embed | None:
        result = self.get_random_title()
        if result is None:
            return None

        role, rarity = result
        title = Title(role.name, rarity)
        compensation = title.apply(user)
        if not compensation:
            self.role_checks.append(user.user_id)

        return get_title_embed(title, compensation)

    def get_random_firedust(self) -> int | None:
        # firedust_chance = 1
        firedust_chance = .025
        firedust_found = random.random() <= firedust_chance
        if not firedust_found:
            return None

        return random.choices([10, 20, 30, 40, 50, 100, 200], weights=[5, 10, 10, 10, 10, 2, 1], k=1)[0]

    def spawn_firedust(self, user: FameUser) -> Embed | None:
        amount = self.get_random_firedust()
        if amount is None:
            return None

        user.found_firedust += amount
        return get_firedust_embed(amount)

    def spawn_boosters(self, user: FameUser, guaranteed: bool = False) -> discord.Embed | None:
        user.check_starter_booster()
        booster_found = random.random() <= .025
        if guaranteed or booster_found:
            result = Booster.get_random()
        else:
            return None

        if result is None:
            return None

        booster = result
        user.add_booster(booster)
        user.last_booster = 0
        embed = get_booster_embed(booster)
        return embed

    def do_vote(self, user: FameUser, alpha2: str, votes_count: int, booster_applies: bool = True,
                gives_xp: bool = True) -> Tuple[int, int]:
        prev_order = (self.get_order(POINTS), self.get_order(VOTES))
        old_level = user.level

        points_gained, xp_gained = user.do_vote(votes_count, alpha2, self.daily_boosted_countries, self.daily_boost_factor, booster_applies, gives_xp)

        for scope in self.recap_scopes:
            recap = self.get_recap(scope)
            recap.add(alpha2, points=points_gained, votes=votes_count)
            recap.save()

        new_order = (self.get_order(POINTS), self.get_order(VOTES))
        new_level = user.level
        self.update_recap_ranks(prev_order, new_order)
        if old_level != new_level or user.total_votes == 1:
            self.role_checks.append(user.user_id)

        special_title = Title('Denis the Menace', 'SPECIAL')
        if not user.has_title(special_title.name) and user.total_votes >= 10_000:
            user.add_title(special_title)
            user.save()
            self.role_checks.append(user.user_id)

        return points_gained, xp_gained

    def get_country_stats(self, alpha2: str, scope: str = 'alltime') -> Tuple[int, int, int, int]:
        c_data = self.get_recap(scope).get(alpha2)
        return c_data[VOTES], c_data[POINTS], self.get_rank(alpha2, VOTES, scope), self.get_rank(alpha2, POINTS, scope)

    def vote_args(self, alpha2, c_name: str, fame_user: FameUser, user: User) -> Dict[str, Any]:
        booster_embed = self.spawn_boosters(fame_user, guaranteed=True if fame_user.last_booster >= 75 else False)
        title_embed = self.spawn_titles(fame_user)
        dust_embed = self.spawn_firedust(fame_user)

        fame_user.update_next_vote(self.cooldown)
        fame_user.daily_votes += 1
        if booster_embed is None:
            fame_user.last_booster += 1

        quest_embed = None
        for i, quest in enumerate(list(fame_user.daily_quests)):
            possible_countries = list(quest.get_countries(self.trivia))
            update = False
            if alpha2 in possible_countries:
                quest.progress += 1
                update = True

            if quest.finished and not quest.claimed:
                quest.apply(fame_user)
                quest.claimed = True
                update = True
                quest_embed = get_base_embed(
                    user, ':pencil: Quest completed!',
                    description=f'You have gained the following rewards:\n{quest}\n\n'
                                'View your active quests using **/quests**. All quests are reset every 24 hours.'
                )

            if update:
                fame_user.update_quest(quest, i)

        fame_user.save()

        vote_args = {'embeds': []}
        active_booster = fame_user.active_booster
        symbol_str = ''
        if alpha2 in self.daily_boosted_countries:
            symbol_str += ':sunny:'
        if active_booster is not None:
            symbol_str += active_booster.symbol + ' '

        old_role = fame_user.get_role(self.progression_roles)
        points_gained, xp_gained = self.do_vote(self.get_user(user.id), alpha2, 1)
        new_role = fame_user.get_role(self.progression_roles)
        role_up = new_role != old_role

        vote_count, point_count, vote_rank, points_rank = self.get_country_stats(alpha2)
        user_rank = list(self.get_top_users().keys()).index(fame_user.user_id) + 1

        maxed_titles_embed = None
        maxed_titles = [title for title in fame_user.titles if title.daily_votes == self.title_daily_limit]
        if maxed_titles:
            maxed_titles_embed = get_maxed_titles_embed(maxed_titles)

        embed = get_base_embed(
            user, title=f'{symbol_str}Vote for {format_cname(alpha2, c_name)} registered! ({incr_symbol(points_gained)}{millify(points_gained)} pt.)'
        )
        if alpha2 in self.daily_boosted_countries:
            embed.colour = discord.Colour.yellow()
        elif active_booster is not None:
            embed.colour = active_booster.color
        left_duration = fame_user.active_booster.left_duration if fame_user.has_active_booster else 0
        embed.add_field(name='Country stats',
                        value=f'Points: {millify(point_count)} (#{points_rank}{get_rank_symbol(points_rank)})\n'
                              f'Votes: {millify(vote_count)} (#{vote_rank}{get_rank_symbol(vote_rank)})',
                        inline=True)
        embed.add_field(name='Your stats',
                        value=f'Level: {fame_user.level} (#{user_rank}{get_rank_symbol(user_rank)})\n'
                              f'+{xp_gained}xp ({ceil(fame_user.xp_until_next_level)}xp until next level)' +
                              (f'\nBooster duration: {active_booster.left_duration} -> {left_duration}' if active_booster is not None else ''),
                        inline=True)

        format_embed(vote_args, embed, alpha2, True, active_booster)

        class VoteView(ui.View):
            @staticmethod
            async def check_user(interaction: Interaction):
                if interaction.user.id != user.id:
                    await interaction.respond(embed=get_base_embed(user, f'This is {user.name}\'s voting window! Make your own one using /cvote', error=True), ephemeral=True)
                    return False
                return True

            @ui.button(label='Vote again', style=ButtonStyle.primary, custom_id='again',
                       disabled=False if self.cooldown == 0 else True)
            async def again_callback(self2, button: Button, interaction: Interaction):
                if not await self2.check_user(interaction) or not await self.check_permissions(interaction, False):
                    return

                _fame_user = self.get_user(interaction.user.id)
                if _fame_user.next_vote and not _fame_user.vote_ready:
                    rem = _fame_user.remaining_cooldown
                    embed = get_base_embed(
                        interaction.user, 'Slow down!',
                        description=f'Voting is on cooldown for {ceil(rem)} second{"s" if rem > 1 else ""}.',
                        error=True)
                    await interaction.respond(embed=embed, ephemeral=True)
                    self2.disable_all_items()
                    await interaction.message.edit(view=view)
                    return

                self2.disable_all_items()
                await interaction.edit(view=view)

                _vote_args = self.vote_args(alpha2, c_name, _fame_user, user)
                await self.check_streak(interaction, _fame_user)
                await self.check_roles(interaction, fame_user)
                new_resp = await interaction.respond(**_vote_args)

                await _fame_user.wait_cooldown()
                _vote_args['view'].set_again_state(True)
                await new_resp.edit(view=_vote_args['view'])

                await asyncio.sleep(60)
                _vote_args['view'].disable_all_items()
                await new_resp.edit(view=_vote_args['view'])

            if fame_user.boosters_available and not fame_user.has_active_booster:
                @ui.button(label='Boosters available', style=ButtonStyle.red, custom_id='boosters')
                async def boosters_callback(self2, button: Button, interaction: Interaction):
                    if not await self2.check_user(interaction):
                        return
                    await interaction.respond(**self.activate_booster_args(interaction))

            def set_again_state(self, value: bool):
                for item in self.children:
                    if type(item) == ui.Button and item.custom_id == 'again':
                        item.disabled = not value
                        break

        vote_args['embeds'].append(embed)
        for embed in [booster_embed, title_embed, quest_embed, dust_embed, maxed_titles_embed]:
            if embed is not None:
                vote_args['embeds'].append(embed)
        if role_up:
            booster = RoleUpBooster()
            fame_user.add_booster(booster)
            vote_args['embeds'].append(get_booster_embed(booster))

        view = VoteView()
        vote_args['view'] = view
        return vote_args

    def quest_args(self, ctx: ApplicationContext | Interaction):
        fame_user = self.get_user(ctx.user.id)
        fame_user.check_starter_booster()
        if len(list(fame_user.data['daily_quests'])) == 0:
            fame_user.reset_daily_quests(self.trivia, 5, list(self.titles))
        embed = get_base_embed(ctx.user,':pencil: Your active quests')

        for quest in fame_user.daily_quests:
            embed.add_field(name=quest.formatted_name,
                            value=f'{quest.formatted_description}\n' +
                                  (f'Progress: {quest.progress}/{quest.requirement}' if not quest.finished else 'Finished!') +
                                  f'\n{quest}',
                            inline=False)

        class DetailView(ui.View):
            @staticmethod
            async def check_user(interaction: Interaction):
                if interaction.user.id != ctx.user.id:
                    await interaction.respond(embed=get_base_embed(ctx.user, f'This is {ctx.user.name}\'s quest menu! Make your own one using /cvote', error=True), ephemeral=True)
                    return False
                return True

            @ui.button(label='Details', style=ButtonStyle.primary, custom_id='details')
            async def details_callback(self2, button: Button, interaction: Interaction):
                if not await self2.check_user(interaction) or not await self.check_permissions(interaction, False):
                    return

                embed2 = get_base_embed(ctx.user,':pencil2: Quest details')
                for quest2 in fame_user.daily_quests:
                    possible_countries = list(quest2.get_countries(self.trivia))
                    embed2.add_field(name=quest2.formatted_name,
                                     value=', '.join(possible_countries) if len(possible_countries) >= 0 else '',
                                     inline=False)
                await interaction.respond(embed=embed2)

        return {'embed': embed, 'view': DetailView()}

    def activate_booster_args(self, ctx: ApplicationContext | Interaction):
        fame_user = self.get_user(ctx.user.id)
        fame_user.check_starter_booster()
        has_boosters = len(list(fame_user.boosters)) > 0
        embed = get_base_embed(ctx.user, 'Your Boosters' if has_boosters else 'No boosters in inventory! Keep voting to gain some!')

        for booster, count in fame_user.boosters:
            embed.add_field(name=booster.format_name(count),
                            value=f'Boost factor: {booster.format_boost()} (20xp -> {floor(20 * (1 + booster.boost))}xp)\n'
                                  f'Duration: {booster.format_duration()} votes',
                            inline=False)

        class BoosterSelect(discord.ui.View):
            if has_boosters:
                @discord.ui.select(
                    options=[discord.SelectOption(label=b.name, emoji=b.symbol) for b, _ in fame_user.boosters],
                    placeholder='Select a booster to activate' if not fame_user.has_active_booster else f'Active booster: {fame_user.active_booster.name}',
                    max_values=1,
                    min_values=1,
                    disabled=fame_user.has_active_booster
                )
                async def select_callback(self2, select: ui.Select, interaction: Interaction):
                    if interaction.user.id != fame_user.user_id:
                        await interaction.respond(
                            embed=get_base_embed(interaction.user, f'This is {ctx.user.name}\'s booster menu! Make your own one using /boosters', error=True),
                            ephemeral=True
                        )
                        return
                    if fame_user.has_active_booster:
                        await interaction.respond(
                            embed=get_base_embed(
                                interaction.user, 'Already active!',
                                description=f'You already have a booster active! The current one runs out in {fame_user.active_booster.left_duration} votes.',
                                error=True
                            ), ephemeral=True
                        )
                        return
                    boo = Booster.from_name(select.values[0])()
                    fame_user.activate_booster(boo)
                    emb = get_base_embed(
                        interaction.user,
                        title=f'{boo.symbol} You have activated a {boo.name}!',
                        description=f'Your points and xp gains will increase by {boo.format_boost()} for the next {boo.left_duration} votes.',
                        colour=boo.color
                    )
                    await interaction.respond(embed=emb)

        return {'embed': embed, 'view': BoosterSelect()}

    def title_args(self, ctx: ApplicationContext | Interaction):
        fame_user = self.get_user(ctx.user.id)
        fame_user.check_starter_booster()
        has_boosters = len(list(fame_user.boosters)) > 0
        if list(fame_user.titles):
            descr = f'Total gain from titles: {fame_user.title_xp_incr}xp (20xp -> {20 + fame_user.title_xp_incr}xp)'
        else:
            descr = 'You don\'t have any titles yet! Keep voting to gain some.'
        embed = get_base_embed(ctx.user, 'Your Titles', description=descr)

        for rarity, role_list in self.title_roles.items():
            txt, example_title = '', None
            for role in role_list:
                example_title = Title(role.name, rarity)
                if fame_user.has_title(role.name):
                    title = fame_user.get_title(role.name)
                    descr = f'' if not title.is_maxed else ', :x: Maxed out' if title.is_upgradable else ', :x: Not upgradable'
                    upgrade_cost = title.upgrade_cost
                    txt += f'{title.name} (Lvl. {title.leveling}{descr})\n'
                else:
                    txt += '???\n'

            embed.add_field(
                name=' '.join([s.capitalize() for s in rarity.lower().split('_')]) + f' +{RARITY_XP.get(rarity)}xp' +
                     (f' (Upgrade Cost: {example_title.upgrade_cost} :sparkles: Firedust)' if example_title.is_upgradable else ''),
                value=txt,
                inline=False)

        class UpgradeSelection(discord.ui.View):
            @discord.ui.select(
                options=[discord.SelectOption(label=title.name, description=f'Cost: {title.upgrade_cost}') for title in fame_user.titles if title.is_upgradable],
                placeholder='Select a title to upgrade',
                max_values=1,
                min_values=1
            )
            async def select_callback(self2, select: ui.Select, interaction: Interaction):
                if interaction.user.id != fame_user.user_id:
                    await interaction.respond(
                        embed=get_base_embed(interaction.user, f'This is {ctx.user.name}\'s title menu! Make your own one using /titles', error=True),
                        ephemeral=True
                    )
                    return

                title_rarity = None
                for rarity_ in RARITY_XP.keys():
                    if any(r.name == select.values[0] for r in self.title_roles[rarity_]):
                        title_rarity = rarity_

                title_ = Title(select.values[0], title_rarity)
                if fame_user.total_firedust < title_.upgrade_cost:
                    await interaction.respond(
                        embed=get_base_embed(interaction.user,
                                             f'You need **{title_.upgrade_cost} :sparkles: Firedust** to upgrade this title!',
                                             error=True),
                        ephemeral=True
                    )
                    return

                fame_user.upgrade_title(title_.name)
                new_title = fame_user.get_title(title_.name)
                emb = get_base_embed(
                    interaction.user,
                    title=f':arrow_up_small: You have upgraded {title_.name} to **Lvl. {new_title.leveling}**!',
                    description=f'This title now gives you +{new_title.xp_incr}xp per vote.'
                )
                await interaction.respond(embed=emb)

        kwargs = {'embed': embed}
        if len(list(fame_user.titles)) > 0:
            kwargs['view'] = UpgradeSelection()
        return kwargs

    def title_equip_args(self, ctx: ApplicationContext | Interaction):
        fame_user = self.get_user(ctx.user.id)
        embed = get_base_embed(ctx.user, ':shield: Equipped Titles',
                               description='Equip titles to earn one **:coin: BotCoin** per vote.\n'
                                           f'Each title can give a daily maximum of {self.title_daily_limit} :coin: BotCoins.\n'
                                           f'Purse: **{fame_user.total_coins} :coin: BotCoins**')
        equipped_titles = list(fame_user.equipped_titles)

        for title in fame_user.equipped_titles:
            is_maxed = title.daily_votes >= self.title_daily_limit
            embed.add_field(name=(':white_check_mark: ' if title.is_equipped else ':x: ') + title.name,
                            value=f'Daily votes: {title.daily_votes}/{self.title_daily_limit}' + (' **Maxed!**' if is_maxed else ''),
                            inline=False)

        class EquipView(ui.View):
            def __init__(self2):
                super().__init__(timeout=None)
                self2.equipped_titles = equipped_titles
                self2.fame_user = fame_user
                self2.ctx = ctx

                # Disequip buttons for currently equipped titles
                for i, t in enumerate(self2.equipped_titles):
                    btn = ui.Button(label=t.name, style=ButtonStyle.red, custom_id=f'disequip_{i}')

                    async def disequip_btn(interaction: Interaction, title_name=t.name):
                        if not self2.fame_user.get_title(title_name).is_equipped:
                            await interaction.response.send_message(
                                embed=get_base_embed(self2.ctx.user, f'Not equipped!',
                                                     description=f'This title is no longer equipped', error=True),
                                ephemeral=True
                            )
                            return
                        self2.fame_user.equip_title(title_name, False)
                        disequipped_title = self2.fame_user.get_title(title_name)
                        await interaction.response.send_message(embed=get_base_embed(
                            self2.ctx.user, f'{disequipped_title.name} disequipped',
                            description='Equip a new title in the free slot to gain more **:coin: BotCoins**'
                        ))
                        await self2.ctx.edit(**self.title_equip_args(self2.ctx))

                    btn.callback = disequip_btn
                    self2.add_item(btn)

                # Equip buttons for unequipped titles
                for i, t in enumerate(
                        [user_title for user_title in self2.fame_user.titles if not user_title.is_equipped and user_title.is_equipable]):
                    btn = ui.Button(label=t.name, style=ButtonStyle.green, custom_id=f'equip_{i}')

                    async def equip_btn(interaction: Interaction, title_name=t.name):
                        if len(self2.equipped_titles) >= self.max_equipped_titles:
                            await interaction.response.send_message(
                                embed=get_base_embed(self2.ctx.user, f'Too many equipped titles!',
                                                     description=f'You can\'t equip more than {self.max_equipped_titles} titles at a time!',
                                                     error=True),
                                ephemeral=True
                            )
                            return
                        elif self2.fame_user.get_title(title_name).is_equipped:
                            await interaction.response.send_message(
                                embed=get_base_embed(self2.ctx.user, f'Already equipped!',
                                                     description=f'You already have this title equipped.',
                                                     error=True),
                                ephemeral=True
                            )
                            return
                        self2.fame_user.equip_title(title_name, True)
                        equipped_title = self2.fame_user.get_title(title_name)
                        await interaction.response.send_message(embed=get_base_embed(
                            self2.ctx.user, f'{equipped_title.formatted_rarity} Title {equipped_title.name} equipped!',
                            description='You will gain **:coin: BotCoins** from voting with this title.'
                        ))
                        await self2.ctx.edit(**self.title_equip_args(self2.ctx))

                    btn.callback = equip_btn
                    self2.add_item(btn)



        kwargs = {'embed': embed}
        if list(fame_user.titles):
            kwargs['view'] = EquipView()
        return kwargs

    def booster_shop_args(self, ctx: ApplicationContext | Interaction):
        fame_user = self.get_user(ctx.user.id)
        embed = get_base_embed(ctx.user, ':arrow_double_up: Booster Shop')

        embed.add_field(name='Your Firedust',
                        value=f'**{fame_user.total_firedust} :sparkles: Firedust**',
                        inline=False)

        for booster in boosters:
            if booster.firedust_cost is None:
                continue

            embed.add_field(name=booster.formatted_name if fame_user.total_firedust >= booster.firedust_cost else f'**:x: {booster.name}**',
                            value=f'Cost: **{booster.firedust_cost} :sparkles: Firedust**\n' \
                                  f'Boost factor: {booster.format_boost()} (20xp -> {floor(20 * (1 + booster.boost))}xp)\n',
                            inline=False)

        class BoosterSelect(discord.ui.View):
            @discord.ui.select(
                options=[discord.SelectOption(label=b.name, emoji=b.symbol) for b in boosters if b.firedust_cost],
                placeholder='Select a booster to purchase',
                max_values=1,
                min_values=1
            )
            async def select_callback(self2, select: ui.Select, interaction: Interaction):
                if interaction.user.id != fame_user.user_id:
                    await interaction.respond(
                        embed=get_base_embed(interaction.user, f'This is {ctx.user.name}\'s booster menu! Make your own one using /boosters', error=True),
                        ephemeral=True
                    )
                    return

                boo = Booster.from_name(select.values[0])()
                if fame_user.total_firedust < boo.firedust_cost:
                    await interaction.respond(
                        embed=get_base_embed(interaction.user,
                                             f'You need **{boo.firedust_cost} :sparkles: Firedust** to purchase one {boo.formatted_name}',
                                             error=True),
                        ephemeral=True
                    )
                    return

                fame_user.purchase_booster(boo)
                emb = get_base_embed(
                    interaction.user,
                    title=f'{boo.symbol} You have purchased a {boo.name}!',
                    description=f'Active boosters using **/boosters**.',
                    colour=boo.color
                )
                await interaction.respond(embed=emb)

        return {'embed': embed, 'view': BoosterSelect()}

    async def check_permissions(self, ctx: ApplicationContext | Interaction, admin_only: bool) -> bool:
        is_admin = ctx.user.id in self.admin_ids
        if self.title_roles is None:
            description = ':hourglass: The bot is not yet ready...'
        elif admin_only and not is_admin:
            description = ':no_entry_sign: You need to be Admin to use this command!'
        elif self.on_maintenance and ctx.user.id not in self.admin_ids:
            description = ':tools: The bot is currently under maintenance.'
        elif (not hasattr(ctx.channel, 'category_id') or not ctx.channel.category_id or ctx.channel.category_id != 1361995334246469703) \
              and not is_admin and not self.is_test_build:
            description = 'FAME Vote can only be used in the voting channels of the FAME server.'
        else:
            return True

        await ctx.respond(embed=get_base_embed(ctx.author, 'Action failed', description=description, error=True), ephemeral=True)
        return False

    async def check_roles(self, ctx: ApplicationContext | Interaction, fame_user: FameUser):
        if fame_user.user_id not in self.role_checks:
            return

        if type(ctx) == ApplicationContext:
            await ctx.defer()

        guild, channel = ctx.guild, self.role_up_channel
        user = ctx.author if type(ctx) == ApplicationContext else ctx.user

        if type(user) != Member or guild.id != self.main_guild:
            return  # only role checking on the FAME server

        present_roles = user.roles
        wanted_roles = [role for role in sum(self.title_roles.values(), []) if fame_user.has_title(role.name)]
        wanted_roles.append(guild.get_role(fame_user.get_role(self.progression_roles)))

        all_roles = list(self.progression_roles.values()) + sum(self.title_role_ids.values(), [])
        for role_id in all_roles:
            role = guild.get_role(role_id)
            if role in present_roles and not role in wanted_roles:
                await user.remove_roles(role)
            elif role not in present_roles and role in wanted_roles:
                await user.add_roles(role)
                if role_id in self.progression_roles.values():  # is progression role
                    await channel.send(f'{ctx.user.mention} has reached seasonal **Lvl. {fame_user.current_level}**! You are now a {role.name}!')
                elif role_id == 1365849684177981621:
                    await channel.send(f'{ctx.user.mention} has reached **10,000 votes**! You have been awarded {role.name}')

        self.role_checks.remove(fame_user.user_id)

    async def check_streak(self, ctx: ApplicationContext | Interaction, fame_user: FameUser) -> None:
        if fame_user.daily_votes != self.min_daily_votes:
            return
        fame_user.daily_streak += 1

        dc_user = await self.fetch_dc_user(fame_user.user_id)
        await self.giveaway_channel.send(f'{dc_user.mention} has joined the giveaway! Your daily streak is now {fame_user.daily_streak}.')

        reward = StreakReward.generate(fame_user.daily_streak, list(self.titles))
        reward.apply(fame_user)
        self.role_checks.append(fame_user.user_id)

        embed = get_streak_embed(reward)
        await ctx.channel.send(dc_user.mention, embed=embed)

    def reset_daily_users(self) -> None:
        for user in self.users:
            if user.daily_votes < self.min_daily_votes:
                user.daily_streak = 0
            user.daily_votes = 0

            user.reset_daily_quests(self.trivia, 5, list(self.titles))
            user.reset_daily_votes()

            user.save()

    async def create_giveaway(self) -> None:
        giveaway = Giveaway.generate(list(self.titles))
        self.daily_giveaway = giveaway

        embed = get_base_embed(self.bot.user, ':gift: Daily giveaway',
                                    description='Today\'s rewards:\n' + str(giveaway))
        embed.add_field(name='How to participate?',
                        value=f'Anyone who does {self.min_daily_votes} or more votes in the next 24 hours enters the giveaway.')
        await self.giveaway_channel.send(embed=embed)

    async def create_daily_boost(self) -> None:
        giveaway = Giveaway.generate(list(self.titles))
        self.daily_giveaway = giveaway

        countries = random.choices(ALPHA2_COUNTRIES, k=self.daily_boost_count)
        countries_str = '\n'.join([f'- {format_cname(alpha2, alpha2_to_country(alpha2))}' for alpha2 in countries])
        self.daily_boosted_countries = countries

        embed = get_base_embed(self.bot.user, ':sunny: Solar Flare',
                                    description=f'Points for the following countries are doubled today:\n\n{countries_str}')
        await self.daily_boosts_channel.send(embed=embed)

    async def resolve_giveaway(self):
        assert self.daily_giveaway is not None  # daily giveaway should always exist
        participating = [user for user in self.users if user.daily_votes >= self.min_daily_votes]
        if not participating:
            await self.giveaway_channel.send(
                embed=get_base_embed(self.bot.user, 'No participants in the daily giveaway.')
            )
            return

        winner = random.choice(participating)
        self.daily_giveaway.apply(winner)

        winner_dc = await self.fetch_dc_user(winner.user_id)
        embed = get_base_embed(winner_dc, f'{winner_dc.display_name} has won!',
                                    description=f'You have gained the following rewards:\n{self.daily_giveaway}')
        await self.giveaway_channel.send(embed=embed)
        self.daily_giveaway = None

    async def generate_chances(self, user: Member | User | ClientUser, topic: str) -> Dict[str, Any]:
        embed = get_base_embed(user, f'{topic.lower().capitalize()} chances')

        if topic == 'booster':
            abs_weight = sum(booster.spawn_chance for booster in boosters)
            for booster in boosters:
                if booster.spawn_chance == 0:
                    continue
                rel_chance = booster.spawn_chance / abs_weight
                abs_chance = .025 * rel_chance
                embed.add_field(name=booster.format_name(), value=f'Relative Chance: {round(rel_chance*100, 2)}%\n'
                                                                  f'Absolute Chance: {round(abs_chance*100, 3)}%\n'
                                                                  f'1 in {ceil(1 / abs_chance)} votes',
                                inline=False)
        elif topic == 'title':
            for title in self.titles:
                if title.spawn_chance == 0:
                    continue
                abs_chance = title.spawn_chance
                embed.add_field(name=title.name, value=f'Absolute Chance: {round(abs_chance * 100, 3)}%\n'
                                                       f'1 in {ceil(1 / abs_chance)} votes', inline=False)

        kwargs = {'embed': embed}
        return kwargs

    async def generate_leaderboard(self, user: Member | User | ClientUser, scope: str, topic: str, page: int = 1,
                             entries_per_page: int = 20) -> Dict[str, Any]:
        is_recap = scope != 'alltime'
        topic_str = topic.lower()
        recap = None
        if topic == 'countries':
            recap = self.get_recap(scope)
            point_values, vote_values = self.get_top_countries(scope)
            values = {'points': point_values, 'votes': vote_values}
        elif topic == 'users':
            values = {'levels': self.get_top_users()}
        else:
            if topic == 'Continent':
                topic_str = 'continents'
            elif topic == 'ReligionPrimary':
                topic_str = 'majority religions'
            elif topic == 'RegionName':
                topic_str = 'regions'
            elif topic == 'OfficialLang':
                topic_str = 'languages'

            point_values, vote_values = self.get_top_trivia(scope, topic)
            values = {'points': point_values, 'votes': vote_values}

        max_pages = 0
        embed = get_base_embed(user, title=f':earth_africa: Top {scope.lower()} {topic_str}')
        for ctype, data in values.items():
            str_list = []
            for item_indicator, count in data.items():
                if count == 0:
                    continue

                rank = list(data.keys()).index(item_indicator) + 1

                if topic == 'users':
                    user_id = int(item_indicator)
                    fame_user = self.get_user(user_id)
                    dc_user = await self.fetch_dc_user(user_id)
                    if count <= 1:
                        continue
                    ranking_str = format_user_ranking(dc_user.display_name, rank, round(fame_user.leveling, 2), ctype)

                else:
                    dpos = None

                    if topic == 'countries':
                        alpha2 = item_indicator
                        cname = format_cname(alpha2, alpha2_to_country(alpha2))
                        if is_recap:
                            cdata = recap.get(alpha2)
                            dpos = cdata[f'dpos_{ctype}']
                    else:
                        cname = item_indicator

                    ranking_str = format_country_ranking(cname, rank, count, ctype, dpos)

                str_list.append(ranking_str)

            max_pages = max(max_pages, ceil(len(str_list) / 20))
            full_str = '\n'.join(str_list[(page-1)*entries_per_page:page*entries_per_page])
            embed.add_field(name=ctype.capitalize(), value=full_str, inline=True)

        class LeaderboardView(ui.View):
            def __init__(self):
                super().__init__(timeout=None)

            @staticmethod
            async def modify_page(interaction: Interaction, page_n: int):
                await interaction.edit(**await self.generate_leaderboard(user, scope, topic, page_n, entries_per_page))

            @ui.button(label='Previous Page', style=ButtonStyle.primary, custom_id='prev',
                       disabled=page == 1)
            async def prev_btn(self2, button: Button, interaction: Interaction):
                await self2.modify_page(interaction, page - 1)

            @ui.button(label='Next Page', style=ButtonStyle.primary, custom_id='next',
                       disabled=page == max_pages)
            async def next_btn(self2, button: Button, interaction: Interaction):
                await self2.modify_page(interaction, page + 1)

        kwargs = {'embed': embed}
        if max_pages > 1 and not is_recap :
            kwargs['view'] = LeaderboardView()
        return kwargs

    @tasks.loop(seconds=5)
    async def recap_task(self):
        await self.bot.wait_until_ready()
        dt = datetime.datetime.now()
        if not dt.minute == 0:
            return

        scopes = ['hourly']
        channels = {}
        if dt.hour == 0:
            scopes.append('daily')
            channels['daily'] = 1363171417612353658
            if dt.weekday() == 0:
                scopes.append('weekly')
                channels['weekly'] = 1363171435962433768
            if dt.day == 0:
                scopes.append('seasonal')
                channels['seasonal'] = 1363171461954670632

            if self.daily_giveaway is not None:
                await self.resolve_giveaway()
            await self.create_giveaway()

            await self.create_daily_boost()

            self.reset_daily_users()

        alltime_recap = self.get_recap('alltime')
        for scope in scopes:
            name = dt.strftime('%Y-%m-%d')
            if scope == 'hourly':
                name = f'{name}_{dt.hour}'
            save_data(scope, name, alltime_recap.data)

        for scope, channel_id in channels.items():
            name = dt.strftime('%Y-%m-%d')
            if scope == 'hourly':
                name = f'{name}_{dt.hour}'
            recaps_channel = self.bot.get_channel(channel_id)
            await recaps_channel.send(
                **await self.generate_leaderboard(self.bot.user, scope, 'countries'),
                files=[discord.File(Path('exports', scope, name+'.csv'), spoiler=True, filename=name+'.csv'),
                       discord.File(Path('exports', scope, name+'.json'), spoiler=True, filename=name+'.json')]
            )
            del self.loaded_recaps[scope]

        clear_database(recaps=list(channels.keys()))
        await asyncio.sleep(100)

    def update_title_roles(self) -> None:
         main_guild = self.bot.get_guild(self.main_guild)
         if not main_guild:
             print(f'Main guild {self.main_guild} not found!')
             exit(1)
         self.title_roles = {rarity: [main_guild.get_role(role) for role in roles_list] for rarity, roles_list in self.title_role_ids.items()}

    def register_cmds(self):
        country_cmds = SlashCommandGroup('country', 'country-related commands')
        gift_cmds = SlashCommandGroup('gift', 'make gifts to other users')
        top_cmds = SlashCommandGroup('top', 'leaderboards')
        user_cmds = SlashCommandGroup('user', 'user-related commands')
        booster_cmds = SlashCommandGroup('boosters', 'booster-related commands')
        title_cmds = SlashCommandGroup('titles', 'title-related commands')

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
            user = self.get_user(ctx.author.id)
            if user.next_vote and not user.vote_ready:
                rem = user.remaining_cooldown
                embed = get_base_embed(
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
            await self.check_streak(ctx, user)
            await self.check_roles(ctx, user)
            await ctx.respond(**vote_args)

            await user.wait_cooldown()
            vote_args['view'].set_again_state(True)
            await ctx.edit(view=vote_args['view'])

            await asyncio.sleep(60)
            vote_args['view'].disable_all_items()
            await ctx.edit(view=vote_args['view'])

        @gift_cmds.command(
            name='xp',
            description='Gift xp to another user'
        )
        async def gift_xp_cmd(ctx: ApplicationContext, recipient: User, amount: Option(int)):
            if not await self.check_permissions(ctx, True):
                return

            from_user, to_user = self.get_user(ctx.user.id), self.get_user(recipient.id)
            """if (from_user.total_xp - amount - 100) <= 0:
                embed = get_base_embed(
                    ctx.author, 'Not enough XP',
                    error=True)
                await ctx.respond(embed=embed, ephemeral=True)
                return"""

            # from_user.gift_xp -= amount
            to_user.gift_xp += amount

            await ctx.respond(embed=get_base_embed(ctx.author, f'Gifted {amount}xp to {recipient.display_name}'))

        @gift_cmds.command(
            name='booster',
            description='Gift firepowers to another user'
        )
        async def gift_xp_cmd(ctx: ApplicationContext, recipient: User,
                              booster: Option(str, choices=booster_names), amount: Option(int)):
            if not await self.check_permissions(ctx, True):
                return

            from_user, to_user = self.get_user(ctx.user.id), self.get_user(recipient.id)
            booster_cls = booster_name_to_cls.get(booster, None)
            if booster_cls is None:
                raise AssertionError

            # from_user.add_booster(booster_cls, -amount)
            to_user.add_booster(booster_cls, amount)

            await ctx.respond(embed=get_base_embed(ctx.author, f'Gifted {amount}x {booster} to {recipient.display_name}'))

        @self.bot.slash_command(
            name='gen_giveaway',
            guild_ids=self.admin_guilds
        )
        @default_permissions(administrator=True)
        async def gen_giveaway_cmd(ctx: ApplicationContext):
            await self.create_giveaway()

        @self.bot.slash_command(
            name='gen_flare',
            guild_ids=self.admin_guilds
        )
        @default_permissions(administrator=True)
        async def gen_flare_cmd(ctx: ApplicationContext):
            await self.create_daily_boost()

        @self.bot.slash_command(
            name='gen_daily',
            guild_ids=self.admin_guilds
        )
        @default_permissions(administrator=True)
        async def gen_giveaway_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, True):
                return

            for user in self.users:
                user.reset_daily_quests(self.trivia, 5, list(self.titles))

        @self.bot.slash_command(
            name='reset_title_votes',
            guild_ids=self.admin_guilds
        )
        @default_permissions(administrator=True)
        async def gen_giveaway_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, True):
                return

            for user in self.users:
                user.reset_daily_votes()

        @self.bot.slash_command(
            name='resolve_giveaway',
            guild_ids=self.admin_guilds
        )
        @default_permissions(administrator=True)
        async def resolve_giveaway_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, True):
                return

            await self.resolve_giveaway()

        @self.bot.slash_command(
            name='reset',
            description='Resting data manually',
            guild_ids=self.admin_guilds
        )
        @default_permissions(administrator=True)
        async def reset_cmd(ctx: ApplicationContext, scope: Option(str, choices=['everything', 'users', 'game_data'] + self.recap_scopes)):
            if not await self.check_permissions(ctx, True):
                return

            self.loaded_recaps, self.loaded_users = {}, {}

            kwargs = {}
            if scope == 'everything':
                kwargs['users'], kwargs['recaps'], kwargs['game_data'] = True, True, True
            elif scope == 'game_data':
                kwargs['game_data'] = True
            elif scope == 'users':
                kwargs['users'] = True
            else:
                kwargs['recaps'] = [scope]
                if scope == 'daily':
                    for user in self.users:
                        user.daily_votes = 0
                        user.reset_daily_quests(self.trivia, 5, list(self.titles))
                        user.reset_daily_votes()
                        user.save()
            clear_database(**kwargs)

            await ctx.respond(embed=get_base_embed(ctx.author, f'{scope.capitalize()} cleared', description='Hope you know what you are doing!'), ephemeral=True)

        @country_cmds.command(
            name='set',
            description='Sets votes of a country to a specific amount',
            guild_ids=self.admin_guilds
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
                await ctx.respond(embed=get_base_embed(ctx.author, 'Unknown ctype!', desccription='Use "votes" or "points".'), ephemeral=True)
                return

            recap = self.get_recap('alltime')
            recap.set(alpha2, **{ctype: amount})
            recap.save()
            await ctx.respond(embed=get_base_embed(ctx.author, 'Data changed', description=f'{ctype.capitalize()} for {alpha2_to_country(alpha2)} ({alpha2}) set to {amount}!'), ephemeral=True)

        @country_cmds.command(
            name='clear',
            description='Resets votes for a specific country',
            guild_ids=self.admin_guilds
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

            embed = get_base_embed(ctx.author, title=format_cname(alpha2, c_name))
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
            name='user',
            description='List of the top users'
        )
        async def utop_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.defer()
            await ctx.respond(**await self.generate_leaderboard(ctx.user, 'alltime', 'users'))

        @top_cmds.command(
            name='country',
            description='List of the top countries'
        )
        async def ctop_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**await self.generate_leaderboard(ctx.user, 'alltime', 'countries'))

        @top_cmds.command(
            name='continent',
            description='List of the top continents'
        )
        async def contop_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**await self.generate_leaderboard(ctx.user, 'alltime', 'Continent'))

        @top_cmds.command(
            name='religion',
            description='List of the top majority religions'
        )
        async def reltop_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**await self.generate_leaderboard(ctx.user, 'alltime', 'ReligionPrimary'))

        @top_cmds.command(
            name='region',
            description='List of the top world regions'
        )
        async def regtop_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**await self.generate_leaderboard(ctx.user, 'alltime', 'RegionName'))

        @top_cmds.command(
            name='language',
            description='List of the top languages'
        )
        async def langtop_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**await self.generate_leaderboard(ctx.user, 'alltime', 'OfficialLang'))

        @self.bot.slash_command(
            name='daily',
            description='Give a daily bonus to a country of your choice!'
        )
        async def daily_cmd(ctx: ApplicationContext, country: Option(str)):
            if not await self.check_permissions(ctx, False):
                return

            fame_user = self.get_user(ctx.user.id)
            if fame_user.daily_claim:
                next_claim = fame_user.daily_claim + 60*60*20
                dt = next_claim - time()
                if dt > 0:
                    await ctx.respond(
                        embed=get_base_embed(ctx.author, 'Too early!', description=f'Wait {round(dt/60/60, 1)} hours before claiming your daily award again.', error=True),
                        ephemeral=True)
                    return

            try:
                alpha2, c_name = await self.eval_country(ctx, country)
            except TypeError:
                return

            fame_user = self.get_user(ctx.author.id)
            points_gained, xp_gained = self.do_vote(fame_user, alpha2, self.daily_votes, False, False)
            # if ctx.author.id not in self.users_role_checked:
            await self.check_roles(ctx, fame_user)

            vote_count, point_count, vote_rank, points_rank = self.get_country_stats(alpha2)
            fame_user.update_daily_claim()
            fame_user.save()

            embed = get_base_embed(
                ctx.author, title=f'{self.daily_votes} daily votes registered for {format_cname(alpha2, c_name)}! ({incr_symbol(points_gained)}{millify(points_gained)} pt.)'
            )
            embed.add_field(name='Points',
                            value=f'{millify(point_count)} (#{points_rank}{get_rank_symbol(points_rank)})', inline=True)
            embed.add_field(name='Votes',
                            value=f'{millify(vote_count)} (#{vote_rank}{get_rank_symbol(vote_rank)})', inline=True)
            embed.set_thumbnail(url=f'attachment://{alpha2}.png')

            await ctx.respond(embed=embed, file=File(Path(flags_dir, alpha2 + '.png'), filename=alpha2 + '.png'))

        @self.bot.slash_command(
            name='maintenance',
            description='Toggle maintenance mode',
            guild_ids=self.admin_guilds
        )
        @default_permissions(administrator=True)
        async def daily_cmd(ctx: ApplicationContext, value: Option(bool)):
            if not await self.check_permissions(ctx, True):
                return
            self.on_maintenance = value

            await ctx.respond(embed=get_base_embed(
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

            await ctx.respond(**await self.generate_leaderboard(ctx.user, scope, 'countries'))

        @self.bot.slash_command(
            name='chances',
            description='View the chances behind the FAME bot'
        )
        async def recap_cmd(ctx: ApplicationContext, topic: Option(str, choices=['booster', 'title'])):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**await self.generate_chances(ctx.user, topic))

        @user_cmds.command(
            name='info',
            description='Displays information on a user'
        )
        async def uinfo_cmd(ctx: ApplicationContext, user: Option(User)):
            if not await self.check_permissions(ctx, False):
                return

            fame_user = self.get_user(user.id)

            embed = get_base_embed(ctx.author, title=f'{user.name}\'s Profile')
            embed.add_field(name='Leveling',
                            value=f'{fame_user.leveling_formatted}'
                                  f'\n{ceil(fame_user.xp_until_next_level)}xp until next level\n'
                                  f'(From Season 1: {fame_user.season_1_level} Levels)',
                            inline=True)
            embed.add_field(name='Available Firedust', value=str(fame_user.total_firedust), inline=False)
            embed.add_field(name='Total votes', value=millify(fame_user.total_votes), inline=True)
            embed.add_field(name='Total points', value=millify(fame_user.total_points), inline=True)
            embed.add_field(name='Daily streak',
                            value=f'Current streak: {fame_user.daily_streak}\n'
                                  f'Reached today? {"**yes**" if fame_user.daily_votes >= self.min_daily_votes else f"**no**, do {self.min_daily_votes - fame_user.daily_votes} more votes"}',
                            inline=False)
            embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
            await ctx.respond(embed=embed)

        @user_cmds.command(
            name='data',
            description='Displays data on a user (admin only)'
        )
        async def udata_cmd(ctx: ApplicationContext, user: Option(User), key: Optional[str]):
            if not await self.check_permissions(ctx, True):
                return

            fame_user = self.get_user(user.id)
            data = fame_user.data if not key else fame_user.data[key]
            await ctx.respond(embed=get_base_embed(ctx.author, title=f'{user.name}\'s data', description=f'```{data}```'))

        @self.bot.slash_command(
            name='me',
            description='View your own profile!'
        )
        async def me_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await uinfo_cmd(ctx, ctx.user)

        @booster_cmds.command(
            name='sell',
            description='Sell your boosters to obtain firedust'
        )
        async def sell_booster_cmd(ctx: ApplicationContext, booster: Option(str, choices=booster_names), amount: Optional[int]):
            if not await self.check_permissions(ctx, False):
                return

            fame_user = self.get_user(ctx.user.id)
            booster_cls = booster_name_to_cls.get(booster, None)
            if booster_cls is None:
                raise AssertionError

            booster_count = fame_user.data['boosters'].get(booster_cls.name, 0)
            if amount is None:
                amount = booster_count
            if booster_count < amount or booster_count == 0:
                await ctx.respond(
                    embed=get_base_embed(ctx.user, f'You don\'t have enough {booster_cls.format_name()}s!'),
                    ephemeral=True
                )
                return
            if not booster_cls.firedust_cost:
                await ctx.respond(
                    embed=get_base_embed(ctx.user, f'{booster_cls.format_name()}s cannot be sold or bought!'),
                    ephemeral=True
                )
                return

            firedust_amount = amount * booster_cls.firedust_cost
            fame_user.data['boosters'][booster_cls.name] -= amount
            fame_user.scavenged_firedust += firedust_amount

            await ctx.respond(
                embed=get_base_embed(ctx.user, f'You have sold {amount}x {booster_cls.format_name()}s for {firedust_amount} :sparkles: Firedust!'),
                ephemeral=True
            )

        @booster_cmds.command(
            name='activate',
            description='Active available boosters'
        )
        async def activate_boosters_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**self.activate_booster_args(ctx))

        @booster_cmds.command(
            name='buy',
            description='Spent your firedust on boosters',
        )
        async def buy_boosters_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**self.booster_shop_args(ctx))

        @booster_cmds.command(
            name='scrap',
            description='Remove your currently active booster'
        )
        async def scrap_boosters_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            user = self.get_user(ctx.user.id)

            if not user.has_active_booster:
                await ctx.respond(
                    embed=get_base_embed(
                        ctx.author,f'You don\'t have an active booster to scrap!',error=True
                    ), ephemeral=True
                )
                return

            class ConfirmationView(ui.View):
                @ui.button(label='Scrap my booster', style=ButtonStyle.green, custom_id='confirm')
                async def again_callback(self2, button: Button, interaction: Interaction):
                    if not await self.check_permissions(interaction, False):
                        return

                    await interaction.respond(embed=get_base_embed(
                        ctx.author, f'Your active {user.active_booster.formatted_name} was scrapped.'
                    ))
                    user.scrap_booster()

            confirmation_embed = get_base_embed(
                ctx.author, 'Are you sure your active booster should be scrapped?',
                description=f'This means you will permanently loose your {user.active_booster.formatted_name} with {user.active_booster.left_duration} left duration.'
            )

            await ctx.respond(view=ConfirmationView(), embed=confirmation_embed, ephemeral=True)

        @title_cmds.command(
            name='upgrade',
            description='View and upgrade your title collection'
        )
        async def titles_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**self.title_args(ctx))

        @title_cmds.command(
            name='equip',
            description='View and manage your equipped titles'
        )
        async def titles_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**self.title_equip_args(ctx))

        @self.bot.slash_command(
            name='quests',
            description='View your current quests'
        )
        async def quests_cmd(ctx: ApplicationContext):
            if not await self.check_permissions(ctx, False):
                return

            await ctx.respond(**self.quest_args(ctx))

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
            await self.fetch_titles(ctx.channel)
            await ctx.respond('analysis finished!', ephemeral=True)

        self.bot.add_application_command(country_cmds)
        self.bot.add_application_command(gift_cmds)
        self.bot.add_application_command(top_cmds)
        self.bot.add_application_command(user_cmds)
        self.bot.add_application_command(booster_cmds)
        self.bot.add_application_command(title_cmds)

        @self.bot.listen(once=True)
        async def on_ready():
            self.update_title_roles()
            print('Bot ready')

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

    async def fetch_titles(self, channel: TextChannel):
        Path('users5755762').mkdir(exist_ok=True)
        user_data = {}

        bot_id = 1071362480347041802
        channels = [channel for channel in channel.guild.channels if channel.category_id == 1361995334246469703]
        for channel in channels:
            for message in await channel.history(limit=300).flatten():
                if not message.author.id == bot_id or not message.embeds:
                    continue

                title_embed = None
                for embed in message.embeds:
                    if 'You have found a ' in embed.title and 'title' in embed.title:
                        title_embed = embed
                        break

                if title_embed is None:
                    continue

                a, b = title_embed.title.split(' title: ')
                title_rarity = a.split(' found a ')[1].upper().replace(' ', '_')
                title_name = b.replace('!', '').strip()

                user = message.guild.get_member_named(message.embeds[0].footer.text)
                if user.id not in user_data:
                    user_data[user.id] = deepcopy(self.get_user(user.id).data)
                if any([title['name'] == title_name for title in user_data[user.id]['titles']]):
                    user_data[user.id]['titles'][[title['name'] == title_name for title in user_data[user.id]['titles']].index(True)]['amount_found'] += 1
                else:
                    user_data[user.id]['titles'].append({'rarity': title_rarity, 'name': title_name, 'amount_found': 1, 'is_equipped': False})

        for user_id, udata in user_data.items():
            Path('users5755762', f'{user_id}.json').write_text(json.dumps(udata, indent=2))

    def run(self):
        intents = Intents.default()
        intents.message_content = True
        intents.members = True
        self.bot = Bot(intents=intents)
        self.register_cmds()
        self.recap_task.start()
        self.bot.run(self.token)

        # failsafe to prevent data loss
        self.save()
