import logging 
import os
from fastapi import FastAPI, HTTPException
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.messages import GetHistoryRequest
from dotenv import load_dotenv
from cryptography.fernet import Fernet

logging.basicConfig(level=logging.INFO)

# بارگذاری متغیرهای محیطی
load_dotenv()

# اطمینان از وجود دایرکتوری data
DATA_DIR = "./data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "App is working securely"}

# دریافت متغیرهای محیطی
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")

# مسیر ذخیره session
SESSION_FILE_PATH = os.path.join(DATA_DIR, "bookNook_session.session.enc")
KEY_FILE_PATH = os.path.join(DATA_DIR, "encryption_key.key")

# ایجاد کلید رمزگذاری (در اولین اجرا)
if not os.path.exists(KEY_FILE_PATH):
    key = Fernet.generate_key()
    with open(KEY_FILE_PATH, "wb") as key_file:
        key_file.write(key)
else:
    with open(KEY_FILE_PATH, "rb") as key_file:
        key = key_file.read()

cipher = Fernet(key)

# بررسی وجود session رمزگذاری‌شده
if os.path.exists(SESSION_FILE_PATH):
    with open(SESSION_FILE_PATH, "rb") as enc_file:
        decrypted_session = cipher.decrypt(enc_file.read())
    with open("bookNook_session.session", "wb") as session_file:
        session_file.write(decrypted_session)

# راه‌اندازی کلاینت Telethon با session امن
client = TelegramClient("bookNook_session", API_ID, API_HASH)

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
        await client.start(PHONE_NUMBER)
        
        if await client.is_user_authorized():
            data = await scrape_telegram_channels(channels)
            await client.disconnect()

            # ذخیره‌سازی session به‌صورت رمزگذاری‌شده
            with open("bookNook_session.session", "rb") as session_file:
                encrypted_session = cipher.encrypt(session_file.read())
            with open(SESSION_FILE_PATH, "wb") as enc_file:
                enc_file.write(encrypted_session)

            # حذف فایل session اصلی پس از رمزگذاری
            os.remove("bookNook_session.session")

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
