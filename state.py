"""
Shared in-memory server state.
All game and lobby state lives here so routers can import it cleanly.
"""

from fastapi import WebSocket

# Maps uid -> WebSocket connection (for lobby)
lobby_connections: dict[str, WebSocket] = {}

# Maps room_id -> {
#   "players": [uid1, uid2],
#   "connections": {uid: WebSocket},
#   "board": [None]*9,
#   "turn": uid,
#   "active": bool,
#   "markers": {uid: "X"/"O"}
# }
game_rooms: dict[str, dict] = {}

# Pending challenges: challenger_uid -> { "target_uid": ..., "challenger_ws": WebSocket }
pending_challenges: dict[str, dict] = {}