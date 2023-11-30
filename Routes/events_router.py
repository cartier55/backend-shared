from auth import authenticate_user, verify_password, create_tokens, get_current_user, get_user, get_password_hash
from bson import ObjectId
from typing import List, Dict
from Functions.event_creator import create_events_with_duration
from Functions.schedule_cleaner import CFClassesDataCleaner
from fastapi import Depends, HTTPException, status, Query, APIRouter
from models import User, Token, TokenData, Coach, Event, CoachHours, CoachDetail, CoachPublic, EventPublic, CoachHoursPublic, CreateUserData, EventCreateUpdateData, NewEmptyEventData
from auth import authenticate_user, verify_password, create_tokens, get_current_user, get_user, get_password_hash
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from db import get_database
from logger import coach_logger
from datetime import timedelta, time, datetime, timezone
import pytz
from dateutil.parser import parse  # Import this for parsing string to datetime
from dotenv import load_dotenv
import os
from pandas import pandas as pd
from pprint import pprint as pp
from dateutil import parser

events_router = APIRouter()

INPUT_FILE_PATH = r'C:/Users/carte/OneDrive/Documents/Code/Coach Box/backend/Data/OG_Schedule.xlsx'
PRESERVED_OUTPUT_FILE_PATH = r'C:/Users/carte/OneDrive/Documents/Code/Coach Box/backend/Data/Output/Date_Preserved.xlsx'
CLEANED_OUTPUT_FILE_PATH = r'C:/Users/carte/OneDrive/Documents/Code/Coach Box/backend/Data/Output/Cleaned_Schedule.xlsx'

@events_router.get("/create-events")
async def create_events(db=Depends(get_database)):
    if db is None:
        coach_logger.log_error("[-] Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    else:
        cleaner = CFClassesDataCleaner(INPUT_FILE_PATH, PRESERVED_OUTPUT_FILE_PATH)
        cleaner.preserve_dates()
        cleaner.load_data()
        cleaner.set_date_as_header()
        df = cleaner.get_cf_classes_df_partial()
        df.to_excel('output_df_test.xlsx', index=False)
        events = create_events_with_duration(df)

        # Assuming you have a collection named 'events' and 'coaches'
        events_collection = db.get_collection("events")
        users_collection = db.get_collection("users")

        coach_logger.log_warning(f"[!] Deleting all existing events")
        await events_collection.delete_many({})  # Delete all existing events

        inserted_count = 0
        for event in events:
            # Find the coach whose first_name matches the event title
            coach = await users_collection.find_one({"first_name": {"$regex": f"^{event['title']}$", "$options": "i"}, "type": "coach"})
            if coach:
                # Add the coach_id to the event
                event["coach_id"] = str(coach["_id"])

                # Insert the event into the database
                result = await events_collection.insert_one(event)
                inserted_count += 1
                # Convert ObjectId to str for JSON serialization
                event["_id"] = str(result.inserted_id)
            else:
                coach_logger.log_warning(f"[-] No coach found with first_name matching event title: {event['title']}")
        coach_logger.log_info(f"[+] Inserted {inserted_count} events into the database")
        return {"inserted_count": inserted_count, "events": events}

def convert_objectid(data):
    if isinstance(data, list):
        for item in data:
            convert_objectid(item)
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, ObjectId):
                data[key] = str(value)
            convert_objectid(value)

