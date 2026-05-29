from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("API_KEY", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/maison.db")
PORT = int(os.getenv("PORT", "8042"))
