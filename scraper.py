import csv
import requests
import base64
from db import get_mysql, get_mongo


def run():
    mysql = get_mysql()
    cursor = mysql.cursor()
    mongo_col = get_mongo()

    session = requests.Session()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            uid VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100),
            elo_rating INT DEFAULT 1200,
            is_online BOOLEAN DEFAULT FALSE
        )
    """)
    mysql.commit()

    with open("utils/batch_data.csv", newline="") as f:
        reader = csv.DictReader(f)

        count = 0

        for row in reader:
            uid = row["uid"].strip()
            name = row["name"].strip()
            url = row["website_url"].strip()

            if not url.startswith("http"):
                url = "https://" + url

            image_url = f"{url.rstrip('/')}/images/pfp.jpg"

            try:
                resp = session.get(image_url, timeout=5)
                if resp.status_code != 200:
                    print(f"[SKIP] {uid}: HTTP fail")
                    continue

                image_b64 = base64.b64encode(resp.content).decode("utf-8")

                # MySQL
                cursor.execute(
                    "INSERT INTO users (uid, name) VALUES (%s, %s) ON DUPLICATE KEY UPDATE name=%s",
                    (uid, name, name)
                )

                # Mongo (store IMAGE, not encoding)
                mongo_col.update_one(
                    {"uid": uid},
                    {"$set": {"uid": uid, "image": image_b64}},
                    upsert=True
                )

                print(f"[OK] {uid}")
                count += 1

                if count % 10 == 0:
                    mysql.commit()

            except Exception as e:
                print(f"[ERROR] {uid}: {e}")
                continue

        mysql.commit()

    cursor.close()
    mysql.close()
    print("Done.")


if __name__ == "__main__":
    run()