from fastapi import Depends, HTTPException, status, Query, APIRouter, Body, Response, Request, File, UploadFile
from models import User, Admin, Token, TokenData, Coach, Event, CoachHours, CoachDetail, CoachPublic, EventPublic, CoachHoursPublic, CreateUserData, TokenPublic, UpdateUserData
from auth import authenticate_user, verify_password, create_tokens, get_current_user, get_user, get_password_hash, admin_dependency
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
import secrets

load_dotenv()

auth_router = APIRouter()

@auth_router.post("/signup", response_model=TokenPublic)
async def create_coach(response: Response, create_user_data: CreateUserData, db = Depends(get_database)):
    # Check if a user with the given email already exists
    # print(create_user_data)
    if create_user_data.email == '':
        coach_logger.log_error("[-] Email cannot be empty")
        raise HTTPException(status_code=400, detail="Email cannot be empty")
    
    if await get_user(db, create_user_data.email):
        coach_logger.log_error("[-] Email already registered")
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if create_user_data.password == '':
        coach_logger.log_error("[-] Password cannot be empty")
        raise HTTPException(status_code=400, detail="Password cannot be empty")
    # Hash the password
    hashed_password = get_password_hash(create_user_data.password)

    new_coach = {
        "email": create_user_data.email,
        "hashed_password": hashed_password,
        "first_name": create_user_data.first_name,
        "last_name": create_user_data.last_name,
        "disabled": False,
        "type": create_user_data.type  # You can set a type field to distinguish between different types of users
    }

    # Insert the new coach into the database
    coach_logger.log_info(f"[+] Inserting new {create_user_data.type} into the database: {new_coach}")
    results = await db.users.insert_one(new_coach)
    user_id = str(results.inserted_id)
    # print(results)

    # Generate a new access and refresh token
    token_data = {"email": create_user_data.email, "user_id": user_id}
    tokens = await create_tokens(db, data=token_data)  # Make sure create_tokens is an async function
    
    # Save the refresh token in the database
    coach_logger.log_info(f"[+] Setting refresh token as HttpOnly cookie: {tokens['refresh_token']}")
    # response.set_cookie(
    #     key="refresh_token", 
    #     value=tokens["refresh_token"], 
    #     httponly=True, 
    #     secure=True,
    #     samesite="None",
    #     domain=".graytecknologies.com"
    # )
    response.set_cookie(key="refresh_token", value=tokens["refresh_token"], httponly=True)
    return {
        "user":{
            "first_name":create_user_data.first_name,
            "last_name":create_user_data.last_name,
            "email":create_user_data.email
            # "image_url": user.image_url
            },
        "access_token": tokens.get("access_token"),
        "token_type": "bearer"
        }
