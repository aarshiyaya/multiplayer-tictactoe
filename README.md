[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/rd3t__9M)
# Introduction to Software Systems S26 
## Course Project: Identity-Verified Multiplayer Arena

The assignment is available [here](https://cs6201.github.io/s26/assets/Project.pdf).

[This](https://hackmd.io/@iss-spring-2026/S1WBWzzoWe) is where you can ask questions about it, for which you will receive answers [here](https://hackmd.io/@iss-spring-2026/ryZ_WGzibx).

Good luck, have fun!  

# ByteMe Arena

A real-time multiplayer Tic-Tac-Toe platform with facial recognition login and Elo-based matchmaking.

**Stack:** FastAPI, WebSockets, MySQL, MongoDB, face_recognition

---

## Database Schemas

### MySQL — `byteme` database

```sql
-- Users table (created by scraper.py)
CREATE TABLE IF NOT EXISTS users (
    uid VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100),
    elo_rating INT DEFAULT 1200,
    is_online BOOLEAN DEFAULT FALSE
);

-- Matches table (created automatically on server startup)
CREATE TABLE IF NOT EXISTS matches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    player1_uid VARCHAR(255),
    player2_uid VARCHAR(255),
    winner_uid VARCHAR(255),
    result ENUM('win', 'draw', 'forfeit'),
    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### MongoDB — `arena` database, `images` collection

```json
{
    "uid": "string — matches MySQL users.uid",
    "image": "string — base64-encoded profile photo"
}
```

---

## Setup & Run

### 1. Start databases

```bash
docker compose up -d
```

This starts:
- **MySQL** on port `3308` (root password: `rootpassword`, database: `byteme`)
- **MongoDB** on port `27019` (user: `admin`, password: `password123`)

### 2. Install dependencies and run

```bash
uv sync
```

This reads `pyproject.toml`, creates the `.venv`, and installs all dependencies in one command.

### 3. Populate the database

```bash
uv run python scraper.py
```

This scrapes profile images from the batch data CSV, stores user records in MySQL and face images in MongoDB.

### 4. Start the server

```bash
uv run uvicorn main:app --reload
```

The app runs at `http://localhost:8000`.

---
