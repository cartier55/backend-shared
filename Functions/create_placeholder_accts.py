import sys
sys.path.append('C:/Users/carte/OneDrive/Documents/Code/Coach Box/backend/')

from motor.motor_asyncio import AsyncIOMotorClient
from auth import get_password_hash  # Replace with your actual import
import asyncio

async def create_placeholder_coaches():
    # Open a new database connection
    mongodb_client = AsyncIOMotorClient("mongodb+srv://cjames:<creds>@cluster0.hxjsezh.mongodb.net/")
    db = mongodb_client.get_database("coach-box-db")  # Replace with your actual database name
    coaches_collection = db.get_collection("users")  # Replace with your actual collection name

    # Your placeholder coaches data remains the same
    placeholder_coaches = [
        {"first_name": "Carter", "last_name": "James", "email": "cj@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Doza", "last_name": "Doe", "email": "doza@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Laurie", "last_name": "Doe", "email": "laurie@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Jonathan", "last_name": "Doe", "email": "jonathan@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Tom", "last_name": "Doe", "email": "tom@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Ashlyn", "last_name": "Doe", "email": "ashlyn@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Janet", "last_name": "Doe", "email": "janet@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Marni", "last_name": "Doe", "email": "marni@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Nick", "last_name": "Doe", "email": "nick@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Aly", "last_name": "Doe", "email": "aly@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Mirka", "last_name": "Doe", "email": "mirka@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Jay", "last_name": "Doe", "email": "jay@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Craig", "last_name": "Doe", "email": "craig@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Seth", "last_name": "Doe", "email": "seth@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Jana", "last_name": "Doe", "email": "jana@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Chris", "last_name": "Doe", "email": "chris@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Brandon", "last_name": "Doe", "email": "brandon@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Todd", "last_name": "Doe", "email": "todd@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Matt", "last_name": "Doe", "email": "matt@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
        {"first_name": "Jacob", "last_name": "Doe", "email": "jacob@gmail.com", "hashed_password": get_password_hash("abc123"), "type": "coach"},
    ]

    await coaches_collection.insert_many(placeholder_coaches)

    # Close the database connection
    mongodb_client.close()

# Run this function once to populate your database
# You can run this in a script or in an initialization block of your application

if __name__ == "__main__":
    asyncio.run(create_placeholder_coaches())
