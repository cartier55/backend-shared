import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

client = WebClient(token=os.environ["APP_OAUTH"])

def update_slack(msg):
    client.chat_postMessage(channel='coachify', text=msg)
    

def upload_file(filename, file_path):
    response = client.files_upload(
        channels='#general',
        file=file_path,
        title=filename,
        initial_comment="Here is the Parts File you requested."
    )
    if response["ok"]:
        print("File uploaded successfully")
    else:
        print(f"File upload failed: {response['error']}")
    ...