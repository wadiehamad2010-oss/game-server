import asyncio
import websockets
import json
import uuid

waiting_players = {}
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

				room_id = await find_match(
					player_id, websocket, score_range
				)

			elif data["type"] == "position_update":
				if room_id and room_id in active_rooms:
					room = active_rooms[room_id]
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

			elif data["type"] == "cancel_match":
				_remove_from_waiting(player_id)

	except websockets.exceptions.ConnectionClosed:
		pass
	finally:
		_remove_from_waiting(player_id)
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
			del active_rooms[room_id]
		print(f"❌ لاعب خرج - ID: {player_id}")

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

		waiting_players[score_range] = [
			p for p in players
			if p["id"] not in [player_id, other["id"]]
		]

		# نرسل match_found لكلا اللاعبين
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

		# ننتظر ثانية عشان اللاعبين يدخلون Game أولاً
		await asyncio.sleep(1)

		# نرسل player_joined لكلا اللاعبين
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
		total = sum(len(v) for v in waiting_players.values())
		await websocket.send(json.dumps({
			"type": "waiting",
			"count": total
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