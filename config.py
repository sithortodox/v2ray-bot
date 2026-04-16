import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
CHECK_TIMEOUT_SECONDS = int(os.getenv("CHECK_TIMEOUT_SECONDS", "5"))
DB_PATH = os.getenv("DB_PATH", "v2ray_bot.db")

GITHUB_API_URL = "https://api.github.com"
GITHUB_RAW_URL = "https://raw.githubusercontent.com"

SEARCH_QUERIES = [
    "vmess://",
    "vless://",
    "trojan://",
    "ss://",
]

SEARCH_EXTENSIONS = ["txt", "yaml", "yml", "json", "csv", "conf"]

MAX_CONFIGS_PER_MESSAGE = 10
