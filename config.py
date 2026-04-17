import os
from dotenv import load_dotenv

load_dotenv(override=False)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
CHECK_TIMEOUT_SECONDS = int(os.getenv("CHECK_TIMEOUT_SECONDS", "5"))
DB_PATH = os.getenv("DB_PATH", "/app/data/v2ray_bot.db")

GITHUB_API_URL = "https://api.github.com"
GITHUB_RAW_URL = "https://raw.githubusercontent.com"
PUSH_REPO = os.getenv("PUSH_REPO", "sithortodox/v2ray-bot")
PUSH_BRANCH = os.getenv("PUSH_BRANCH", "main")

SEARCH_QUERIES = [
    "vmess://",
    "vless://",
    "trojan://",
    "ss://",
]

SEARCH_EXTENSIONS = ["txt", "yaml", "yml", "json", "csv", "conf"]

SUBSCRIPTION_URLS = [
    "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAgg/master//sub/sub_merge_base64.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list_raw.txt",
    "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
    "https://raw.githubusercontent.com/freefq/free/master/v2",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/base64/mix",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/base64/vless",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/base64/vmess",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/base64/trojan",
    "https://raw.githubusercontent.com/sashalsk/V2Ray/main/V2Config_64Encode",
    "https://raw.githubusercontent.com/mahdibland/V2RayAgg/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/ermaozi/free_subscribe/main/v2ray/v2ray.txt",
    "https://raw.githubusercontent.com/coolsteamsv2ray/v2ray/refs/heads/main/v2ray.txt",
    "https://raw.githubusercontent.com/Bardiafa/Free-V2ray-Config/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/v2rayfree/v2ray-free/master/v2",
]

KNOWN_REPO_FILES = [
    ("barry-far/V2ray-Configs", "All_Configs_Sub.txt"),
    ("barry-far/V2ray-Configs", "Sub1.txt"),
    ("barry-far/V2ray-Configs", "Sub2.txt"),
    ("barry-far/V2ray-Configs", "Sub3.txt"),
    ("barry-far/V2ray-Configs", "Sub4.txt"),
    ("barry-far/V2ray-Configs", "Sub5.txt"),
    ("barry-far/V2ray-Configs", "Sub6.txt"),
    ("barry-far/V2ray-Configs", "Sub7.txt"),
    ("barry-far/V2ray-Configs", "Sub8.txt"),
    ("barry-far/V2ray-Configs", "Sub9.txt"),
    ("barry-far/V2ray-Configs", "Sub10.txt"),
    ("yebekhe/TelegramV2rayCollector", "sub/sub_merge.txt"),
    ("yebekhe/TelegramV2rayCollector", "sub/sub_merge_base64.txt"),
    ("yebekhe/TelegramV2rayCollector", "sub/base64/mix"),
    ("mahdibland/V2RayAgg", "sub/sub_merge.txt"),
    ("mahdibland/V2RayAgg", "sub/sub_merge_base64.txt"),
    ("peasoft/NoMoreWalls", "list_raw.txt"),
    ("peasoft/NoMoreWalls", "list.txt"),
    ("aiboboxx/v2rayfree", "v2"),
    ("freefq/free", "v2"),
    ("mfuu/v2ray", "v2ray"),
    ("Pawdroid/Free-servers", "sub"),
    ("ermaozi/free_subscribe", "v2ray/v2ray.txt"),
    ("sashalsk/V2Ray", "V2Config_64Encode"),
    ("Bardiafa/Free-V2ray-Config", "All_Configs_Sub.txt"),
    ("v2rayfree/v2ray-free", "v2"),
]

MAX_CONFIGS_PER_MESSAGE = 10
