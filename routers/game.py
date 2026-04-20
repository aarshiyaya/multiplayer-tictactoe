"""
Game Router — serves game page + WebSocket game logic for Tic-Tac-Toe.
"""
import json
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse
from db import get_mysql
from state import game_rooms
from utils.elo import update_elo_both

router = APIRouter()

# All 8 winning lines for a 3x3 board
WIN_LINES = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8],  # rows
    [0, 3, 6], [1, 4, 7], [2, 5, 8],  # cols
    [0, 4, 8], [2, 4, 6],             # diagonals
]


def check_winner(board):
    """Return the marker ('X' or 'O') that won, or None."""
    for a, b, c in WIN_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None


def check_draw(board):
    return all(cell is not None for cell in board)


async def broadcast(room, msg_dict):
    """Send a JSON message to all connected players in a room."""
    text = json.dumps(msg_dict)
    for ws in list(room["connections"].values()):
        try:
            await ws.send_text(text)
        except Exception:
            pass


async def finalize_match(room_id, winner_uid, status):
    """
    End a game: update Elo ratings, record match in DB, notify players.
    winner_uid is None for a draw.
    """
    room = game_rooms.get(room_id)
    if not room:
        return

    room["active"] = False
    uid1, uid2 = room["players"]

    # Get current Elo ratings
    conn = get_mysql()
    cur = conn.cursor()
    cur.execute("SELECT uid, elo_rating FROM users WHERE uid IN (%s, %s)", (uid1, uid2))
    elo_map = {row[0]: row[1] for row in cur.fetchall()}
    r1, r2 = elo_map.get(uid1, 1200), elo_map.get(uid2, 1200)

    # Compute new ratings
    if winner_uid is None:
        outcome = "draw"
    elif winner_uid == uid1:
        outcome = "player1_win"
    else:
        outcome = "player2_win"

    new_r1, new_r2 = update_elo_both(r1, r2, outcome)

    # Save to DB
    cur.execute("UPDATE users SET elo_rating = %s WHERE uid = %s", (new_r1, uid1))
    cur.execute("UPDATE users SET elo_rating = %s WHERE uid = %s", (new_r2, uid2))
    cur.execute(
        "INSERT INTO matches (player1_uid, player2_uid, winner_uid, result) VALUES (%s, %s, %s, %s)",
        (uid1, uid2, winner_uid, "draw" if winner_uid is None else "win")
    )
    conn.commit()
    cur.close()
    conn.close()

    # Notify both players
    await broadcast(room, {
        "type": "game_state",
        "board": room["board"],
        "turn": room["turn"],
        "status": status,
        "winner": winner_uid,
    })


async def handle_forfeit(room_id, disconnected_uid):
    """Handle forfeit when a player disconnects mid-game."""
    room = game_rooms.get(room_id)
    if not room or not room["active"]:
        return

    room["active"] = False
    uid1, uid2 = room["players"]
    winner_uid = uid2 if disconnected_uid == uid1 else uid1

    # Update Elo
    conn = get_mysql()
    cur = conn.cursor()
    cur.execute("SELECT uid, elo_rating FROM users WHERE uid IN (%s, %s)", (uid1, uid2))
    elo_map = {row[0]: row[1] for row in cur.fetchall()}
    r1, r2 = elo_map.get(uid1, 1200), elo_map.get(uid2, 1200)

    outcome = "player2_win" if disconnected_uid == uid1 else "player1_win"
    new_r1, new_r2 = update_elo_both(r1, r2, outcome)

    cur.execute("UPDATE users SET elo_rating = %s WHERE uid = %s", (new_r1, uid1))
    cur.execute("UPDATE users SET elo_rating = %s WHERE uid = %s", (new_r2, uid2))
    cur.execute("UPDATE users SET is_online = FALSE WHERE uid = %s", (disconnected_uid,))
    cur.execute(
        "INSERT INTO matches (player1_uid, player2_uid, winner_uid, result) VALUES (%s, %s, %s, 'forfeit')",
        (uid1, uid2, winner_uid)
    )
    conn.commit()
    cur.close()
    conn.close()

    # Notify remaining player
    remaining_ws = room["connections"].get(winner_uid)
    if remaining_ws:
        try:
            await remaining_ws.send_text(json.dumps({
                "type": "game_over",
                "status": "win",
                "reason": "opponent_disconnected",
                "winner": winner_uid
            }))
        except Exception:
            pass

    game_rooms.pop(room_id, None)


# --- HTTP endpoint ---

@router.get("")
async def game_page(request: Request):
    if not request.session.get("uid"):
        return RedirectResponse("/")
    return FileResponse("static/game.html")


# --- WebSocket game logic ---

@router.websocket("/ws/{room_id}")
async def game_ws(websocket: WebSocket, room_id: str):
    uid = websocket.query_params.get("uid")
    room = game_rooms.get(room_id)

    if not room or not uid or uid not in room["players"]:
        await websocket.close(code=4003)
        return

    await websocket.accept()
    room["connections"][uid] = websocket

    # When both players connected, start the game
    if len(room["connections"]) == 2:
        room["active"] = True
        for player_uid, ws in room["connections"].items():
            try:
                await ws.send_text(json.dumps({
                    "type": "game_state",
                    "board": room["board"],
                    "turn": room["turn"],
                    "your_uid": player_uid,
                    "status": "ongoing",
                    "markers": room["markers"],
                    "players": room["players"],
                }))
            except Exception:
                pass
    else:
        await websocket.send_text(json.dumps({"type": "waiting", "message": "Waiting for opponent..."}))

    try:
        while True:
            msg = json.loads(await websocket.receive_text())

            if msg.get("type") != "move":
                continue

            # Validate move
            if not room["active"]:
                await websocket.send_text(json.dumps({"type": "error", "message": "Game is not active"}))
                continue
            if room["turn"] != uid:
                await websocket.send_text(json.dumps({"type": "error", "message": "Not your turn"}))
                continue

            cell = msg.get("cell")
            if cell is None or not (0 <= cell <= 8) or room["board"][cell] is not None:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid move"}))
                continue

            # Apply move
            room["board"][cell] = room["markers"][uid]

            # Switch turn
            uid1, uid2 = room["players"]
            room["turn"] = uid2 if uid == uid1 else uid1

            # Check win/draw
            if check_winner(room["board"]):
                await finalize_match(room_id, uid, "win")
                game_rooms.pop(room_id, None)
                break
            elif check_draw(room["board"]):
                await finalize_match(room_id, None, "draw")
                game_rooms.pop(room_id, None)
                break
            else:
                await broadcast(room, {
                    "type": "game_state",
                    "board": room["board"],
                    "turn": room["turn"],
                    "status": "ongoing",
                    "markers": room["markers"],
                    "players": room["players"],
                })

    except WebSocketDisconnect:
        room["connections"].pop(uid, None)

        conn = get_mysql()
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_online = FALSE WHERE uid = %s", (uid,))
        conn.commit()
        cur.close()
        conn.close()

        if game_rooms.get(room_id, {}).get("active"):
            await handle_forfeit(room_id, uid)