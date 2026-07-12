import os

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://rpa:rpa_secret@db:5432/rpa_bot")
MOCKSHOP_URL = os.getenv("MOCKSHOP_URL", "http://mockshop:8090")
HEADED = os.getenv("HEADED", "false").lower() == "true"
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
