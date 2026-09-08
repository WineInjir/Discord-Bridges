#!/usr/bin/env python3
"""
Simple example: Login via phone (SMS) and show groups.
Phone is entered interactively in terminal.
"""
import asyncio
from maxpy import MaxClient, TransportType


async def main():
    phone = input("Введите номер телефона (+7...): ").strip()
    if not phone.startswith('+'):
        phone = '+7' + phone.lstrip('78')
    
    client = MaxClient(
        transport=TransportType.TCP,
        phone=phone,
        session_name="show_groups",
        persist_session=True,
    )
    
    try:
        print("Подключение...")
        await client.start()
        print(f"✅ Вошли как: {client.user.get_full_name()}")
        
        chats = await client.chats.fetch_chats()
        groups = [c for c in chats if c.is_group]
        
        print(f"\n📋 Групп: {len(groups)}")
        for i, g in enumerate(groups, 1):
            print(f"  {i}. {g.title or 'Без названия'} ({g.id}) — {g.members_count} участников")
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())