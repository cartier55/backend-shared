from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from logger import coach_logger
import asyncio
from fastapi import FastAPI
from zoneinfo import ZoneInfo  # Python 3.9+
from websocket_manager import manager
from bson import ObjectId

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongodb_client, mongodb
    coach_logger.log_info("[+] Connecting to MongoDB...")
    # mongodb_client = AsyncIOMotorClient("mongodb://localhost:27017/")
    mongodb_client = AsyncIOMotorClient("mongodb+srv://web_guru:{dbpwd}@cluster0.hxjsezh.mongodb.net/")
    mongodb = mongodb_client.get_database("coach-box-dev-db")
    
    await cleanup_expired_tokens(mongodb)

    # Start scheduler with tasks
    scheduler.add_job(
        mark_inactive_users,
        'interval',
        minutes=15,
        args=[mongodb, manager],
        next_run_time=datetime.now(ZoneInfo("UTC"))
    )
    coach_logger.log_info("[+] Starting scheduler...")
    scheduler.start()

    yield  # Here FastAPI will start handling requests

    # Shutdown logic
    if scheduler.running:
        coach_logger.log_info("[+] Shutting down scheduler...")
        scheduler.shutdown()
    mongodb_client.close()
    coach_logger.log_info("[+] Application shutdown")


async def get_database():
    return mongodb

async def cleanup_expired_tokens(db):
    coach_logger.log_info("[+] Cleaning up expired tokens...")
    current_time = datetime.utcnow()
    await db.tokens.delete_many({"expires_at": {"$lt": current_time}})

async def mark_inactive_users(db, manager):
    coach_logger.log_info("[+] Running scheduled task to mark inactive users...")
    inactive_threshold = datetime.utcnow() - timedelta(minutes=5)  # Check for users who haven't made a request in the last 5 minutes
    # First, find all users who will be marked as inactive
    inactive_users = await db.users.find(
        {"last_request_at": {"$lt": inactive_threshold}, "isActive": True},
        {"_id": 1}
    ).to_list(None)
    # Extract the user IDs
    inactive_user_ids = [str(user['_id']) for user in inactive_users]

    # If have been inactive for 5 minutes, mark as inactive
    update_result = await db.users.update_many(
        {"_id": {"$in": [ObjectId(id) for id in inactive_user_ids]}},
        {"$set": {"isActive": False}}
    )

    coach_logger.log_info(f"[+] Marked {update_result.modified_count} users as inactive.")

    # If any users were marked as inactive, broadcast their IDs
    if update_result.modified_count > 0:
        for user_id in inactive_user_ids:
            await manager.broadcast({
                "message": "user_status_update",
                "user_id": user_id,
                "isActive": False
            })
