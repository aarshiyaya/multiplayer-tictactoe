from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
import json, time

from db import get_mysql, get_mongo
from routers import auth, lobby, game
from state import lobby_connections, pending_challenges, game_rooms
from routers.lobby import broadcast_user_list, handle_forfeit_from_lobby
from utils.facial_recognition_module import build_encodings_cache

app = FastAPI(title="ByteMe Arena")

app.add_middleware(SessionMiddleware, secret_key="BYTEME_SECRET_KEY_CHANGE_IN_PROD", same_site="lax")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router, prefix="/auth")
app.include_router(lobby.router, prefix="/lobby")
app.include_router(game.router, prefix="/game")


@app.on_event("startup")
def load_encodings():
    """Pre-build face encoding cache from MongoDB on server start."""
    mongo = get_mongo()
    db_images = {doc["uid"]: doc["image"] for doc in mongo.find({}, {"uid": 1, "image": 1})}
    app.state.encodings_cache = build_encodings_cache(db_images)
    print("Face encoding cache ready")


@app.on_event("startup")
async def create_tables():
    """Create the matches table if it doesn't exist, reset online status."""
    conn = get_mysql()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INT AUTO_INCREMENT PRIMARY KEY,
            player1_uid VARCHAR(255),
            player2_uid VARCHAR(255),
            winner_uid VARCHAR(255),
            result ENUM('win', 'draw', 'forfeit'),
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("UPDATE users SET is_online = FALSE")
    conn.commit()
    cur.close()
    conn.close()


@app.get("/")
async def root():
    return FileResponse("static/login.html")


@app.get("/leaderboard-page")
async def leaderboard_page():
    return FileResponse("static/leaderboard.html")


@app.websocket("/ws/lobby")
async def lobby_ws(websocket: WebSocket):
    uid = websocket.query_params.get("uid")
    if not uid:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    lobby_connections[uid] = websocket

    # Mark online
    conn = get_mysql()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_online = TRUE WHERE uid = %s", (uid,))
    conn.commit()
    cur.close()
    conn.close()

    await broadcast_user_list()

    try:
        while True:
            msg = json.loads(await websocket.receive_text())

            if msg["type"] == "challenge":
                target_uid = msg.get("target_uid")
                if not target_uid or target_uid not in lobby_connections:
                    await websocket.send_text(json.dumps({"type": "error", "message": "Target user not online"}))
                    continue

                pending_challenges[uid] = {"target_uid": target_uid}

                # Get challenger name
                conn = get_mysql()
                cur = conn.cursor()
                cur.execute("SELECT name FROM users WHERE uid = %s", (uid,))
                row = cur.fetchone()
                cur.close()
                conn.close()

                target_ws = lobby_connections.get(target_uid)
                if target_ws:
                    await target_ws.send_text(json.dumps({
                        "type": "challenge_incoming",
                        "challenger_uid": uid,
                        "challenger_name": row[0] if row else uid
                    }))

            elif msg["type"] == "challenge_response":
                challenger_uid = msg.get("challenger_uid")
                accepted = msg.get("accepted", False)

                if challenger_uid not in pending_challenges:
                    continue

                if not accepted:
                    cws = lobby_connections.get(challenger_uid)
                    if cws:
                        await cws.send_text(json.dumps({"type": "challenge_declined", "target_uid": uid}))
                    pending_challenges.pop(challenger_uid, None)
                    continue

                # Create game room
                target_uid = uid
                room_id = f"{challenger_uid}_{target_uid}_{int(time.time())}"

                game_rooms[room_id] = {
                    "players": [challenger_uid, target_uid],
                    "connections": {},
                    "board": [None] * 9,
                    "turn": challenger_uid,
                    "active": False,
                    "markers": {challenger_uid: "X", target_uid: "O"}
                }

                # Getting names for the players
                conn = get_mysql()
                cur = conn.cursor()
                cur.execute("SELECT uid, name FROM users WHERE uid IN (%s, %s)", (challenger_uid, target_uid))
                name_map = {r[0]: r[1] for r in cur.fetchall()}
                cur.close()
                conn.close()

                #redirecting to game
                cws = lobby_connections.get(challenger_uid)
                if cws:
                    await cws.send_text(json.dumps({
                        "type": "match_start",
                        "room_id": room_id,
                        "opponent_uid": target_uid,
                        "opponent_name": name_map.get(target_uid, target_uid)
                    }))

                await websocket.send_text(json.dumps({
                    "type": "match_start",
                    "room_id": room_id,
                    "opponent_uid": challenger_uid,
                    "opponent_name": name_map.get(challenger_uid, challenger_uid)
                }))

                pending_challenges.pop(challenger_uid, None)

    except WebSocketDisconnect:
        lobby_connections.pop(uid, None)

        conn = get_mysql()
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_online = FALSE WHERE uid = %s", (uid,))
        conn.commit()
        cur.close()
        conn.close()

        await handle_forfeit_from_lobby(uid)
        await broadcast_user_list()