import mysql.connector
from pymongo import MongoClient

def get_mysql():
    return mysql.connector.connect(
        host="localhost",
        port=3307,
        user="root",
        password="rootpassword",
        database="byteme_test"
    )

def get_mongo():
    client = MongoClient(
        "mongodb://admin:password123@localhost:27018/?authSource=admin"
    )
    return client["arena"]["images"]