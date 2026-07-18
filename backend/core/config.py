import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./enterprise_platform.db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CRON_SECRET = os.getenv("CRON_SECRET", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

# Publish any day of the week
PUBLISH_WEEKDAYS = {0, 1, 2, 3, 4, 5, 6}
WEEKDAY_NAMES = {0: "Monday", 1: "Tuesday", 4: "Friday"}
ALL_WEEKDAY_NAMES = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}

DEFAULT_RSS_FEEDS = [
    "https://feeds.feedburner.com/TechCrunch/",
    "https://www.wired.com/feed/category/science/latest/rss",
    "https://export.arxiv.org/rss/cs",
    "https://www.technologyreview.com/feed/",
    "https://www.theverge.com/rss/index.xml",
]
