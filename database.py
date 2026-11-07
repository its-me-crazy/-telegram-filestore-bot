import datetime
import pytz
import motor.motor_asyncio
from config import MONGO_URI, DATABASE_NAME

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]
users_col = db["users"]
fsub_col = db["force_subs"]
IST = pytz.timezone('Asia/Kolkata')

async def fix_old_users():
    now = datetime.datetime.now(IST)
    # Find users missing the date field and update them
    result = await users_col.update_many(
        {"date": {"$exists": False}},
        {
            "$set": {
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%I:%M:%S %p"),
                "day": now.strftime("%A")
            }
        }
    )
    print(f"Updated {result.modified_count} old user records with default IST timestamps.")

import asyncio
asyncio.run(fix_old_users())

async def add_user(user_id: int, first_name: str = "User", username: str = None):
    now = datetime.datetime.now(IST)
    await users_col.update_one(
        {"user_id": user_id},
        {
            "$setOnInsert": {
                "user_id": user_id,
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%I:%M:%S %p"), 
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
    pipeline = [
        {"$group": {
            "_id": "$user_id",
            "user_id": {"$first": "$user_id"},
            "first_name": {"$first": "$first_name"},
            "username": {"$first": "$username"},
            "date": {"$first": "$date"},
            "time": {"$first": "$time"},  # <--- Included time in aggregation grouping
            "day": {"$first": "$day"}
        }}
    ]
    return [doc async for doc in users_col.aggregate(pipeline)]

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
