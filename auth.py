from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from models import User, Token, TokenData, Coach, Admin, Event, CoachHours, CoachDetail, CoachPublic, EventPublic, CoachHoursPublic, CreateUserData
from datetime import timedelta, datetime
from jose import jwt, JWTError
from typing import Optional, Union
from db import get_database
from logger import coach_logger
from dotenv import load_dotenv
import os
from bson import ObjectId
# from Routes.admin_router import manager

from websocket_manager import manager

load_dotenv()

SECRET_KEY = "diddydoggy"
ALGS = ["HS256"]
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth_2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/signin")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

async def verify_admin(db, user_id: str):
    """
    Verifies if the user is an admin by checking the admin collection for the user_id and admin flag.
    """
    admin = await db.users.find_one({"user_id": ObjectId(user_id), "is_admin": True})
    return admin is not None

async def get_user(db, email: str):
    user = await db.users.find_one({"email": email})
    if user:
        user['id'] = str(user.pop('_id'))  # Rename '_id' to 'id' and convert ObjectId to str

        if user.get('type').lower() == 'coach':
            return Coach(**user)
        if user.get('type').lower() == 'admin':
            return User(**user)
    
async def authenticate_user(db, email: str, password: str):
    user = await get_user(db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    
        # Check if the user has been welcomed or if the status is 'inactive'
    if not user.welcomed or not user.isActive:
        # Update the user document in the database
        update_values = {}
        if not user.welcomed:
            update_values['welcomed'] = True
        if not user.isActive:
            update_values['isActive'] = True

        await db.users.update_one(
            {"_id": ObjectId(user.id)},
            {"$set": update_values}
        )

        # Update the user object
        user.welcomed = True
        user.isActive = True
        coach_logger.log_info(f"[+] User {user.email} loggin in boradcasting user_status_update")
        await manager.broadcast({"message": "user_status_update", "user_id": user.id, "welcomed": True, "isActive": True})
    return user

async def create_tokens(db, data: dict, access_expires_delta: Optional[timedelta] = None, refresh_expires_delta: Optional[timedelta] = None):
    coach_logger.log_info(f"[+] Creating tokens for user: {data.get('email')}")
    if access_expires_delta:
        access_expire = datetime.utcnow() + access_expires_delta
    else:
        access_expire = datetime.utcnow() + timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES')))
        # access_expire = datetime.utcnow() + timedelta(minutes=1)

    if refresh_expires_delta:
        refresh_expire = datetime.utcnow() + refresh_expires_delta
    else:
        refresh_expire = datetime.utcnow() + timedelta(days=int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS')))
        # refresh_expire = datetime.utcnow() + timedelta(minutes=2)

    access_data = data.copy()
    refresh_data = data.copy()


    access_data.update({"exp": access_expire})
    refresh_data.update({"exp": refresh_expire})

    try:
        access_token = jwt.encode(access_data, os.getenv('ACCESS_TOKEN_SECRET'), algorithm=ALGS[0])
        refresh_token = jwt.encode(refresh_data, os.getenv('REFRESH_TOKEN_SECRET'), algorithm=ALGS[0])
    except Exception as e:
        # Handle the exception (you can raise a custom exception or log the error)
        coach_logger.log_error(f"[-] An error occurred while encoding the token: {e}")
        print(f"An error occurred while encoding the token: {e}")
        return {}
    
    # Save the refresh token in the MongoDB database
    try:
        coach_logger.log_info(f"[+] Saving new refresh token: {refresh_token}")
        await db.tokens.insert_one({
            "user_id": data.get("user_id"),  # The user's email
            "refresh_token": refresh_token,
            "user_email": data.get("email"),
            "expires_at": refresh_expire
        })
    except Exception as e:
        # Handle the exception (you can raise a custom exception or log the error)
        coach_logger.log_error(f"[-] An error occurred while saving the refresh token: {e}")
        return {}
    
    return {"access_token": access_token, "refresh_token": refresh_token}

async def get_current_user(token: str = Depends(oauth_2_scheme), db = Depends(get_database)):
    cred_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})

    try:
        payload = jwt.decode(token, os.getenv('ACCESS_TOKEN_SECRET'), algorithms=ALGS)
        user_id: str = payload.get("user_id")
        email: str = payload.get("email")
        if email is None:
            coach_logger.log_error(f"[-] Could not validate credentials, email not found: {cred_exception}")
            raise cred_exception
        
        token_data = TokenData(user_id=user_id, email=email, exp=payload.get("exp"))
    except jwt.ExpiredSignatureError:
        coach_logger.log_error("[-] Token has expired")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired", headers={"X-Expired": "True"})
    except JWTError:
        print(token)
        coach_logger.log_error(f"[-] Could not validate credentials, JWTError: {cred_exception}")
        raise cred_exception
                                       

    user = await get_user(db, token_data.email)
    if user is None:
        coach_logger.log_error(f"[-] Could not validate credentials, user not found: {cred_exception}")
        raise cred_exception
    
    return user
    ...

