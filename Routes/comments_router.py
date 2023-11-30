# comments_router.py
from fastapi import APIRouter, HTTPException, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Union
from db import get_database
from models import CommentCreate, CommentInDB, Comment, Coach
from datetime import datetime, timedelta
from auth import get_current_user
from bson import ObjectId
import os
import pytz

comments_router = APIRouter()


@comments_router.post("/comments", response_model=Comment)
async def create_comment(comment: CommentCreate, db=Depends(get_database), current_user: Coach = Depends(get_current_user)):
    comments_collection = db.get_collection("comments")
    
    # Create a new Comment with the current server timestamp
    current_datetime = datetime.utcnow()  # Use UTC time for consistency
    comment_with_date = {
        **comment.model_dump(),
        "coach_id": current_user.id,
        "date": current_datetime,
    }

    # Insert the new Comment into the database
    comment_op = await comments_collection.insert_one(comment_with_date)
    
    # Retrieve the newly inserted Comment
    new_comment = await comments_collection.find_one({"_id": comment_op.inserted_id})
    new_comment["id"] = str(new_comment["_id"])
    # return CommentInDB(**{**new_comment, "_id": str(new_comment["_id"])})
    return CommentInDB(**new_comment)

# @comments_router.get("/comments", response_model=List[Union[Comment, dict]])
@comments_router.get("/comments")
async def read_comments(date: datetime = Query(None, alias="date"), db=Depends(get_database), current_user: Coach = Depends(get_current_user),):
    comments_collection = db.get_collection("comments")
    users_collection = db.get_collection("users")
    
    if date:
        # Assume 'date' is in local time and convert to UTC
        # If 'date' is already in UTC, remove the conversion
        tz = pytz.timezone('America/New_York')  # Replace with your time zone
        start_of_day_local = tz.localize(datetime(date.year, date.month, date.day))
        start_of_day_utc = start_of_day_local.astimezone(pytz.utc)
        end_of_day_utc = start_of_day_utc + timedelta(days=1)
        
        # Filter comments by the date
        comments = await comments_collection.find({
            "date": {
                "$gte": start_of_day_utc,
                "$lt": end_of_day_utc
            }
        }).to_list(100)
    else:
        comments = await comments_collection.find({}).to_list(100)
    
     # Prepare the output list
    enriched_comments = []
    for comment in comments:
        # comment_dict = CommentInDB(**{**comment, "id": str(comment["_id"])})
        # comment_dict = comment_dict.model_dump()  # Convert CommentInDB object to dictionary
        
        # Fetch the user who matches with coach_id
        coach_info = await users_collection.find_one({"_id": ObjectId(comment.get("coach_id", None))})
        # print(coach_info)
        if coach_info:
            # You can choose which user fields you want to include
            comment["coach_info"] = {
                "first_name": coach_info.get("first_name", ""),
                "last_name": coach_info.get("last_name", ""),
                "email": coach_info.get("email", ""),
                "pfp": os.path.basename(coach_info.get("image_url", ""))
            }

        # Convert ObjectId to str for JSON serialization
        comment["_id"] = str(comment["_id"])
        # print(comment)
        enriched_comments.append(comment)
    
    return enriched_comments

@comments_router.get("/comments/{comment_id}", response_model=Comment)
async def read_comment(comment_id: str, db=Depends(get_database), current_user: Coach = Depends(get_current_user),):
    comments_collection = db.get_collection("comments")
    comment = await comments_collection.find_one({"_id": comment_id})
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return CommentInDB(**comment)

# @comments_router.put("/comments/{comment_id}", response_model=Comment)
@comments_router.put("/comments/{comment_id}")
async def update_comment(comment_id: str, comment: CommentCreate, db=Depends(get_database), current_user: Coach = Depends(get_current_user),):
    comments_collection = db.get_collection("comments")

    existing_comment = await comments_collection.find_one({"_id": ObjectId(comment_id)})

    if existing_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    if existing_comment["coach_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have permission to update this comment")

    updated_comment = await comments_collection.find_one_and_update(
        {"_id": ObjectId(comment_id)},
        {"$set": comment.model_dump()},
        return_document=True
    )

    updated_comment["_id"] = str(updated_comment["_id"])
    return updated_comment

@comments_router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, db=Depends(get_database), current_user: Coach = Depends(get_current_user),):
    comments_collection = db.get_collection("comments")
    print(current_user)
    existing_comment = await comments_collection.find_one({"_id": ObjectId(comment_id)})

    if existing_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    if existing_comment["coach_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have permission to delete this comment")

    deleted_comment = await comments_collection.find_one_and_delete({"_id": ObjectId(comment_id)})

    return {"message": "Comment deleted successfully"}