import asyncio
import websockets

players = set()

async def handle(websocket):
    players.add(websocket)
    print(f"لاعب دخل - المتصلون: {len(players)}")
    try:
        async for message in websocket:
            for p in list(players):
                if p != websocket:
                    await p.send(message)
    finally:
        players.remove(websocket)
        print(f"لاعب خرج - المتصلون: {len(players)}")

async def main():
    port = int(__import__('os').environ.get('PORT', 8765))
    print(f"السيرفر يعمل على البورت {port}")
    async with websockets.serve(handle, "0.0.0.0", port):
        await asyncio.Future()

asyncio.run(main())