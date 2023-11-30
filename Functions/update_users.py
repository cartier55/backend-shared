from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
import asyncio

async def update_users(db_url: str, db_name: str):
    # Connect to MongoDB asynchronously
    client = AsyncIOMotorClient(db_url)
    db = client[db_name]
    users_collection: AsyncIOMotorCollection = db['users']

    # Update operation
    update_result = await users_collection.update_many(
        {},  # empty filter matches all documents
        {
            "$unset": {"status": ""},  # Remove the status field
            "$set": {"isActive": False, "welcomed": False, "last_request_at": None}  # Set isActive to False and reset welcomed to False
        }
    )

    # Close the MongoDB connection
    client.close()

    return update_result.matched_count, update_result.modified_count



# Usage example
db_url = "mongodb://localhost:27017/"
db_name = "coach-box-db"

async def main():
    matched, modified = await update_users(db_url, db_name)
    print(f"Documents matched: {matched}, Documents modified: {modified}")

# Run the async function
asyncio.run(main())
