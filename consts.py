import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
DB_NAME = os.getenv('DB_NAME', 'quiz_bot.db')