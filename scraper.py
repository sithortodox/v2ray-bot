import asyncio
import logging
import aiohttp
from config import GITHUB_API_URL, GITHUB_RAW_URL, GITHUB_TOKEN, SEARCH_QUERIES, SEARCH_EXTENSIONS
from parser import extract_configs, decode_subscription, ParsedConfig
from checker import is_blacklisted

logger = logging.getLogger(__name__)

MAX_ITEMS_PER_QUERY = 5
DELAY_BETWEEN_REQUESTS = 4

PRIORITY_QUERIES = [
    "vless+reality",
    "vmess+ws+tls",
    "trojan",
    "v2ray",
]

PRIORITY_EXTENSIONS = ["txt", "csv", "conf"]


def _headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


async def _search_code(session: aiohttp.ClientSession, query: str) -> list[dict]:
    url = f"{GITHUB_API_URL}/search/code"
    params = {"q": query, "per_page": MAX_ITEMS_PER_QUERY, "page": 1}
    try:
        async with session.get(url, headers=_headers(), params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("items", [])
            elif resp.status == 403:
                logger.warning("GitHub API rate limit hit")
                await asyncio.sleep(30)
                return []
            else:
                logger.warning("GitHub search returned %s for: %s", resp.status, query)
                return []
    except Exception as e:
        logger.error("GitHub search error: %s", e)
        return []


async def _fetch_raw(session: aiohttp.ClientSession, repo_full_name: str, file_path: str) -> str:
    for branch in ("main", "master"):
        url = f"{GITHUB_RAW_URL}/{repo_full_name}/{branch}/{file_path}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception:
            pass
    return ""


def _filter_configs(configs: list[ParsedConfig]) -> list[ParsedConfig]:
    result = []
    for cfg in configs:
        if is_blacklisted(cfg):
            continue
        if cfg.protocol == "ss" and cfg.port in (443, 80, 8080):
            continue
        result.append(cfg)
    vmess_vless = [c for c in result if c.protocol in ("vmess", "vless", "trojan")]
    ss = [c for c in result if c.protocol == "ss"]
    return vmess_vless + ss


async def scrape_github() -> list[ParsedConfig]:
    all_configs: list[ParsedConfig] = []
    seen_raw: set[str] = set()
    seen_repos: set[str] = set()

    async with aiohttp.ClientSession() as session:
        for pq in PRIORITY_QUERIES:
            for ext in PRIORITY_EXTENSIONS:
                query = f'{pq} extension:{ext}'
                items = await _search_code(session, query)
                for item in items[:MAX_ITEMS_PER_QUERY]:
                    repo_name = item["repository"]["full_name"]
                    file_path = item["path"]
                    repo_key = f"{repo_name}/{file_path}"
                    if repo_key in seen_repos:
                        continue
                    seen_repos.add(repo_key)
                    content = await _fetch_raw(session, repo_name, file_path)
                    if not content:
                        continue
                    decoded = decode_subscription(content)
                    configs = extract_configs(decoded)
                    for cfg in configs:
                        if cfg.raw not in seen_raw:
                            seen_raw.add(cfg.raw)
                            all_configs.append(cfg)
                    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        for protocol_query in SEARCH_QUERIES:
            for ext in SEARCH_EXTENSIONS:
                query = f'"{protocol_query}" extension:{ext}'
                items = await _search_code(session, query)
                for item in items[:MAX_ITEMS_PER_QUERY]:
                    repo_name = item["repository"]["full_name"]
                    file_path = item["path"]
                    repo_key = f"{repo_name}/{file_path}"
                    if repo_key in seen_repos:
                        continue
                    seen_repos.add(repo_key)
                    content = await _fetch_raw(session, repo_name, file_path)
                    if not content:
                        continue
                    decoded = decode_subscription(content)
                    configs = extract_configs(decoded)
                    for cfg in configs:
                        if cfg.raw not in seen_raw:
                            seen_raw.add(cfg.raw)
                            all_configs.append(cfg)
                    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    logger.info("Scraped %d unique configs from GitHub", len(all_configs))
    return _filter_configs(all_configs)


async def scrape_subscription_urls() -> list[ParsedConfig]:
    all_configs: list[ParsedConfig] = []
    seen_raw: set[str] = set()

    async with aiohttp.ClientSession() as session:
        for q in ["v2ray subscription", "vless reality free", "vmess ws tls free"]:
            query = f'{q} extension:txt'
            items = await _search_code(session, query)
            for item in items[:5]:
                repo_name = item["repository"]["full_name"]
                file_path = item["path"]
                content = await _fetch_raw(session, repo_name, file_path)
                if not content:
                    continue
                decoded = decode_subscription(content)
                configs = extract_configs(decoded)
                for cfg in configs:
                    if cfg.raw not in seen_raw:
                        seen_raw.add(cfg.raw)
                        all_configs.append(cfg)
                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    return _filter_configs(all_configs)


async def scrape_all() -> list[ParsedConfig]:
    configs1 = await scrape_github()
    configs2 = await scrape_subscription_urls()
    seen = set()
    result = []
    for cfg in configs1 + configs2:
        if cfg.raw not in seen:
            seen.add(cfg.raw)
            result.append(cfg)
    return result
