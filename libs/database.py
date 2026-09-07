import asyncio
from tortoise import Tortoise, run_async
from tortoise import fields
from tortoise.models import Model

class Database:
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)
    discord_id = fields.BigIntField(unique=True)
    telegram_id = fields.BigIntField(unique=True)
    max_id = fields.BigIntField(unique=True)


async def main():
    await Tortoise.init(
    db_url="postgres://postgres:secret@localhost:5432/bridge",
    modules={"models": ["models"]},
    )
    await Tortoise.generate_schemas()
    print("Up and running!")
    await Tortoise.close_connections()

asyncio.run(main())