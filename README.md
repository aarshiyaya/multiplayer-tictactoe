# ByteMe Arena

A real-time multiplayer Tic-Tac-Toe platform with facial recognition authentication and Elo-based matchmaking.

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSockets-010101?style=for-the-badge&logo=socketdotio&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

---

## Overview

ByteMe Arena is a full-stack multiplayer gaming platform where users log in via facial recognition instead of passwords. Once authenticated, players are matched against opponents of similar skill using an Elo rating system. Matches are played in real time over WebSockets, with all game logic validated server-side to prevent client manipulation.

---

## Features

- **Facial recognition login** — no passwords; authentication uses live face matching against stored profile images
- **Real-time gameplay** — moves and game state synced over persistent WebSocket connections
- **Elo-based matchmaking** — players are ranked and matched by skill rating, updated after every match
- **Live online status** — see which players are currently active
- **Server-side validation** — all move legality and win detection handled on the backend
- **Dual-database architecture** — relational data in MySQL, image data in MongoDB

---

## Architecture

```
Client (Browser)
      |
      | HTTP (auth, matchmaking)
      | WebSocket (live gameplay, presence)
      v
FastAPI Server (main.py)
      |
      |-- MySQL (users, match history, Elo ratings)
      |-- MongoDB (base64 face images, keyed by UID)
      |-- face_recognition (login verification)
```

User records and match history live in MySQL. Face images are stored in MongoDB, linked to users by UID. On login, the submitted image is compared against the stored encoding — no session tokens, no passwords.

---

## Database Schemas

### MySQL — `byteme`

```sql
CREATE TABLE IF NOT EXISTS users (
    uid          VARCHAR(50)  PRIMARY KEY,
    name         VARCHAR(100),
    elo_rating   INT          DEFAULT 1200,
    is_online    BOOLEAN      DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS matches (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    player1_uid  VARCHAR(255),
    player2_uid  VARCHAR(255),
    winner_uid   VARCHAR(255),
    result       ENUM('win', 'draw', 'forfeit'),
    played_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
```

### MongoDB — `arena.images`

```json
{
  "uid":   "string — matches MySQL users.uid",
  "image": "string — base64-encoded profile photo"
}
```

---

## Setup & Run

**Prerequisites:** Docker, Python 3.11+, [uv](https://github.com/astral-sh/uv)

### 1. Start databases

```bash
docker compose up -d
```

Starts MySQL on port `3308` and MongoDB on port `27019`.

### 2. Install dependencies

```bash
uv sync
```

Reads `pyproject.toml`, creates `.venv`, and installs all packages.

### 3. Populate the database

```bash
uv run python scraper.py
```

Scrapes profile images from the batch data CSV, writes user records to MySQL, and stores face images in MongoDB.

### 4. Start the server

```bash
uv run uvicorn main:app --reload
```

Server runs at `http://localhost:8000`.

---

## Project Structure

```
.
├── main.py          # FastAPI app, WebSocket handlers, game logic
├── scraper.py       # Database seeding from CSV
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Design Decisions

**Why two databases?** User records and match history are relational and benefit from SQL queries and joins. Face images are binary blobs with no relational structure — MongoDB handles those more naturally and keeps MySQL clean.

**Why server-side game validation?** Trusting the client for move legality opens the door to cheating. All validation runs on the server; the client only sends intended moves and renders state it receives back.

**Why Elo?** Elo is simple, well-understood, and self-correcting over time. New users start at 1200 and ratings converge to reflect actual skill after enough matches.
