import asyncio
import logging
from typing import Dict
import sys
import os

import discord
from discord import app_commands
from discord.ext import commands

from pymax import Client, Message

# --- НАСТРОЙКИ ---
# ЗАМЕНИТЕ ЭТОТ ТОКЕН НА РЕАЛЬНЫЙ ТОКЕН ВАШЕГО БОТА
DISCORD_BOT_TOKEN = ""
MAX_PHONE = ""  # ВАШ НОМЕР ТЕЛЕФОНА
MAX_WORK_DIR = "max_cache"
MAX_SESSION_NAME = "main.db"

# --- НАСТРОЙКА ЛОГГИРОВАНИЯ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- СОЗДАНИЕ КЛИЕНТОВ ---
max_client = Client(
    phone=MAX_PHONE,
    work_dir=MAX_WORK_DIR,
    session_name=MAX_SESSION_NAME,
)

intents = discord.Intents.default()
intents.message_content = True
discord_bot = commands.Bot(command_prefix="!", intents=intents)

chat_bindings: Dict[int, int] = {}
max_ready = False
discord_ready = False

# --- ОБРАБОТЧИКИ MAX ---

@max_client.on_start()
async def on_max_start(client: Client):
    """Вызывается когда MAX клиент готов."""
    global max_ready
    max_ready = True
    logger.info("✅ MAX клиент успешно авторизован!")
    if client.me:
        logger.info(f"👤 ID: {client.me.contact.id}")
    
    # Если Discord уже готов, отправляем уведомление
    if discord_ready:
        try:
            for guild in discord_bot.guilds:
                if guild.system_channel:
                    await guild.system_channel.send("✅ MAX клиент авторизован и готов к работе!")
                    break
        except:
            pass

@max_client.on_message()
async def on_max_message(message: Message, client: Client):
    """Обработчик новых сообщений в MAX."""
    if message.chat_id is None or message.text is None or message.out:
        return
    
    discord_channel_id = chat_bindings.get(message.chat_id)
    if discord_channel_id is None:
        return
    
    channel = discord_bot.get_channel(discord_channel_id)
    if channel is None:
        chat_bindings.pop(message.chat_id, None)
        return
    
    sender_name = "Неизвестный"
    try:
        if hasattr(message, 'sender') and message.sender:
            if hasattr(message.sender, 'contact') and message.sender.contact:
                sender_name = message.sender.contact.name or message.sender.contact.nickname or str(message.sender.contact.id)
            elif hasattr(message.sender, 'user') and message.sender.user:
                sender_name = message.sender.user.first_name or message.sender.user.last_name or str(message.sender.user.id)
    except:
        pass
    
    try:
        text = message.text[:1900] + "..." if len(message.text) > 1900 else message.text
        await channel.send(f"**{sender_name}:** {text}")
        logger.info(f"📨 Переслано сообщение из чата {message.chat_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в Discord: {e}")

# --- КОМАНДЫ DISCORD ---

@discord_bot.event
async def on_ready():
    """Когда Discord бот готов."""
    global discord_ready
    discord_ready = True
    logger.info(f"✅ Discord бот {discord_bot.user} готов!")
    logger.info(f"🌐 На серверах: {len(discord_bot.guilds)}")
    
    try:
        synced = await discord_bot.tree.sync()
        logger.info(f"📋 Синхронизировано {len(synced)} команд")
    except Exception as e:
        logger.error(f"❌ Ошибка синхронизации: {e}")

@discord_bot.tree.command(name="add_chats", description="Подключить текущий канал к чату MAX")
@app_commands.describe(max_chat_id="ID чата в MAX")
async def add_chats(interaction: discord.Interaction, max_chat_id: int):
    await interaction.response.defer(ephemeral=True)
    
    if not max_ready:
        await interaction.followup.send("❌ MAX клиент не авторизован. Проверьте консоль.")
        return
    
    try:
        chat_info = await max_client.get_chat(max_chat_id)
        if chat_info is None:
            await interaction.followup.send(f"❌ Чат {max_chat_id} не найден.")
            return
    except Exception as e:
        await interaction.followup.send(f"❌ Ошибка: {e}")
        return
    
    chat_bindings[max_chat_id] = interaction.channel_id
    await interaction.followup.send(f"✅ Чат {max_chat_id} подключен к этому каналу!")
    logger.info(f"🔗 Привязка: {max_chat_id} -> {interaction.channel_id}")

@discord_bot.tree.command(name="remove_chat", description="Отключить чат от текущего канала")
@app_commands.describe(max_chat_id="ID чата в MAX")
async def remove_chat(interaction: discord.Interaction, max_chat_id: int):
    await interaction.response.defer(ephemeral=True)
    
    if chat_bindings.get(max_chat_id) == interaction.channel_id:
        chat_bindings.pop(max_chat_id, None)
        await interaction.followup.send(f"✅ Чат {max_chat_id} отключен.")
    else:
        await interaction.followup.send(f"❌ Чат {max_chat_id} не подключен к этому каналу.")

@discord_bot.tree.command(name="list_chats", description="Показать все подключенные чаты")
async def list_chats(interaction: discord.Interaction):
    if not chat_bindings:
        await interaction.response.send_message("📭 Нет подключенных чатов.", ephemeral=True)
        return
    
    message = "**📋 Подключенные чаты:**\n"
    for max_id, discord_id in chat_bindings.items():
        channel = discord_bot.get_channel(discord_id)
        channel_name = f"#{channel.name}" if channel else f"Канал {discord_id}"
        message += f"• Чат {max_id} → {channel_name}\n"
    
    await interaction.response.send_message(message, ephemeral=True)

# --- ОСНОВНАЯ ЛОГИКА ---

async def run_clients():
    """Запускает оба клиента с правильным порядком."""
    
    # ЗАПУСКАЕМ MAX КЛИЕНТ (он будет ждать SMS-код в консоли)
    logger.info("🚀 Запуск MAX клиента...")
    logger.info("📱 Если потребуется - введите SMS-код в консоли")
    
    max_task = None
    try:
        # Запускаем MAX клиент в фоне
        max_task = asyncio.create_task(max_client.start())
        
        # Даем MAX клиенту время на авторизацию
        await asyncio.sleep(2)
        
        # Проверяем статус
        if not max_ready:
            logger.info("⏳ Ожидание авторизации MAX... (введите SMS-код если требуется)")
            # Ждем пока MAX не авторизуется с таймаутом
            timeout = 120  # 2 минуты на ввод кода
            start_time = asyncio.get_event_loop().time()
            while not max_ready:
                await asyncio.sleep(1)
                if asyncio.get_event_loop().time() - start_time > timeout:
                    logger.error("❌ Таймаут авторизации MAX")
                    return
        
        logger.info("✅ MAX клиент готов, запускаем Discord бота...")
        
        # Теперь запускаем Discord бота
        await discord_bot.start(DISCORD_BOT_TOKEN)
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
    finally:
        # Останавливаем MAX клиент если он еще работает
        if max_task and not max_task.done():
            max_task.cancel()

async def main():
    """Главная функция."""
    try:
        await run_clients()
    except KeyboardInterrupt:
        logger.info("👋 Завершение работы...")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        # Закрываем соединения
        if discord_bot.is_ready():
            await discord_bot.close()
        if max_client.is_running:
            try:
                await max_client.stop()
            except:
                pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Программа остановлена")
        sys.exit(0)