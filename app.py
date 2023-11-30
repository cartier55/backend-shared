import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Query, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.middleware.cors import CORSMiddleware
from Functions.schedule_cleaner import CFClassesDataCleaner
from Functions.event_creator import create_events_with_duration
from typing import List, Dict
from bson import ObjectId
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import timedelta, datetime
from db import get_database, lifespan
from auth import authenticate_user, verify_password, create_tokens, get_current_user, get_current_user_manual, get_user, get_password_hash
from models import User, Token, TokenData, Coach, Event, CoachHours, CoachDetail, CoachPublic, EventPublic, CoachHoursPublic, CreateUserData, FeatureRequestCreate, FeatureRequestModel, FeatureRequestInDB
from fastapi.responses import FileResponse
from logger import coach_logger
import pytz
import pandas as pd
from jose import ExpiredSignatureError, JWTError, jwt
from fastapi.responses import JSONResponse
from fastapi import HTTPException, Request, Response
from fastapi import HTTPException, status

from Routes.auth_router import auth_router
from Routes.events_router import events_router
from Routes.comments_router import comments_router
from Routes.admin_router import admin_router

SECRET_KEY = "diddydoggy"
ALGS = ["HS256"]
ACCESS_TOKEN_EXPIRE_MINUTES = 30

INPUT_FILE_PATH = r'C:/Users/carte/OneDrive/Documents/Code/Coach Box/backend/Data/OG_Schedule.xlsx'
PRESERVED_OUTPUT_FILE_PATH = r'C:/Users/carte/OneDrive/Documents/Code/Coach Box/backend/Data/Output/Date_Preserved.xlsx'
CLEANED_OUTPUT_FILE_PATH = r'C:/Users/carte/OneDrive/Documents/Code/Coach Box/backend/Data/Output/Cleaned_Schedule.xlsx'

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# oauth_2_scheme = OAuth2PasswordBearer(tokenUrl="token")

load_dotenv()

app = FastAPI(lifespan=lifespan)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "https://coachify.onrender.com",
#         "https://coachify.graytecknologies.com",
#         "http://35.160.120.126",
#         "http://44.233.151.27",
#         "http://34.211.200.85"
#     ],  # Adjust this to your frontend URL
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
#     expose_headers=["x-Expired"]  # Add your custom headers here
# )

# CORS middleware settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Adjust this to your frontend URL
    # allow_origins=["*"],  # Adjust this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-expired"]  # Add your custom headers here
)

@app.middleware("http")
async def update_last_request_data(request: Request, call_next):
    response = await call_next(request)
    # Skip middleware logic for refresh endpoint
    if request.url.path == "/refresh":
        return response
    if "Authorization" not in request.headers:
        # This is a non authenticated request
        # Not able to track user activity
        # coach_logger.log_info("[+] No Authorization header found")
        return response
    # coach_logger.log_info("[+] Authorization header found")
    token = request.headers.get("Authorization").split(" ")[1]
    if token == "Og==":
        # This is a non authenticated request
        # Not able to track user activity
        # This is a login request
        # coach_logger.log_info("[+] Token is 'Basic Og=='. Skipping...")
        return response
    try:
        db = await get_database()
        user = await get_current_user_manual(token=token, db=db)
        if user == "TokenExpired":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Token has expired."},
                headers={
                    "WWW-Authenticate": "Bearer",
                    "X-Expired": "True",
                    "Access-Control-Allow-Origin": "*",  # or "http://localhost:3000"
                    "Access-Control-Expose-Headers": "X-Expired",  # Expose your custom headers
                    }
            )

        if user == "InvalidToken":
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token."},
            )
        if user:
            await db.users.update_one(
                {"_id": ObjectId(user.id)},
                {"$set": {"last_request_at": datetime.utcnow(), "isActive": True}}
            )

        return response
    except Exception as e:
        # Log and handle any other exceptions
        print('500 error')
        return Response("An error occurred", status_code=500)


