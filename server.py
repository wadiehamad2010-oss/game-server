# ======================================
# server.py - سيرفر اللعبة
# يربط اللاعبين ببعض عبر الإنترنت
# ======================================

import asyncio
import websockets
import json

# قاموس يحفظ جميع اللاعبين المتصلين
players = {}

# ======================================
# دالة تشتغل لما لاعب يتصل
# ======================================
async def handle_player(websocket):
    player_id = id(websocket)
    players[player_id] = websocket
    print(f"✅ لاعب دخل - ID: {player_id} | المتصلون: {len(players)}")

    try:
        async for message in websocket:
            # نرسل الرسالة لجميع اللاعبين الآخرين
            for pid, ws in list(players.items()):
                if pid != player_id:
                    try:
                        await ws.send(message)
                    except:
                        pass

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        del players[player_id]
        print(f"❌ لاعب خرج - ID: {player_id} | المتصلون: {len(players)}")

# ======================================
# تشغيل السيرفر
# ======================================
async def main():
    print("🚀 السيرفر يعمل على البورت 8765")
    async with websockets.serve(handle_player, "0.0.0.0", 8765):
        await asyncio.Future()

asyncio.run(main())