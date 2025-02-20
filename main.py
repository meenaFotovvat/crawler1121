import logging
import os
import base64
import gzip
from fastapi import FastAPI, HTTPException
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.messages import GetHistoryRequest
from dotenv import load_dotenv
from cryptography.fernet import Fernet

logging.basicConfig(level=logging.INFO)
load_dotenv()  # بارگذاری متغیرهای محیطی

app = FastAPI()

# نمایش مسیر جاری
current_path = os.getcwd()
logging.info(f"📂 مسیر جاری اجرای برنامه: {current_path}")

try:
    test_file = os.path.join(current_path, "test_write_permission.txt")
    with open(test_file, "w") as f:
        f.write("Test write permissions")
    os.remove(test_file)
    logging.info("✅ مسیر ذخیره‌سازی قابل نوشتن است.")
except Exception as e:
    logging.error(f"❌ مشکل در نوشتن فایل در مسیر جاری: {e}")

@app.get("/")
async def read_root():
    return {"message": "App is working securely"}

# دریافت متغیرهای محیطی
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")

# دریافت مقدار `ENCRYPTED_SESSION`
ENCRYPTED_SESSION_B64 = os.getenv("ENCRYPTED_SESSION")
ENCRYPTION_KEY_ENV = os.getenv("ENCRYPTION_KEY")

SESSION_FILE_NAME = "bookNook_session.session"

if not ENCRYPTION_KEY_ENV:
    raise Exception("متغیر ENCRYPTION_KEY در محیط تنظیم نشده است.")
encryption_key = ENCRYPTION_KEY_ENV.encode()
cipher = Fernet(encryption_key)

# تابع فشرده‌سازی داده
def compress_data(data: bytes) -> bytes:
    return gzip.compress(data)

# تابع باز کردن فشرده‌سازی
def decompress_data(data: bytes) -> bytes:
    return gzip.decompress(data)

# رمزگشایی مقدار `ENCRYPTED_SESSION`
if ENCRYPTED_SESSION_B64:
    try:
        encrypted_session = base64.b64decode(ENCRYPTED_SESSION_B64)
        decrypted_compressed_session = cipher.decrypt(encrypted_session)
        decrypted_session = decompress_data(decrypted_compressed_session)
 
        with open(SESSION_FILE_NAME, "wb") as session_file:
            session_file.write(decrypted_session)

        # بررسی وجود فایل session پس از ذخیره
        session_path = os.path.abspath(SESSION_FILE_NAME)
        if os.path.exists(session_path):
            logging.info(f"✅ فایل session در مسیر ذخیره شد: {session_path}")
        else:
            logging.error("❌ فایل session پس از ذخیره‌سازی یافت نشد!")

    except Exception as e:
        logging.error("❌ خطا در رمزگشایی فایل session: " + str(e))

# راه‌اندازی کلاینت تلگرام
client = TelegramClient(SESSION_FILE_NAME, API_ID, API_HASH)

async def scrape_telegram_channels(channels):
    all_data = {}
    for channel in channels:
        try:
            logging.info(f"📌 در حال دریافت اطلاعات از کانال: {channel}")
            channel_entity = await client.get_entity(channel)
            messages = await client(GetHistoryRequest(
                peer=channel_entity, offset_id=0, offset_date=None, 
                add_offset=0, limit=50, max_id=0, min_id=0, hash=0
            ))

            data = [{
                'message_id': message.id, 'text': message.message,
                'date': str(message.date),
                'sender_id': message.from_id.user_id if message.from_id else None
            } for message in messages.messages]

            all_data[channel] = data
            logging.info(f"✅ داده‌های کانال {channel} دریافت شد.")

        except Exception as e:
            logging.error(f"❌ خطا در دریافت اطلاعات از کانال {channel}: {e}")
            raise HTTPException(status_code=500, detail=f"Error scraping channel {channel}: {e}")

    return all_data

@app.get("/fetch_telegram_data")
async def fetch_telegram_data():
    channels = ['@chiiro', '@Tajrobeh_home', '@Khaneh_Agahi1', '@yarroshd']
    
    try:
        await client.start(PHONE_NUMBER)
        if await client.is_user_authorized():
            data = await scrape_telegram_channels(channels)
            await client.disconnect()

            # فشرده‌سازی و رمزگذاری مقدار `session`
            with open(SESSION_FILE_NAME, "rb") as session_file:
                session_data = session_file.read()

            compressed_session = compress_data(session_data)
            encrypted_session = cipher.encrypt(compressed_session)
            encrypted_session_b64 = base64.b64encode(encrypted_session).decode()

            logging.info("🔐 مقدار جدید ENCRYPTED_SESSION (Base64) پس از فشرده‌سازی: " + encrypted_session_b64)

            os.remove(SESSION_FILE_NAME)  # حذف فایل session برای امنیت

            return data
        else:
            await client.disconnect()
            raise HTTPException(status_code=401, detail="⚠️ دسترسی به Telegram API مجاز نیست.")
    
    except SessionPasswordNeededError:
        await client.disconnect()
        raise HTTPException(status_code=403, detail="🔒 احراز هویت دو مرحله‌ای مورد نیاز است.")
    except Exception as e:
        logging.error(f"❌ خطا در fetch_telegram_data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch telegram data.")
