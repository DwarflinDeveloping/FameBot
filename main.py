import json
import os
from dotenv import load_dotenv
from pathlib import Path
import pycountry
import discord
from discord import default_permissions

load_dotenv()

data_path = Path('data.json')
flags_dir = Path('flags')

COUNTRIES_NAME_LIST = [country.name for country in pycountry.countries]
ALPHA_TO_NAME = {country.alpha_2: country.name for country in pycountry.countries}
DATA_PRESET = {'counts': {country.alpha_2: 0 for country in pycountry.countries}}

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

        self._data = None
        _ = self.data  # initializing data
        # self.load_flags()  # initializing flags

    @property
    def data(self):
        if self._data is None:
            self.data = load_data()  # loading data for the first time
        return self._data

    @data.setter
    def data(self, value):
        self._data = value
        self.save_data()

    """def load_flags(self):
        self.country_imgs = {}
        for flag_file in os.listdir(flags_dir):
            country = flag_file.split('.')[0]
            file_path = Path(flags_dir, flag_file)

            self.country_imgs[country] = discord.File(file_path, filename=country + '.png')"""

    def save_data(self):
        data_path.write_text(json.dumps(self.data, indent=2))

    def run(self):
        self.bot = discord.Bot(intents=discord.Intents.default(), command_prefix='&')

        @self.bot.slash_command(
            name='cvote',
            description='Cast a vote for a country of your choice!'
        )
        async def vote_cmd(ctx, country: discord.Option(str)):
            country = country.upper()
            if country not in self.data['counts']:
                await ctx.respond(f'Unknown country code {country}! Please use ISO 3166-1 Alpha-2.')
                return

            country_name = ALPHA_TO_NAME[country]
            self.data['counts'][country] += 1
            self.save_data()

            embed = discord.Embed(
                title='Vote successful!',
                description=f'You have cast vote #{self.data['counts'][country]} for {country_name}.',
                color=discord.Colour.blurple(),
            )
            embed.set_footer(text="FameBot", icon_url="https://cdn3.emoji.gg/emojis/9435-blurple-bot.png")
            print(country)
            embed.set_thumbnail(url=f'attachment://{country}.png')
            await ctx.respond(
                embed=embed,
                file=discord.File(Path(flags_dir, country+'.png'), filename=country+'.png')
            )

        @self.bot.slash_command(
            name='dbclear',
            description='Clears the entire database'
        )
        @default_permissions(administrator=True)
        async def dbclear_cmd(ctx):
            self.data = DATA_PRESET.copy()
            await ctx.respond('Database cleared! Hope you know what you are doing.')

        @self.bot.slash_command(
            name='cset',
            description='Sets votes of a country to a specific amount'
        )
        @default_permissions(administrator=True)
        async def cset_cmd(ctx, country: discord.Option(str), amount: discord.Option(int)):
            country = country.upper()
            if country not in self.data['counts']:
                await ctx.respond(f'Unknown country code {country}! Please use ISO 3166-1 Alpha-2.')
                return

            self.data['counts'][country] = amount
            self.save_data()
            await ctx.respond(f'Votes for {ALPHA_TO_NAME[country]} ({country}) set to {amount}!')

        @self.bot.slash_command(
            name='cclear',
            description='Resets votes for a specific country'
        )
        @default_permissions(administrator=True)
        async def cclear_cmd(ctx, country: discord.Option(str)):
            await cset_cmd(ctx, country, 0)

        self.bot.run(os.getenv('TOKEN'))

if __name__ == '__main__':
    bot = FameBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.save_data()  # failsafe for data loss
