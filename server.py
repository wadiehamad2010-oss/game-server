import asyncio
import websockets
import json
import uuid

waiting_players = {}
active_rooms = {}
# ربط كل لاعب بغرفته (يحل مشكلة room_id للاعب الأول)
player_rooms = {}
# تتبع من أرسل game_ready داخل كل غرفة
room_ready = {}

# ======================================
async def handle(websocket):
	player_id = str(uuid.uuid4())[:8]
	player_score = 0

	print(f"✅ لاعب دخل - ID: {player_id}")

	try:
		async for message in websocket:
			data = json.loads(message)

			if data["type"] == "find_match":
				player_score = data.get("score", 0)
				score_range = player_score // 100

				if score_range not in waiting_players:
					waiting_players[score_range] = []

				waiting_players[score_range].append({
					"id": player_id,
					"socket": websocket,
					"score": player_score
				})

				await find_match(player_id, websocket, score_range)

			elif data["type"] == "game_ready":
				room_id = player_rooms.get(player_id)
				if not room_id or room_id not in active_rooms:
					continue

				ready = room_ready.setdefault(room_id, set())
				ready.add(player_id)
				print(f"📥 game_ready من {player_id} — الغرفة {room_id}: {len(ready)}/2")

				if len(ready) >= len(active_rooms[room_id]):
					await _send_player_joined(room_id)

			elif data["type"] == "position_update":
				# الاعتماد على player_rooms فقط (وليس متغير room_id المحلي في handle)
				room_id = player_rooms.get(player_id)
				# مزامنة: اللاعب المنتظر أولاً قد يكون داخل الغرفة دون تسجيل في player_rooms
				if not room_id:
					for rid, room in active_rooms.items():
						if player_id in room:
							room_id = rid
							player_rooms[player_id] = rid
							break
				if not room_id:
					continue
				room = active_rooms.get(room_id)
				if not room or player_id not in room:
					continue
				payload = json.dumps({
					"type": "position_update",
					"x": data["x"],
					"y": data["y"],
					"z": data["z"],
					"ry": data["ry"]
				})
				for pid, pws in room.items():
					if pid == player_id:
						continue
					try:
						await pws.send(payload)
					except Exception:
						pass

			elif data["type"] == "cancel_match":
				_remove_from_waiting(player_id)

	except websockets.exceptions.ConnectionClosed:
		pass
	finally:
		_remove_from_waiting(player_id)
		room_id = player_rooms.get(player_id)
		if room_id and room_id in active_rooms:
			room = active_rooms[room_id]
			for pid, pws in room.items():
				if pid != player_id:
					try:
						await pws.send(json.dumps({
							"type": "player_left",
							"player_id": player_id
						}))
					except:
						pass
			_cleanup_room(room_id)
		print(f"❌ لاعب خرج - ID: {player_id}")

# ======================================
async def _send_player_joined(room_id):
	room = active_rooms.get(room_id)
	if not room or len(room) < 2:
		return

	player_ids = list(room.keys())
	for pid in player_ids:
		other_pid = player_ids[1] if player_ids[0] == pid else player_ids[0]
		try:
			await room[pid].send(json.dumps({
				"type": "player_joined",
				"player_id": other_pid
			}))
		except:
			pass

	print(f"✅ أرسلنا player_joined للغرفة {room_id}")

# ======================================
def _cleanup_room(room_id):
	if room_id in active_rooms:
		for pid in active_rooms[room_id]:
			player_rooms.pop(pid, None)
		del active_rooms[room_id]
	room_ready.pop(room_id, None)

# ======================================
async def find_match(player_id, websocket, score_range):
	players = waiting_players.get(score_range, [])

	other = None
	for p in players:
		if p["id"] != player_id:
			other = p
			break

	if other:
		room_id = str(uuid.uuid4())[:8]
		active_rooms[room_id] = {
			player_id: websocket,
			other["id"]: other["socket"]
		}

		# ربط كلا اللاعبين بالغرفة (إصلاح room_id للاعب الأول)
		for pid in active_rooms[room_id]:
			player_rooms[pid] = room_id
		room_ready[room_id] = set()

		waiting_players[score_range] = [
			p for p in players
			if p["id"] not in [player_id, other["id"]]
		]

		await websocket.send(json.dumps({
			"type": "match_found",
			"player_id": player_id,
			"player_index": 0,
			"room_id": room_id
		}))

		await other["socket"].send(json.dumps({
			"type": "match_found",
			"player_id": other["id"],
			"player_index": 1,
			"room_id": room_id
		}))

		print(f"✅ غرفة جديدة: {room_id} — بانتظار game_ready من اللاعبين")
	else:
		total = sum(len(v) for v in waiting_players.values())
		await websocket.send(json.dumps({
			"type": "waiting",
			"count": total
		}))

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