app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(events_router, prefix="/api/events", tags=["events"])
app.include_router(comments_router, prefix="/api", tags=["comments"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])

@app.get("/")
async def read_root(db=Depends(get_database)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
    else:
        return {"status": "Database is connected", "db_name": db.name}
    
@app.get("/api/users/me", response_model=Coach)
async def read_users_me(current_user: Coach = Depends(get_current_user)):
    return current_user

@app.get("/api/images/{filename}")
async def read_item(filename: str):
    # file_path = f"/opt/var/data/db/pfps/{filename}"
    file_path = f"C:/Users/carte/OneDrive/Documents/Code/Coach Box/backend/Data/Uploaded/{filename}"
    return FileResponse(file_path)

@app.post("/api/feature-requests")
async def create_feature_request(request_data: FeatureRequestCreate, db=Depends(get_database), current_user: Coach = Depends(get_current_user)):
    feature_request = FeatureRequestModel(coach_id=current_user.id, **request_data.dict())
    await db.feature_reqs.insert_one(feature_request.dict())
    return feature_request

@app.get("/api/wods-pdf")
async def wods_pdf_endpoint(db=Depends(get_database)):
    # Query the 'programming_materials' collection for the 'current_week' document
    current_week_materials = await db.programming_materials.find_one({"identifier": "current_week"})
    # print(current_week_materials)
    if current_week_materials and "pdf_link" in current_week_materials:
        return {"pdf_link": current_week_materials["pdf_link"]}
    raise HTTPException(status_code=404, detail="Weekly PDF not found")


@app.get("/api/daily-prog")
async def daily_prog_endpoint(db=Depends(get_database)):
    # Set your desired timezone
    tz = pytz.timezone('America/New_York')  # Replace 'Your/Timezone' with your timezone, e.g., 'America/New_York'
    # Query the 'programming_materials' collection for the 'current_week' document
    current_week_materials = await db.programming_materials.find_one({"identifier": "current_week"})
    
    if current_week_materials:
        # Get current weekday according to the specified timezone
        weekday = datetime.now(tz).strftime('%A')  # Get current weekday, e.g., 'Monday'
        coach_logger.log_info(f"[+] Today is {weekday}")
        video_link = current_week_materials.get("video_links", {}).get(weekday)
        
        if video_link:
            coach_logger.log_info(f"[+] Found video link: {video_link}")
            return {"video_link": video_link}
        else:
            coach_logger.log_error("[-] Daily video not found for today")
            raise HTTPException(status_code=404, detail="Daily video not found for today")
    
    coach_logger.log_error("[-] Weekly programming materials not found")
    raise HTTPException(status_code=404, detail="Programming materials not found")

# Change at 7pm est
# @app.get("/api/daily-prog")
# async def daily_prog_endpoint(db=Depends(get_database)):
#     # Set the timezone to Eastern Time
#     tz = pytz.timezone('America/New_York')
    
#     # Get the current time in the specified timezone
#     current_time = datetime.now(tz)
    
#     # If it's past 7:00 PM, use the next day's date
#     if current_time.hour >= 19:
#         current_time += timedelta(days=1)
    
#     # Query the 'programming_materials' collection for the 'current_week' document
#     current_week_materials = await db.programming_materials.find_one({"identifier": "current_week"})
    
#     if current_week_materials:
#         # Get current weekday according to the adjusted current time
#         weekday = current_time.strftime('%A')
#         coach_logger.log_info(f"[+] Today is {weekday}")
        
#         # Fetch the video link for the current or next day, depending on the time
#         video_link = current_week_materials.get("video_links", {}).get(weekday)
        
#         if video_link:
#             coach_logger.log_info(f"[+] Found video link: {video_link}")
#             return {"video_link": video_link}
#         else:
#             coach_logger.log_error("[-] Daily video not found for today")
#             raise HTTPException(status_code=404, detail="Daily video not found for today")
    
#     coach_logger.log_error("[-] Weekly programming materials not found")
#     raise HTTPException(status_code=404, detail="Programming materials not found")