@events_router.get("/events-for-month", response_model=List[dict])
async def get_events_for_month(month: int = Query(..., alias="month", ge=1, le=12), year: int = Query(..., alias="year"), db=Depends(get_database)):
    if db is None:
        coach_logger.log_error("[-] Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    coach_logger.log_info(f"[+] Fetching events for month: {month} and year: {year}")
    events_collection = db.get_collection("events")
    
    # Generate start and end ISO formatted strings for the given month and year
    start_date = datetime(year, month, 1).isoformat() + "T00:00:00"
    if month == 12:
        end_date = datetime(year + 1, 1, 1).isoformat() + "T00:00:00"  # For December, set to January 1st of the next year
    else:
        end_date = datetime(year, month + 1, 1).isoformat() + "T00:00:00"  # Set to the 1st of the next month
    
    # MongoDB query to get events in the date range
    query = {'start': {'$gte': start_date, '$lt': end_date}}
    
    # Fetch events from the database
    filtered_events = await events_collection.find(query).to_list(length=10000)  # Increase the limit appropriately

    # Convert ObjectIDs to strings
    convert_objectid(filtered_events)
    
    return filtered_events

# Utility function to get coach events
async def fetch_coach_events(current_user: Coach, db):
    coach_logger.log_info(f"[+] Fetching events for coach: {current_user.first_name} {current_user.last_name}")
    coach_logger.log_info(f"[+] Coach ID: {current_user.id}")
    events_collection = db.get_collection("events")
    query = {'coach_id': current_user.id}
    coach_events = await events_collection.find(query).to_list(length=10000)
    coach_logger.log_info(f"[+] Found {len(coach_events)} events for coach")
    convert_objectid(coach_events)
    return coach_events

# Wrapper function to use as a dependency
async def get_coach_events_wrapper(current_user: Coach = Depends(get_current_user), db=Depends(get_database)):
    return await fetch_coach_events(current_user, db)

@events_router.get("/events-for-coach", response_model=List[dict])
async def get_coach_events(current_user: Coach = Depends(get_current_user), db=Depends(get_database)):
    return await fetch_coach_events(current_user, db)

# Utility function to get the start and end of the current week
def get_current_week():
    today = datetime.utcnow()
    start_of_week_date = today - timedelta(days=today.weekday())
    end_of_week_date = start_of_week_date + timedelta(days=6)
    
    # Set the time to 4 AM for the start of the week
    start_of_week = datetime.combine(start_of_week_date.date(), time(4, 0))
    
    # Set the time to 10 PM for the end of the week
    end_of_week = datetime.combine(end_of_week_date.date(), time(22, 0))
    
    return start_of_week, end_of_week

@events_router.get("/weekly-hours", response_model=dict)
async def get_weekly_hours(current_user: Coach = Depends(get_current_user), coach_events: List[dict] = Depends(get_coach_events_wrapper)):
    start_of_week, end_of_week = get_current_week()
    print(start_of_week, end_of_week)
    # Filter events that fall within the current week
    weekly_events = [event for event in coach_events if start_of_week <= parse(event['start']) <= end_of_week]
    pp(weekly_events)
    # Calculate the number of hours worked
    hours_worked = len(weekly_events)  # Assuming each event is 1 hour long
    
    return {"hours_worked": hours_worked}


@events_router.get('/events-in-range', response_model=List[EventPublic])
async def get_events_in_range(start_date: str = Query(..., format="%m/%d/%Y"), end_date: str = Query(..., format="%m/%d/%Y"), current_user=Depends(get_current_user), db=Depends(get_database)):
    # Convert the start_date and end_date to datetime objects
    # print(current_user)
    try:
        start_date_dt = datetime.strptime(start_date, "%m/%d/%Y")
        end_date_dt = datetime.strptime(end_date, "%m/%d/%Y")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use MM/dd/yyyy.")

    # Set the time for start_date to 4 AM and end_date to 10 PM
    # start_date_dt = datetime.combine(start_date_dt.date(), time(4, 0))
    # end_date_dt = datetime.combine(end_date_dt.date(), time(22, 0))

    # Convert to ISO format and set the time
    start_date_iso = start_date_dt.replace(hour=4, minute=0, second=0).isoformat() + "Z"
    end_date_iso = end_date_dt.replace(hour=22, minute=0, second=0).isoformat() + "Z"

    # MongoDB query
    query = {
        "start": {
            "$gte": start_date_iso,
            "$lte": end_date_iso
        },
        "coach_id": current_user.id
    }

    # print(query)
    # Fetch events from MongoDB for the current user
    events_collection = db.get_collection("events")
    events = await events_collection.find(query).to_list(length=10000)
    # Convert ObjectId to str for JSON serialization
    for event in events:
        event["id"] = str(event.get("_id", ""))
        EventPublic(**event)
    

    return events

# @events_router.get('/next-event', response_model=EventPublic)
@events_router.get('/next-event')
async def get_next_event(current_user: Coach = Depends(get_current_user), db=Depends(get_database)):
    # current_time = datetime.utcnow()
    eastern_tz = pytz.timezone('US/Eastern')
    current_time = datetime.now(eastern_tz)
    # current_time = datetime(2023, 10, 20, tzinfo=timezone.utc)    
    # print(current_time)
    # print(current_time.isoformat())
    event_collection = db["events"]
    
     # Find the next 3 upcoming events for the current user
    cursor = event_collection.find(
        {"coach_id": current_user.id, "start": {"$gte": current_time.isoformat() + "Z"}},
        sort=[("start", 1)]
    ).limit(3)

    events = await cursor.to_list(length=3)

    if not events:
        raise HTTPException(status_code=404, detail="No upcoming events found")

    for event in events:
        if "_id" in event and isinstance(event["_id"], ObjectId):
            event["_id"] = str(event["_id"])

    return events
    ...

@events_router.post("/create-events", response_model=dict)
async def create_or_update_event(event_data: EventCreateUpdateData, db=Depends(get_database)):
    if db is None:
        coach_logger.log_error("[-] Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")

    # Assuming you have a collection named 'events' and 'users'
    events_collection = db.get_collection("events")
    users_collection = db.get_collection("users")

    # Find the coach in the users collection based on the "editedValue"
    coach = await users_collection.find_one({"first_name": event_data.editedValue, "type": "coach"})

    if coach:
        # Calculate the end time as one hour after the start time
        start_time = datetime.fromisoformat(event_data.startTime)
        end_time = start_time + timedelta(hours=1)

        # Create or update the event
        event = {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),  # Set the end time one hour after start time
            "title": event_data.editedValue,
            "pay_period": event_data.payPeriod,  # Use the provided payPeriod or default to 1
            "coach_id": str(coach["_id"])
        }

        # Check if an event with the same start time already exists
        existing_event = await events_collection.find_one({"start": event_data.startTime})

        if existing_event:
            # Update the existing event
            await events_collection.update_one({"_id": existing_event["_id"]}, {"$set": event})
            event["_id"] = str(existing_event["_id"])
            return {"message": "Event updated successfully.", "event": event}
        else:
            # Insert the new event into the database
            result = await events_collection.insert_one(event)
            event["_id"] = str(result.inserted_id)
            return {"message": "Event created successfully.", "event": event}
    else:
        # TODO - Send slack message to alert admin
        return {"message": "No coach found with first_name matching 'editedValue'."}

