from dotenv import load_dotenv
import os

# load_dotenv()

# print(os.getenv('INPUT_FILE_PATH'))
# print(os.getenv('PRESERVED_OUTPUT_FILE_PATH'))
# print(os.getenv('CLEANED_OUTPUT_FILE_PATH'))

from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["coach-box-db"]

collection_names = db.list_collection_names()
if "tokens" in collection_names:
    print("The 'tokens' collection exists.")
else:
    print("The 'tokens' collection does not exist.")