@auth_router.post("/signin", response_model=TokenPublic)
async def get_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_database)):
    
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        coach_logger.log_error("[-] Incorrect email or password")
        raise HTTPException(status_code=400, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    
    access_token_expires = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")))
        
    token_data = {"email": user.email, "user_id": user.id}
    tokens = await create_tokens(db, data=token_data)
    if not tokens:
        coach_logger.log_error("[-] Could not create tokens")
        raise HTTPException(status_code=500, detail="Could not create tokens")
    
    coach_logger.log_info(f"[+] Setting refresh token as HttpOnly cookie: {tokens['refresh_token']}")
    # response.set_cookie(
    #     path="/",
    #     samesite="None",
    #     key="refresh_token", 
    #     value=tokens["refresh_token"], 
    #     httponly=True, 
    #     domain=".graytecknologies.com",
    #     secure=True
    # )    
    response.set_cookie(key="refresh_token", value=tokens["refresh_token"], httponly=True)
    return_data = {
        "user":{
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "image_url": ''
        },
        "access_token": tokens.get("access_token"),
        "token_type": "bearer"
    }

    if hasattr(user, 'is_admin'):
        return_data["user"]["is_admin"] = user.is_admin
    
    if user.image_url:
        return_data["user"]["image_url"] = os.path.basename(user.image_url)
    
    return return_data
    ...
@auth_router.post('/signout')
async def logout(request: Request, response: Response, db = Depends(get_database)):
    # Get the refresh token from the HttpOnly cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        coach_logger.log_error("[-] Refresh token not found")
        raise HTTPException(status_code=401, detail="Refresh token not found")

    # Delete the refresh token from the database
    coach_logger.log_warning(f"[!] Deleting refresh token: {refresh_token}")
    result = await db.tokens.delete_one({"refresh_token": refresh_token})
    if result.deleted_count == 0:
        coach_logger.log_warning("[!] Refresh token not found in database")
        # raise HTTPException(status_code=401, detail="Refresh token not found in database")

    # Remove the HttpOnly cookie
    coach_logger.log_info("[+] Removing refresh token from HttpOnly cookie")
    response.delete_cookie("refresh_token")

    return {"message": "Successfully logged out"}
@auth_router.post('/refresh', response_model=TokenPublic)
async def refresh_tokens(request: Request, response: Response, db = Depends(get_database)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        coach_logger.log_error("[-] Refresh token not found")
        raise HTTPException(status_code=401, detail="Refresh token not found")

    # Validate the refresh token
    try:
        payload = jwt.decode(refresh_token, os.getenv("REFRESH_TOKEN_SECRET"), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        coach_logger.log_error("[-] Refresh token expired")
        raise HTTPException(status_code=401, detail="Refresh token expired", headers={"X-Refresh-Expired": "True"})
    except jwt.InvalidTokenError:
        coach_logger.log_error("[-] Invalid refresh token")
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    # Verify the token exists in the database
    stored_token = await db.tokens.find_one({"refresh_token": refresh_token})
    if not stored_token:
        coach_logger.log_error("[-] Refresh token not found in database")
        raise HTTPException(status_code=401, detail="Invalid Refresh Token")

    # Delete the old refresh token from the database
    coach_logger.log_warning(f"[!] Deleting old refresh token: {refresh_token}")
    await db.tokens.delete_one({"refresh_token": refresh_token})

    # Generate new access and refresh tokens
    user_id = payload.get("user_id")
    email = payload.get("email")
    token_data = {"email": email, "user_id": user_id}
    new_tokens = await create_tokens(db, data=token_data)

    # Get the user form db from the user_id
    user = await get_user(db, email)
    # Set the new refresh token as HttpOnly cookie
    coach_logger.log_info(f"[+] Setting new refresh token as HttpOnly cookie: {new_tokens['refresh_token']}")
    # response.set_cookie(
    #     key="refresh_token", 
    #     value=new_tokens["refresh_token"], 
    #     httponly=True, 
    #     secure=True,
    #     samesite="None",
    #     domain=".graytecknologies.com"
    # )
    response.set_cookie(key="refresh_token", value=new_tokens["refresh_token"], httponly=True)
    return_data = {"user":{"first_name":user.first_name, "last_name":user.last_name, "email":user.email, "image_url":''}, "access_token": new_tokens["access_token"], "token_type": "bearer"}
    if user.image_url:
        # print(user.image_url)
        return_data["user"]["image_url"] = os.path.basename(user.image_url)
    return return_data

    ...
@auth_router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), db=Depends(get_database), current_user: User = Depends(get_current_user)):
    # Generate a random string for the filename
    random_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    # Get the file extension
    file_extension = os.path.splitext(file.filename)[1]
    # Construct the filename using the user's first name and the random string
    filename = f"{current_user.first_name}_{random_string}{file_extension}"
    # Save the file to the /uploaded directory
    with open(f"/opt/var/data/db/pfps/{filename}", "wb") as f:
        f.write(file.file.read())
    
    # Construct the image URL using the base URL of your server and the filename
    # base_url = "https://example.com"
    image_url = f"/opt/var/data/db/pfps/{filename}"
    
    # Update the user in the database with the image URL
    result = await db.users.update_one(
        {"email": current_user.email},
        {"$set": {"image_url": image_url}}
    )
    
    # Check if the update was successful
    if result.modified_count == 1:
        return {"image_url": os.path.basename(image_url)}
    else:
        raise HTTPException(status_code=500, detail="Failed to update user profile picture")

@auth_router.patch("/update-details", response_model=UpdateUserData)
async def update_user_details(update_data: UpdateUserData, db=Depends(get_database), current_user: User = Depends(get_current_user)):
    update_dict = update_data.dict(exclude_unset=True)  # Exclude fields that are not set
    # print(update_data)
    # print(update_dict)
    # return
    if update_dict.get("email"):
        # Check if the new email is already registered
        if await get_user(db, update_dict.get("email")):
            raise HTTPException(status_code=400, detail="Email already registered")

    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Log the update
    coach_logger.log_info(f"[+] Updating user {current_user.email} with data: {update_dict}")
    
    # Update the user in the database
    result = await db.users.find_one_and_update(
        {"email": current_user.email},
        {"$set": update_dict},
        return_document=ReturnDocument.AFTER
    )
    
    if result:
        return {
                'first_name': result.get('first_name', ''),
                'last_name': result.get('last_name', ''),
                'email': result.get('email', ''),
                'image_url': os.path.basename(result.get('image_url', '')),
                'is_admin': result.get('is_admin', False)
            }
    else:
        raise HTTPException(status_code=500, detail="Failed to update user details")
    ...

# Route to get the current users profile picture url
@auth_router.get("/get-image/")
async def get_image(current_user: User = Depends(get_current_user)):
    return {"image_url": current_user.image_url}


def generate_api_key():
    # Generate a secure random API key
    return secrets.token_urlsafe(32)  # Generates a random URL-safe text string, 32 bytes long

@auth_router.post("/admin/generate-api-key")
async def generate_and_store_api_key(admin: Admin = Depends(admin_dependency), db = Depends(get_database)):
    # Ensure that the user is an admin
    if not admin.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can generate API keys."
        )
    
    # TODO - Send slack message to me when an API key is generated
    
    # Generate a new API key
    new_api_key = generate_api_key()

    # Get the current date and time
    created_at = datetime.utcnow()

    # Save the new API key and the creation date and time in the database
    await db.api_keys.insert_one({"api_key": new_api_key, "created_at": created_at})

    # Return the new API key (You might want to send this in a more secure way than just returning it)
    return {"api_key": new_api_key}

# Route to verify if a user is an admin using the admin dependecy
@auth_router.get("/admin/verify")
async def verify_admin(admin: Admin = Depends(admin_dependency)):
    # Return 200 status code
    return Response(status_code=200)
