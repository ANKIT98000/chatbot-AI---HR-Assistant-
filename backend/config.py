import os
from dotenv import load_dotenv

load_dotenv()

HUGGINGFACEHUB_API_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")