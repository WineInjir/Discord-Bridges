import asyncio
from tortoise import Tortoise, run_async
from tortoise import fields
from tortoise.models import Model
from libs.models import *

async def init():
    await Tortoise.init(
        db_url='postgres://postgres:secret@localhost:11001/bridge',
        modules={'models': ['libs.models']}
    )
    await Tortoise.generate_schemas()

async def main():
    await init()
    #user = await libs.models.User.create(discord_id="671619583676907541")
    users = await User.all()
    for user in users:
        print(user.id, user.discord_id)
    await Tortoise.close_connections()