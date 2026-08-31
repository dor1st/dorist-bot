import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
if not MONGO_URL:
    raise ValueError("Ошибка: MONGO_URL не найден в файле .env или Variables Railway")

mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)

try:
    mongo_client.admin.command('ping')
    print("Успешное подключение к MongoDB Atlas!")
except Exception as e:
    print(f"Ошибка подключения к MongoDB: {e}")

db = mongo_client["discord_tickets_db"]

tickets_col = db["tickets"]
counters_col = db["counters"]
deleted_tickets_col = db["deleted_tickets"]
settings_col = db["settings"]
message_stats_col = db["message_stats"]
bump_stats_col = db["bump_stats"]

# Индексы
tickets_col.create_index("transcript_url", unique=True, sparse=True)
deleted_tickets_col.create_index("transcript_url", unique=True, sparse=True)
message_stats_col.create_index([("channel_id", 1), ("day", 1), ("user_id", 1)])
bump_stats_col.create_index([("channel_id", 1), ("day", 1), ("user_id", 1)])


def get_next_sequence_value(sequence_name: str) -> int:
    seq = counters_col.find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=True
    )
    return seq["sequence_value"]