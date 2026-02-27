import os

from dateutil import tz
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


TOPICS = {
    "Lietuvoje": "https://www.lrt.lt/naujienos/lietuvoje?rss",
    "Pasaulyje": "https://www.lrt.lt/naujienos/pasaulyje?rss",
    "Mokslas ir IT": "https://www.lrt.lt/naujienos/mokslas-ir-it?rss",
    "Verslas": "https://www.lrt.lt/naujienos/verslas?rss",
    "Sportas": "https://www.lrt.lt/naujienos/sportas?rss",
}

MAX_ARTICLES_PER_TOPIC_MORNING = int(os.getenv("MAX_ARTICLES_PER_TOPIC_MORNING", "5"))
MAX_ARTICLES_PER_TOPIC_MIDDAY = int(os.getenv("MAX_ARTICLES_PER_TOPIC_MIDDAY", "5"))
MAX_ARTICLES_PER_TOPIC_EVENING = int(os.getenv("MAX_ARTICLES_PER_TOPIC_EVENING", "5"))

LOCAL_TZ = tz.gettz("Europe/Vilnius")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

# BREAKING if published within last N minutes
BREAKING_MINUTES = int(os.getenv("BREAKING_MINUTES", "90"))

# Optional: include weather block (Vilnius) in HTML/email
INCLUDE_WEATHER = os.getenv("INCLUDE_WEATHER", "1").strip() not in ("0", "false", "False")

