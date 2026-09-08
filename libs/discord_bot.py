import asyncio
import threading
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.message_content = True

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")

async def main():
    async with bot:
        await bot.start(TOKEN)
    print("executed")

