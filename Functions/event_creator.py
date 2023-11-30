from pandas import pandas as pd
from datetime import datetime, timedelta
from pprint import pprint as pp
from logger import coach_logger  # Assuming you have a logger module

def create_events_with_duration(df):
    coach_logger.log_info("[+] Creating events...")
    events = []
    
    first_event_date = None  # To keep track of the first event's start date
    pay_period = 1  # Initialize pay_period

    # Loop through each column
    for col in df.columns:
        # Skip unwanted columns
        if "Week_Separator" in col or col == 'Unnamed: 2':
            continue
        
        # Loop through each row in the column
        for index, row in df.iterrows():
            time_slot = row['Unnamed: 2']
            value = row[col]
            
            # Skip rows with special time slots or missing values
            if pd.isna(value) or pd.isna(time_slot) or time_slot in ['Open Gym', 'BBC/Other', 'NOTE:']:
                continue
            
            # Construct the start and end datetime objects
            date_str = col
            time_str = time_slot
            datetime_str = f"{date_str} {time_str}"
            
            start_datetime = datetime.strptime(datetime_str, '%m/%d/%Y %H:%M:%S')
            
            # Record the first event's start date if not set
            if first_event_date is None:
                first_event_date = start_datetime.date()
            
            # Check if two weeks have passed since the first event's start date
            days_passed = (start_datetime.date() - first_event_date).days
            if days_passed >= 14:
                first_event_date = start_datetime.date()  # Reset the first_event_date
                pay_period += 1  # Increment pay_period
            
            # Convert start_datetime to ISO 8601 strings
            start_datetime_str = start_datetime.isoformat()
            
            # Set the end time to be 1 hour ahead of the start time
            end_datetime = start_datetime + timedelta(hours=1)
            
            # Convert end_datetime to ISO 8601 strings
            end_datetime_str = end_datetime.isoformat()
            
            # Create the event with the pay_period field
            event = {
                'start': start_datetime_str,
                'end': end_datetime_str,
                'title': value,
                'pay_period': pay_period
            }
            events.append(event)
    
    coach_logger.log_info(f"[+] Created {len(events)} events")
    return events

# Uncomment below to test
# path = 'Cleaned_Schedule_a.xlsx'
# df = pd.read_excel(path, sheet_name='Sheet1')
# events_with_single_coach = create_events_with_duration(df)
# pp(events_with_single_coach)