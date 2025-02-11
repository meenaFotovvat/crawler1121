import logging
import os
import base64
from fastapi import FastAPI, HTTPException
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.messages import GetHistoryRequest
from dotenv import load_dotenv
from cryptography.fernet import Fernet

logging.basicConfig(level=logging.INFO)
load_dotenv()  # بارگذاری متغیرهای محیطی

app = FastAPI()

port = int(os.environ.get("PORT", 8080))

app.run(host="0.0.0.0", port=port)

@app.get("/")
async def read_root():
    return {"message": "App is working securely"}

# دریافت متغیرهای محیطی
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
BOT_TOKEN = os.getenv("BOT_TOKEN")  # در صورت استفاده از توکن بات (اختیاری)

# دریافت متغیرهای محیطی مربوط به session رمزگذاری‌شده و کلید رمزنگاری
ENCRYPTED_SESSION_ENV = os.getenv("ENCRYPTED_SESSION")  # مقدار Base64 شده‌ی session رمزگذاری‌شده
ENCRYPTION_KEY_ENV = os.getenv("ENCRYPTION_KEY")         # کلید رمزنگاری به صورت رشته

# مسیر فایل session plaintext
SESSION_FILE_NAME = "bookNook_session.session"

# بررسی و تهیه کلید رمزنگاری
if ENCRYPTION_KEY_ENV is None:
    raise Exception("ENCRYPTION_KEY در متغیرهای محیطی تنظیم نشده است.")
encryption_key = ENCRYPTION_KEY_ENV.encode()  # فرض می‌کنیم به صورت رشته ذخیره شده است
cipher = Fernet(encryption_key)

# اگر متغیر ENCRYPTED_SESSION موجود باشد، آن را رمزگشایی کرده و به صورت فایل session ذخیره می‌کنیم
if ENCRYPTED_SESSION_ENV:
    try:
        encrypted_session = base64.b64decode(ENCRYPTED_SESSION_ENV)
        decrypted_session = cipher.decrypt(encrypted_session)
        with open(SESSION_FILE_NAME, "wb") as session_file:
            session_file.write(decrypted_session)
        logging.info("فایل session از متغیر ENCRYPTED_SESSION رمزگشایی و ذخیره شد.")
    except Exception as e:
        logging.error("خطا در رمزگشایی فایل session: " + str(e))
        # در صورت بروز خطا، فایل session به صورت جدید ایجاد خواهد شد.
else:
    logging.info("متغیر ENCRYPTED_SESSION یافت نشد؛ یک session جدید ایجاد خواهد شد.")

# راه‌اندازی کلاینت تلگرام با استفاده از فایل session (یا ایجاد session جدید در صورت عدم وجود)
client = TelegramClient(SESSION_FILE_NAME, API_ID, API_HASH)

async def scrape_telegram_channels(channels):
    all_data = {}
    for channel in channels:
        try:
            logging.info(f"دریافت entity برای کانال: {channel}")
            channel_entity = await client.get_entity(channel)

            logging.info(f"دریافت تاریخچه پیام‌ها برای کانال: {channel}")
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
            logging.info(f"عملیات استخراج برای کانال {channel} به اتمام رسید.")

        except Exception as e:
            logging.error(f"خطا در استخراج کانال {channel}: {e}")
            raise HTTPException(status_code=500, detail=f"Error scraping channel {channel}: {e}")

    return all_data

@app.get("/fetch_telegram_data")
async def fetch_telegram_data():
    channels = ['@chiiro', '@Tajrobeh_home', '@Khaneh_Agahi1', '@yarroshd']
    
    try:
        # شروع کردن کلاینت (برای لاگین، اگر session موجود نباشد، جدید ایجاد می‌شود)
        await client.start(PHONE_NUMBER)
        
        if await client.is_user_authorized():
            data = await scrape_telegram_channels(channels)
            await client.disconnect()

            # پس از اتمام کار، فایل session را رمزگذاری کرده و به صورت Base64 دریافت می‌کنیم
            with open(SESSION_FILE_NAME, "rb") as session_file:
                session_data = session_file.read()
            encrypted_session = cipher.encrypt(session_data)
            encrypted_session_b64 = base64.b64encode(encrypted_session).decode()
            logging.info("مقدار جدید ENCRYPTED_SESSION (Base64): " + encrypted_session_b64)
            
            # حذف فایل session plaintext جهت امنیت
            os.remove(SESSION_FILE_NAME)

            return data
        else:
            await client.disconnect()
            raise HTTPException(status_code=401, detail="دسترسی به Telegram API مجاز نیست.")
    
    except SessionPasswordNeededError:
        await client.disconnect()
        raise HTTPException(status_code=403, detail="احراز هویت دو مرحله‌ای مورد نیاز است.")
    except Exception as e:
        logging.error(f"خطا در fetch_telegram_data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch telegram data.")
