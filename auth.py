from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import mysql.connector
from pymongo import MongoClient
import base64
import os
from db import get_mongo

# ── import the provided black-box module (must be in the same directory) ──────
from facial_recognition_module import find_closest_match

app = FastAPI()

# ── middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "change-this-in-production"),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB connection helpers (swap in your Phase 1 credentials) ───────────────────
def get_mysql():
    return mysql.connector.connect(
        host="localhost",
        port=3307,
        user="root",
        password="rootpassword",
        database="byteme_test",
    )
# ── request schema ─────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    image: str   # base64-encoded webcam frame sent from login.html


# ── POST /auth/login ───────────────────────────────────────────────────────────
@app.post("/auth/login")
async def login(payload: LoginRequest, request: Request):
    """
    1. Pull all profile images from MongoDB  →  {uid: image_data}
    2. Call find_closest_match with the webcam frame
    3. On a match: verify uid in MySQL, set is_online=TRUE, create session
    4. Return success/failure JSON
    """

    # ── step 1: load stored profile images from MongoDB ────────────────────────
    try:
        mongo_collection = get_mongo()  # returns arena.images from db.py
        all_docs = mongo_collection.find({}, {"uid": 1, "image": 1, "_id": 0})
        db_images: dict[str, str] = {
            doc["uid"]: doc["image"]
            for doc in all_docs
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {e}")

    if not db_images:
        raise HTTPException(status_code=503, detail="No profiles found in database. Run Phase 1 scraper first.")

    # ── step 2: run facial recognition ────────────────────────────────────────
    try:
        matched_uid = find_closest_match(
            login_image_data=payload.image,   # base64 string from webcam
            db_images_dict=db_images,         # {uid: base64/bytes from Mongo}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Facial recognition error: {e}")

    if matched_uid is None:
        # no face matched within the 0.7 confidence threshold
        raise HTTPException(status_code=401, detail="Face not recognised. Please try again.")

    # ── step 3: cross-reference uid in MySQL ──────────────────────────────────
    try:
        conn = get_mysql()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT uid, name, elo_rating FROM users WHERE uid = %s", (matched_uid,))
        user = cursor.fetchone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MySQL error: {e}")
    finally:
        cursor.close()
        conn.close()

    if not user:
        # face recognised but uid not in MySQL (shouldn't normally happen)
        raise HTTPException(status_code=404, detail="Matched user not found in records.")

    # ── step 4: mark user as online + create session ──────────────────────────
    try:
        conn = get_mysql()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_online = TRUE WHERE uid = %s", (matched_uid,))
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not update online status: {e}")
    finally:
        cursor.close()
        conn.close()

    request.session["uid"] = user["uid"]
    request.session["name"] = user["name"]

    return JSONResponse({
        "success": True,
        "uid": user["uid"],
        "name": user["name"],
        "elo_rating": user["elo_rating"],
    })


# ── POST /auth/logout ─────────────────────────────────────────────────────────
@app.post("/auth/logout")
async def logout(request: Request):
    uid = request.session.get("uid")
    if uid:
        try:
            conn = get_mysql()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_online = FALSE WHERE uid = %s", (uid,))
            conn.commit()
        except Exception:
            pass
        finally:
            cursor.close()
            conn.close()
        request.session.clear()
    return JSONResponse({"success": True})


# ── GET /auth/me — handy helper for the frontend to check session state ────────
@app.get("/auth/me")
async def me(request: Request):
    uid = request.session.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Not logged in")
    return JSONResponse({"uid": uid, "name": request.session.get("name")})
