import asyncio
from libs import discord_bot as bot
from libs import telegram_user as telegram
from libs import database as db

async def main():
    await db.main()

if __name__ == "__main__":
    asyncio.run(bot.main())