@events_router.post("/create-empty-event", response_model=dict)
async def create_new_empty_event(event_data: NewEmptyEventData, db=Depends(get_database)):
    if db is None:
        coach_logger.log_error("[-] Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    else:
        # Assuming you have a collection named 'events' and 'coaches'
        events_collection = db.get_collection("events")
        users_collection = db.get_collection("users")
        time_slots_collection = db.get_collection("reoccurring_time_slots")

        # Find the coach in the users collection based on the "editedValue"
        print(type(event_data.start))
        start_time = datetime.fromisoformat(event_data.start.isoformat())
        formatted_start_time = start_time.strftime("%Y-%m-%dT%H:%M:00")
        # Calculate the end time based on the duration
        # start_time = datetime.fromisoformat(event_data.start.isoformat())
        end_time = start_time + timedelta(minutes=event_data.duration)
        formatted_end_time = end_time.strftime("%Y-%m-%dT%H:%M:00")

        # Create the event
        event = {
            "start": formatted_start_time,
            "end": formatted_end_time,  # Set the end time one hour after start time
            "title": '',
            "pay_period": 555,  # Use the provided payPeriod or default to 1
            # "coach_id": str(coach["_id"])
        }

        # Check if an event with the same start time already exists
        existing_event = await events_collection.find_one({"start": event_data.start.isoformat()})

        if existing_event:
            # Raise exception that the evnet already exists
            raise HTTPException(status_code=400, detail="Event already exists.")
        
        # Insert the new event into the database
        result = await events_collection.insert_one(event)
        event["_id"] = str(result.inserted_id)
        return {"message": "Event created successfully.", "event": event}
        # else:
        #     # TODO - Send slack message to alert admin
            # return {"message": "No coach found with first_name matching 'editedValue'."}
# async def get_events_in_range(start_date: str = Query(..., format="%m/%d/%Y"), end_date: str = Query(..., format="%m/%d/%Y"), current_user=Depends(get_current_user), db=Depends(get_database)):

@events_router.get("/get-time-slots")
async def get_claimed_and_unclaimed_events(current_date, day_count, current_user=Depends(get_current_user), db=Depends(get_database)):
    if db is None:
        coach_logger.log_error("[-] Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    else:
        # Assuming you have a collection named 'events' and 'coaches'
        events_collection = db.get_collection("events")
        users_collection = db.get_collection("users")
        time_slots_collection = db.get_collection("reoccurring _time_slots")
        
        schedule_maker_events = []
        
        # Convert string date to datetime object
        print(type(current_date))
        current_date = parser.parse(current_date)
        # Convert current_date to datetime object
        current_date = datetime.fromisoformat(current_date.isoformat())

        print(type(current_date))
        # Create a list of 5 date objs for the next 5 days
        today_plus_days = [current_date + timedelta(days=i) for i in range(int(day_count))]

        # Get all events for the current date day of the week
        for day in today_plus_days:
            weekday = day.strftime("%A")
            print(weekday)
            # Get all events for the current date
            start_of_day = day.replace(hour=0, minute=0, second=0)
            end_of_day = day.replace(hour=23, minute=59, second=59)
            print(start_of_day, end_of_day)
        
            # Find all event objs from the events collection that are for the current date in the day variable
            query = {
                "start": {
                    "$gte": start_of_day.isoformat(),
                    "$lte": end_of_day.isoformat()
                },
            }
            # Fetch events from MongoDB
            day_events = await events_collection.find(query).to_list(length=10000)

            day_claimed_event_times = []

            # Get all the times for each event in the this days events list then format the time to be hh:mm AM/PM
            for event in day_events:
                print('These are the times that will be compared against recurring time slots')
                print(event['start'])
                # TO find which reoccurring time slots are not clamied by a user already so we can gen emtpy event to send to the frontend
                coach_logger.log_info(f"[+] Event start time: {datetime.fromisoformat(event['start']).strftime('%I:%M %p')}")
                day_claimed_event_times.append(datetime.fromisoformat(event['start']).strftime("%I:%M %p"))
                schedule_maker_events.append(event)
                # event["start"] = datetime.fromisoformat(event["start"]).strftime("%I:%M %p")
                # event["end"] = datetime.fromisoformat(event["end"]).strftime("%I:%M %p")

            # Find which event times from the day_events list is not in the time_slots array of the one obj in the reoccurring_time_slots collection
            time_slots = await time_slots_collection.find_one({"_id": ObjectId("6565e8281698673a91df0941")})
            print(time_slots)

            # Find which event times from the day_claimed_event_times list is not int the time_slots list
            unclaimed_times = [time for time in time_slots["time_slots"] if time not in day_claimed_event_times] # This is a list of reoccuring times that are not claimed by a user
            print(unclaimed_times)

            
            for time in unclaimed_times:
                # combine the current date from the day variable with the time from the unclaimed_times list to create a datetime obj
                # print(day)
                # print(time)
                # print(datetime.strptime(time, "%I:%M %p").hour)
                # print(datetime.strptime(time, "%I:%M %p").minute)


                # Create the event
                        # formatted_end_time = end_time.strftime("%Y-%m-%dT%H:%M:00")

                formatted_start_time = day.replace(hour=datetime.strptime(time, "%I:%M %p").hour, minute=datetime.strptime(time, "%I:%M %p").minute).strftime("%Y-%m-%dT%H:%M:00")
                event = {
                    "start": formatted_start_time,
                    "end": day.replace(hour=datetime.strptime(time, "%I:%M %p").hour, minute=datetime.strptime(time, "%I:%M %p").minute).isoformat(),  # Set the end time one hour after start time
                    "title": '',
                    "pay_period": 555,  # Use the provided payPeriod or default to 1
                    # "coach_id": str(coach["_id"])
                }
                schedule_maker_events.append(event)

        print(schedule_maker_events)
        for evt in schedule_maker_events:
            if "_id" in evt and isinstance(evt["_id"], ObjectId):
                evt["_id"] = str(evt["_id"])
        
        # schedule_maker_events[-1] = len(schedule_maker_events)
        return schedule_maker_events




            # Check if an event with the same start time already exists
            # existing_event = await events_collection.find_one({"start": event["start"]})

            # if existing_event:
            #     # Raise exception that the evnet already exists
            #     raise HTTPException(status_code=400, detail="Event already exists.")
            
            # Insert the new event into the database
            # result = await events_collection.insert_one(event)
            # event["_id"] = str(result.inserted_id)
            # return {"message": "Event created successfully.", "event": event}



       
        

        # Find the coach in the users collection based on the "editedValue"
        coaches = await users_collection.find({"type": "coach"}).to_list(length=10000)
        coaches_dict = {}
        for coach in coaches:
            coaches_dict[coach["first_name"]] = {"id": str(coach["_id"]), "events": []}
        
        # Find all events
        events = await events_collection.find({}).to_list(length=10000)
        for event in events:
            event["id"] = str(event["_id"])
            if event["title"] in coaches_dict:
                coaches_dict[event["title"]]["events"].append(event)
            else:
                coaches_dict[event["title"]] = {"id": "", "events": [event]}
        
        return coaches_dict