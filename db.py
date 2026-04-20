import mysql.connector
from pymongo import MongoClient

def get_mysql():
    return mysql.connector.connect(
        host="localhost",
        port=3308,
        user="root",
        password="rootpassword",
        database="byteme"
    )

def get_mongo():
    client = MongoClient(
        "mongodb://admin:password123@localhost:27019/?authSource=admin"
    )
    return client["arena"]["images"]