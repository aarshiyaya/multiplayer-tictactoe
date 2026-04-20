"""
Lobby Router — serves lobby page, leaderboard API, and shared lobby helpers.
"""
import json
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from db import get_mysql
from state import lobby_connections, game_rooms

router = APIRouter()


# --- HTTP endpoints ---

@router.get("")
async def lobby_page(request: Request):
    if not request.session.get("uid"):
        return RedirectResponse("/")
    return FileResponse("static/lobby.html")


@router.get("/leaderboard")
async def leaderboard(request: Request):
    conn = get_mysql()
    cur = conn.cursor()
    cur.execute("SELECT uid, name, elo_rating FROM users ORDER BY elo_rating DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return JSONResponse([{"uid": r[0], "name": r[1], "elo_rating": r[2]} for r in rows])


# --- Shared helpers used by main.py ---

async def broadcast_user_list():
    """Send the current online player list to all lobby connections."""
    conn = get_mysql()
    cur = conn.cursor()
    cur.execute("SELECT uid, name FROM users WHERE is_online = TRUE")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    msg = json.dumps({"type": "user_list", "users": [{"uid": r[0], "name": r[1]} for r in rows]})

    dead = []
    for uid, ws in list(lobby_connections.items()):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(uid)
    for uid in dead:
        lobby_connections.pop(uid, None)


async def handle_forfeit_from_lobby(uid):
    """If a player who disconnected from lobby is in an active game, forfeit them."""
    from routers.game import handle_forfeit
    for room_id, room in list(game_rooms.items()):
        if uid in room["players"] and room["active"]:
            await handle_forfeit(room_id, uid)
            break