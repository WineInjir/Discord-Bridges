from tortoise import fields
from tortoise.models import Model

class User(Model):
    id = fields.IntField(primary_key=True)
    discord_id = fields.BigIntField(unique=True)
    telegram_id = fields.BigIntField(unique=True, null=True)
    max_id = fields.BigIntField(unique=True, null=True)

    def __str__(self):
        return self.id