async def get_current_user_manual(token: str, db):
    cred_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})

    try:
        payload = jwt.decode(token, os.getenv('ACCESS_TOKEN_SECRET'), algorithms=ALGS)
        user_id: str = payload.get("user_id")
        email: str = payload.get("email")
        if email is None:
            coach_logger.log_error(f"[-] Could not validate credentials, email not found: {cred_exception}")
            raise cred_exception
        
        token_data = TokenData(user_id=user_id, email=email, exp=payload.get("exp"))
    except jwt.ExpiredSignatureError:
        coach_logger.log_error("[-] Token has expired")
        return "TokenExpired"  # Custom signal to indicate expired token
    except JWTError:
        print(token)
        coach_logger.log_error(f"[-] Could not validate credentials, JWTError: {cred_exception}")
        return "InvalidToken"  # Custom signal for invalid token
        raise cred_exception
                                       

    user = await get_user(db, token_data.email)
    if user is None:
        coach_logger.log_error(f"[-] Could not validate credentials, user not found: {cred_exception}")
        raise cred_exception
    
    return user
    ...

async def get_current_active_user(current_user: Union[User, Coach] = Depends(get_current_user)):
    if current_user.disabled:
        coach_logger.log_error(f"[-] Could not validate credentials, user is disabled: {current_user.email}")
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
    
async def get_user_as_admin(db, user_id: str):
    """
    Retrieves the user document and checks if the user is marked as an admin.
    """
    admin_user = await db.users.find_one({"_id": ObjectId(user_id), "is_admin": True})
    if admin_user:
        # Turn _id to id and convert ObjectId to str
        admin_user['id'] = str(admin_user.pop('_id'))
        return Admin(**admin_user)  # Assuming that the Admin model is defined and it can take a MongoDB document as input
    return None

async def admin_dependency(user: User = Depends(get_current_user), db = Depends(get_database)):
    """
    Dependency function to be used in routes that require admin access.
    It verifies if the current user is an admin.
    """
    admin_user = await get_user_as_admin(db, user.id)
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have admin rights"
        )
    return admin_user

async def validate_admin_token(token: str, db) -> User:
    """
    Validate the access token and check if the user is an admin.

    Parameters:
    - token (str): The JWT access token.
    - db: The database session/connection.

    Returns:
    - User: The user object if valid and is an admin, otherwise None.
    """
    try:
        payload = jwt.decode(token, os.getenv('ACCESS_TOKEN_SECRET'), algorithms=ALGS)
        user_id: str = payload.get("user_id")
        email: str = payload.get("email")
        print(user_id)
        if user_id is None:
            return None
        admin_user = await get_user_as_admin(db, user_id)
        if admin_user and admin_user.is_admin:
            return admin_user
    except JWTError as e:
        print(e)
        return None

async def get_api_keys(db):
    # For example, fetching from the database:
    api_keys = await db.api_keys.find({}).to_list(length=100)
    return [key["api_key"] for key in api_keys]

# Dependency function to verify the API key
async def api_key_validator(api_key: str = Header(...), db = Depends(get_database)):
    # Fetch the valid API keys
    valid_api_keys = await get_api_keys(db)
    
    # Check if the provided API key is in the list of valid keys
    if api_key not in valid_api_keys:
        coach_logger.log_error("[-] Invalid API key provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

    # If the check passes, you could return the API key or another relevant piece of information
    coach_logger.log_info("[+] API key is valid")
    return api_key