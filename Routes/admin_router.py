import json
from fastapi import Depends, HTTPException, status, Query, APIRouter, Body, Response, Request, File, UploadFile, WebSocket, WebSocketDisconnect, WebSocketDisconnect
from models import Admin, User, ProgrammingUpdateRequest, TokenData, Coach, Event, CoachHours, CoachDetail, CoachPublic, EventPublic, CoachHoursPublic, CreateUserData, TokenPublic, UpdateUserData, CoachInAdmin
from auth import authenticate_user, verify_password, create_tokens, get_current_user, get_user, get_password_hash, admin_dependency, api_key_validator, validate_admin_token
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pymongo import ReturnDocument
from db import get_database
from logger import coach_logger
from datetime import timedelta, datetime
from dotenv import load_dotenv
from jose import JWTError, jwt
import os
import random
import string
from Functions.link_extractor import fetch_youtube_links_async as link_extractor
from Functions.parse_links import find_weekly_links, find_class_wods_pdf_link
from typing import Optional, Union, List, Dict
from pprint import pprint as pp
from websocket_manager import manager
from starlette.status import WS_1008_POLICY_VIOLATION
# from Functions.Slack.slack_functions import update_slack
load_dotenv()

admin_router = APIRouter()


async def update_weekly_materials(db, pdf_link: str, video_links: Dict[str, str], current_week_number: int):

    materials_update = {
        "week_number": current_week_number,  # Optionally store the week number
        "pdf_link": pdf_link,
        "video_links": video_links,
        "last_updated": datetime.utcnow()  # Store the last update time
    }
    
    # Use a static identifier for the current week's document, like 'current_week'
    result = await db.programming_materials.update_one(
        {"identifier": "current_week"},  # This identifier remains constant
        {"$set": materials_update},
        upsert=True  # This creates a new document if one doesn't exist for the 'current_week'
    )
    return result.modified_count > 0  # Returns True if the update was successful


@admin_router.post("/update-programming-materials")
async def update_programming_materials(
    request: Dict,  # Accept a generic dictionary
    api_key: str = Depends(api_key_validator),
    db = Depends(get_database)):
    coach_logger.log_info("[+] Received request to update programming materials.")
    # update_slack("Received request to update programming materials, Processing...")
    # print(request)
    # print(request.get("htmlBody"))
    # Get the weekly video links
    weekly_video_links = find_weekly_links(request.get("htmlBody"))
    # Get the PDF link
    pdf_link = find_class_wods_pdf_link(request.get("htmlBody"))

    if pdf_link: coach_logger.log_info(f"[+] Found PDF link: {pdf_link}")
    else: coach_logger.log_error("[-] Failed to find PDF link.")

    # Validate the request dictionary to ensure required fields are present
    # pdf_link = request.get("pdf_link")
    # website_links = request.get("website_links")
    if not pdf_link or not weekly_video_links:
        coach_logger.log_error("[-] Missing 'pdf_link' or 'website_links' in the request.")
        # Return succesfful code
        return Response(status_code=200)
        # return {status_code: 200, detail: "Missing 'pdf_link' or 'website_links' in the request."}
        raise HTTPException(
            status_code=400, 
            detail="Missing 'pdf_link' or 'website_links' in the request."
        )
    
    # Extract YouTube links from provided URLs
    youtube_links = await link_extractor(weekly_video_links)
    
    # Update the database with the new PDF link and YouTube links
    update_result = await update_weekly_materials(db, pdf_link, youtube_links, 55)

    # Handle the response, based on whether the update was successful
    if update_result:
        coach_logger.log_info("[+] Programming materials updated successfully.")
        # update_slack("Programming materials updated successfully.")
        return {"message": "Programming materials updated successfully."}
    coach_logger.log_error("[-] Failed to update programming materials.")
    # update_slack("Failed to update programming materials.")
    raise HTTPException(status_code=400, detail="Failed to update programming materials.")


@admin_router.get("/get-users", response_model=List[CoachInAdmin])
async def get_users(db=Depends(get_database), admin: Admin = Depends(admin_dependency)):
    coach_logger.log_info(f"[+] Admin {admin.first_name} requested to get users.")
    try:
        users_collection = db.users
        users_cursor = users_collection.find().limit(50)  # Limiting the results to the first 50 users
        users_list = await users_cursor.to_list(length=50)  # Ensuring no more than 50 are converted to a list
        for item in users_list:
            item["id"] = str(item["_id"])
            del item["_id"]
            # pp(item)
            if item.get("image_url"):
            #     print('here')
                # print(item["image_url"])
                item["image_url"] = os.path.basename(item["image_url"])
        # print(users_list[5])
        return users_list
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))



@admin_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db=Depends(get_database)):
    await websocket.accept()
    admin = None
    try:
        # The first message from the client should be the token for authentication
        auth_data = await websocket.receive_text()
        print("Received token data:", auth_data)  # Debugging: log the received data
        # Parse the JSON to extract the token
        auth_json = json.loads(auth_data)
        token = auth_json.get('token')
        print("Extracted token:", token)  # Debugging: log the extracted token

        # token = auth_data  # Assuming the client sends the token directly, adjust if it's in a JSON structure
        print(type(token))
        admin = await validate_admin_token(token, db)
        if admin is None:
            coach_logger.log_error("[-] WS user failed to authenticate as an Admin.")
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return

        coach_logger.log_info(f"[+] Admin {admin.first_name} connected to the websocket.")
        await manager.connect(websocket)  # Add the connection to the manager

        while True:
            # The admin is now authenticated, and you can receive further messages
            data = await websocket.receive_text()
            coach_logger.log_info(f"[+] Message from {admin.first_name}: {data}")

            # Here you can broadcast messages or handle different types of incoming data

    except WebSocketDisconnect:
        coach_logger.log_info(f"[-] Admin {admin.first_name if admin else 'unknown'} disconnected from the websocket.")
        manager.disconnect(websocket)
        # if admin:
        #     # Only broadcast the disconnect message if the user was successfully authenticated
        #     await manager.broadcast(f"Admin {admin.first_name} has disconnected.")