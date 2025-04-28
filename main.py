from typing import NoReturn

from dotenv import load_dotenv

from bot import FameBot


def main() -> NoReturn:
    load_dotenv()
    bot = FameBot()
    bot.run()

if __name__ == '__main__':
    main()
