import csv
import requests
import base64
from db import get_mysql, get_mongo
import time

def run():
    mysql = get_mysql()
    cursor = mysql.cursor()
    mongo = get_mongo()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            uid VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100),
            elo_rating INT DEFAULT 1200,
            is_online BOOLEAN DEFAULT FALSE
        )
    """)
    mysql.commit()

    with open("batch_data.csv", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uid = row["uid"].strip()
            name = row["name"].strip()
            url = row["website_url"].strip()
            if not url.startswith("http"):
                url = "https://" + url
            image_url = f"{url}/images/pfp.jpg"

            try:
                resp = requests.get(image_url, timeout=5)
                if resp.status_code != 200:
                    print(f"[SKIP] {uid}: HTTP {resp.status_code}")
                    continue

                image_b64 = base64.b64encode(resp.content).decode("utf-8")

                cursor.execute(
                    "INSERT INTO users (uid, name) VALUES (%s, %s) ON DUPLICATE KEY UPDATE name=%s",
                    (uid, name, name)
                )
                mysql.commit()

                mongo.update_one(
                    {"uid": uid},
                    {"$set": {"uid": uid, "image": image_b64}},
                    upsert=True
                )
                print(f"[OK] {uid}")

            except Exception as e:
                print(f"[ERROR] {uid}: {e}")
                continue

            time.sleep(0.2)

    cursor.close()
    mysql.close()
    print("Done.")

if __name__ == "__main__":
    run()