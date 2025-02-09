import json
import logging
from fastapi import FastAPI, HTTPException
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.messages import GetHistoryRequest
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO)

load_dotenv()  # Load environment variables from .env file

app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "App is working"}

# Access environment variables
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
phone_number = os.getenv("PHONE_NUMBER")

# Initialize the Telethon client with a session file
client = TelegramClient('bookNook_session', API_ID, API_HASH)

# Define the Telegram scraping function
async def scrape_telegram_channels(channels):
    all_data = {}
    for channel in channels:
        try:
            logging.info(f"Fetching entity for channel: {channel}")
            channel_entity = await client.get_entity(channel)

            logging.info(f"Fetching message history for channel: {channel}")
            messages = await client(GetHistoryRequest(
                peer=channel_entity,
                offset_id=0,
                offset_date=None,
                add_offset=0,
                limit=50,
                max_id=0,
                min_id=0,
                hash=0
            ))

            data = []
            for message in messages.messages:
                data.append({
                    'message_id': message.id,
                    'text': message.message,
                    'date': str(message.date),
                    'sender_id': message.from_id.user_id if message.from_id else None
                })

            all_data[channel] = data
            logging.info(f"Scraping completed for channel: {channel}")

        except Exception as e:
            logging.error(f"Failed to scrape channel {channel}: {e}")
            raise HTTPException(status_code=500, detail=f"Error scraping channel {channel}: {e}")

    return all_data

@app.get("/fetch_telegram_data")
async def fetch_telegram_data():
    channels = ['@chiiro', '@Tajrobeh_home', '@Khaneh_Agahi1' , '@yarroshd']
    
    try:
        await client.start(phone_number)
        
        if await client.is_user_authorized():
            data = await scrape_telegram_channels(channels)
            await client.disconnect()
            return data
        else:
            await client.disconnect()
            raise HTTPException(status_code=401, detail="Unauthorized access to Telegram API.")
    
    except SessionPasswordNeededError:
        await client.disconnect()
        raise HTTPException(status_code=403, detail="Two-factor authentication is required for this account.")
    except Exception as e:
        logging.error(f"Error in fetch_telegram_data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch telegram data.")