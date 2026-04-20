from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from db import get_mysql
from utils.facial_recognition_module import find_closest_match

router = APIRouter()


@router.post("/login")
async def login(request: Request):
    try:
        body = await request.json()
        image_b64 = body.get("image")

        if not image_b64:
            return {"success": False, "error": "No image provided"}

        #using the prebuilt cache
        encodings_cache = request.app.state.encodings_cache
        matched_uid = find_closest_match(image_b64, encodings_cache)

        if not matched_uid:
            return {"success": False, "error": "No match found"}

        # Look up user
        conn = get_mysql()
        cur = conn.cursor()
        cur.execute("SELECT uid, name FROM users WHERE uid = %s", (matched_uid,))
        row = cur.fetchone()

        if not row:
            cur.close()
            conn.close()
            return {"success": False, "error": "User not found"}

        uid, name = row
        cur.execute("UPDATE users SET is_online = TRUE WHERE uid = %s", (uid,))
        conn.commit()
        cur.close()
        conn.close()

        # Save
        request.session["uid"] = uid
        request.session["name"] = name

        return {"success": True, "uid": uid, "name": name}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/logout")
async def logout(request: Request):
    uid = request.session.get("uid")
    if uid:
        conn = get_mysql()
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_online = FALSE WHERE uid = %s", (uid,))
        conn.commit()
        cur.close()
        conn.close()

    request.session.clear()
    return {"success": True}


@router.get("/me")
async def me(request: Request):
    uid = request.session.get("uid")
    name = request.session.get("name")
    if not uid:
        return {"error": "Not authenticated"}
    return {"uid": uid, "name": name}
