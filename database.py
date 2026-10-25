import datetime
import motor.motor_asyncio
from config import MONGO_URI, DATABASE_NAME

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]

users_col = db["users"]
fsub_col = db["force_subs"]

async def add_user(user_id: int, first_name: str = "User", username: str = None):
    now = datetime.datetime.now()
    # upsert=True creates the document if it doesn't exist, or updates it if it does!
    await users_col.update_one(
        {"user_id": user_id},
        {
            "$setOnInsert": {
                "user_id": user_id,
                "date": now.strftime("%Y-%m-%d"),
                "day": now.strftime("%A")
            },
            "$set": {
                "first_name": first_name if first_name and first_name != "User" else "User",
                "username": username
            }
        },
        upsert=True
    )

async def get_all_users():
    return [doc["user_id"] async for doc in users_col.find({})]

async def get_all_users_data():
    return [doc async for doc in users_col.find({})]

async def total_users_count():
    return await users_col.count_documents({})

async def add_fsub_channel(channel_id: int, channel_title: str, invite_link: str):
    await fsub_col.update_one(
        {"channel_id": channel_id},
        {"$set": {"channel_title": channel_title, "invite_link": invite_link}},
        upsert=True
    )

async def remove_fsub_channel(channel_id: int):
    await fsub_col.delete_one({"channel_id": channel_id})

async def get_fsub_channels():
    return [doc async for doc in fsub_col.find({})]
