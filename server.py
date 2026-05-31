import asyncio
import websockets
import json
import uuid

# ======================================
# server.py - سيرفر مع Matchmaking
# يربط لاعبين بناءً على السكور
# ======================================

# قاموس اللاعبين المنتظرين
# المفتاح = score_range, القيمة = قائمة لاعبين
waiting_players = {}

# قاموس الغرف النشطة
active_rooms = {}

# ======================================
async def handle(websocket):
    player_id = str(uuid.uuid4())[:8]
    player_score = 0
    room_id = None

    print(f"✅ لاعب دخل - ID: {player_id}")

    try:
        async for message in websocket:
            data = json.loads(message)

            # ======================================
            # طلب البحث عن لاعب
            if data["type"] == "find_match":
                player_score = data.get("score", 0)

                # نحدد نطاق السكور
                # كل 100 نقطة = نطاق واحد
                # يمكنك تغيير هذا لاحقاً
                score_range = player_score // 100

                # نضيف اللاعب للانتظار
                if score_range not in waiting_players:
                    waiting_players[score_range] = []

                waiting_players[score_range].append({
                    "id": player_id,
                    "socket": websocket,
                    "score": player_score
                })

                # نبحث عن لاعب مناسب
                room_id = await find_match(
                    player_id,
                    websocket,
                    score_range
                )

            # ======================================
            # تحديث الموقع
            elif data["type"] == "position_update":
                if room_id and room_id in active_rooms:
                    room = active_rooms[room_id]
                    # نرسل للاعب الآخر فقط
                    for pid, pws in room.items():
                        if pid != player_id:
                            try:
                                await pws.send(json.dumps({
                                    "type": "position_update",
                                    "x": data["x"],
                                    "y": data["y"],
                                    "z": data["z"],
                                    "ry": data["ry"]
                                }))
                            except:
                                pass

            # ======================================
            # إلغاء البحث
            elif data["type"] == "cancel_match":
                _remove_from_waiting(player_id)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # نحذف اللاعب من كل مكان
        _remove_from_waiting(player_id)
        if room_id and room_id in active_rooms:
            room = active_rooms[room_id]
            # نخبر اللاعب الآخر
            for pid, pws in room.items():
                if pid != player_id:
                    try:
                        await pws.send(json.dumps({
                            "type": "player_left",
                            "player_id": player_id
                        }))
                    except:
                        pass
            del active_rooms[room_id]
        print(f"❌ لاعب خرج - ID: {player_id}")

# ======================================
async def find_match(player_id, websocket, score_range):
    players = waiting_players.get(score_range, [])

    # نبحث عن لاعب آخر في نفس النطاق
    other = None
    for p in players:
        if p["id"] != player_id:
            other = p
            break

    if other:
        # وجدنا لاعب! نعمل غرفة
        room_id = str(uuid.uuid4())[:8]
        active_rooms[room_id] = {
            player_id: websocket,
            other["id"]: other["socket"]
        }

        # نحذفهم من الانتظار
        waiting_players[score_range] = [
            p for p in players
            if p["id"] not in [player_id, other["id"]]
        ]

        # نخبر كلا اللاعبين
        await websocket.send(json.dumps({
            "type": "match_found",
            "player_id": player_id,
            "room_id": room_id
        }))

        await other["socket"].send(json.dumps({
            "type": "match_found",
            "player_id": other["id"],
            "room_id": room_id
        }))

        # نخبر كلاً منهم بدخول الآخر
        await websocket.send(json.dumps({
            "type": "player_joined",
            "player_id": other["id"]
        }))

        await other["socket"].send(json.dumps({
            "type": "player_joined",
            "player_id": player_id
        }))

        print(f"✅ غرفة جديدة: {room_id}")
        return room_id
    else:
        # لم نجد لاعب، ننتظر
        total_waiting = sum(
            len(v) for v in waiting_players.values()
        )
        await websocket.send(json.dumps({
            "type": "waiting",
            "count": total_waiting
        }))
        return None

# ======================================
def _remove_from_waiting(player_id):
    for score_range in waiting_players:
        waiting_players[score_range] = [
            p for p in waiting_players[score_range]
            if p["id"] != player_id
        ]

# ======================================
async def main():
    import os
    port = int(os.environ.get("PORT", 8765))
    print(f"🚀 السيرفر يعمل على البورت {port}")
    async with websockets.serve(handle, "0.0.0.0", port):
        await asyncio.Future()

asyncio.run(main())