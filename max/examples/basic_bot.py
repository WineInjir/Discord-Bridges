#!/usr/bin/env python3
"""
Basic MaxPy bot example.

This example demonstrates how to create a simple bot using MaxPy with TCP transport.
"""

import asyncio
import os
from maxpy import MaxClient, TransportType, CommandFilter


async def main():
    # Create client with TCP transport (requires phone number for SMS auth)
    # For testing, you can use environment variables:
    # MAXPY_AUTH__PHONE="+79001234567"
    
    client = MaxClient(
        transport=TransportType.TCP,
        phone=os.getenv("MAXPY_PHONE", "+79001234567"),
        session_name="example_bot",
        persist_session=True,
    )
    
    # Register command handlers
    @client.on_message(CommandFilter("start"))
    async def cmd_start(message, client):
        await message.reply(
            "👋 Hello! I'm a MaxPy bot.\n"
            "Available commands:\n"
            "/start - Show this message\n"
            "/echo <text> - Echo back text\n"
            "/photo - Send a random photo"
        )
    
    @client.on_message(CommandFilter("echo"))
    async def cmd_echo(message, client):
        text = message.text.replace("/echo ", "", 1).strip()
        if text:
            await message.reply(f"Echo: {text}")
        else:
            await message.reply("Nothing to echo. Usage: /echo <text>")
    
    @client.on_message(CommandFilter("photo"))
    async def cmd_photo(message, client):
        from maxpy import Photo
        # Send a random photo from picsum.photos
        photo = Photo(url="https://picsum.photos/400/300")
        await client.messages.send_photo(message.chat_id, photo, caption="Random photo!")
    
    # Startup handler
    @client.on_start()
    async def on_startup(client):
        print("✅ Bot started successfully!")
        print(f"Logged in as: {client.user.get_full_name() if client.user else 'Unknown'}")
    
    # Error handler
    @client.on_error(scope="global")
    async def on_error(error, context):
        print(f"❌ Error in {context.handler}: {error}")
    
    # Start the client
    await client.start()
    
    print("Bot is running. Press Ctrl+C to stop.")
    
    try:
        # Keep running until interrupted
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\nStopping bot...")
    finally:
        await client.stop()
        print("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())