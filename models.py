from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict
from datetime import datetime
import os

class User(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str = Field(..., unique=True)
    type: str
    hashed_password: str
    image_url: Optional[str] = None
    welcomed: bool = False  # New field to indicate if the user has been welcomed
    isActive: bool = False  # New field to indicate the user status, defaulting to "inactive"
    last_request_at: Optional[datetime] = None
    is_admin: bool = False


class Admin(User):
    disabled: bool = False
    is_admin: bool = True

class UserDataPublic(BaseModel):
    first_name: str
    last_name: str
    email: str
    image_url: Optional[str] = None
    is_admin: Optional[bool] = None

class UpdateUserData(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    image_url: Optional[str] = None
    is_admin: Optional[bool] = None

    @property
    def formatted_image_url(self) -> Optional[str]:
        return os.path.basename(self.image_url) if self.image_url else None


class CreateUserData(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    type: str

# Model to represent a coach, inheriting from User
class Coach(User):
    disabled: bool = False
    specialization: Optional[str] = None  # e.g., "CrossFit", "Weightlifting", "Cardio"
    is_admin: bool = False

# Model to represent an event
class Event(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    pay_period: int
    coach_id: str  # Foreign key to the Coach model

class NewEmptyEventData(BaseModel):
    start: datetime
    event_type: str
    duration: int
    reoccurring: bool = False


# Model to represent coach hours
class CoachHours(BaseModel):
    coach_id: str  # Foreign key to the Coach model
    total_hours: Optional[float] = None  # Calculated based on classes or events taught

# Model to represent a coach with their classes and hours
class CoachDetail(Coach):
    events: Optional[List[Event]] = None  # List of events the coach is responsible for
    hours: CoachHours

class CoachPublic(BaseModel):
    id: str  # Primary object ID for MongoDB
    first_name: str
    last_name: str
    email: str
    specialization: Optional[str] = None

class CoachInAdmin(User):
    welcomed: bool
    isActive: bool

    class Config:
        from_attributes = True

# Model to represent an event for public-facing API
class EventPublic(BaseModel):
    id: str  # Primary object ID for MongoDB
    title: str
    start: datetime
    end: datetime
    pay_period: int

class EventCreateUpdateData(BaseModel):
    editedValue: str
    date: str
    weekday: str
    startTime: str
    payPeriod: int = 1  # Default value of 1 for payPeriod

# Model to represent coach hours for public-facing API
class CoachHoursPublic(BaseModel):
    total_hours: float

class CommentBase(BaseModel):
    text: str

class CommentCreate(CommentBase):
    pass

class CommentInDB(CommentBase):
    id: str  # MongoDB's default id field is '_id'
    coach_id: str
    date: datetime

class Comment(CommentInDB):
    pass

class CommentPublic(BaseModel):
    id: str
    text: str
    coach: CoachPublic
    date: datetime

class FeatureRequestBase(BaseModel):
    title: str
    body: str

class FeatureRequestCreate(FeatureRequestBase):
    pass

class FeatureRequestModel(FeatureRequestBase):
    coach_id: str

class FeatureRequestInDB(FeatureRequestModel):
    id: str

# Model to represent JWT tokens
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenPublic(BaseModel):
    user: UserDataPublic
    access_token: str
    token_type: str

# Model to represent the payload data in JWT tokens
class TokenData(BaseModel):
    user_id: str
    email: str
    exp: datetime

# Model for incoming authentication data
class AuthDetails(BaseModel):
    username: str
    password: str

class DailyProgrammingMaterials(BaseModel):
    week_number: int
    pdf_link: HttpUrl
    daily_video_links: Dict[str, HttpUrl]

    class Config:
        json_schema_extra = {
            "example": {
                "week_number": 42,
                "pdf_link": "https://example.com/weekly_materials.pdf",
                "daily_video_links": {
                    "monday": "https://youtu.be/monday_video",
                    "tuesday": "https://youtu.be/tuesday_video",
                    "wednesday": "https://youtu.be/wednesday_video",
                    "thursday": "https://youtu.be/thursday_video",
                    "friday": "https://youtu.be/friday_video",
                    "saturday": "https://youtu.be/saturday_video",
                },
            }
        }

class ProgrammingUpdateRequest(BaseModel):
    weeknumber: int
    pdf_link: HttpUrl
    website_links: List[HttpUrl]

    class Config:
        json_schema_extra = {
            "example": {
                "pdf_link": "https://example.com/new_weekly_materials.pdf",
                "website_links": [
                    "http://example.com/link_to_video1",
                    "http://example.com/link_to_video2",
                    "http://example.com/link_to_video3",
                    "http://example.com/link_to_video4",
                    "http://example.com/link_to_video5",
                ],
            }
        }