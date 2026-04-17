import asyncio
import base64
import logging
import aiohttp
from config import (
    GITHUB_API_URL, GITHUB_RAW_URL, GITHUB_TOKEN,
    SEARCH_QUERIES, SEARCH_EXTENSIONS,
    SUBSCRIPTION_URLS, KNOWN_REPO_FILES,
)
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


async def _fetch_url(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception as e:
        logger.debug("Failed to fetch %s: %s", url[:60], e)
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


async def scrape_known_repos() -> list[ParsedConfig]:
    all_configs: list[ParsedConfig] = []
    seen: set[str] = set()

    async with aiohttp.ClientSession() as session:
        for repo_name, file_path in KNOWN_REPO_FILES:
            content = await _fetch_raw(session, repo_name, file_path)
            if not content:
                continue
            decoded = decode_subscription(content)
            configs = extract_configs(decoded)
            count = 0
            for cfg in configs:
                if cfg.raw not in seen:
                    seen.add(cfg.raw)
                    all_configs.append(cfg)
                    count += 1
            logger.info("Known repo %s/%s: %d new configs", repo_name, file_path, count)
            await asyncio.sleep(1)

    logger.info("Known repos: %d total configs", len(all_configs))
    return _filter_configs(all_configs)


async def scrape_subscriptions() -> list[ParsedConfig]:
    all_configs: list[ParsedConfig] = []
    seen: set[str] = set()

    async with aiohttp.ClientSession() as session:
        for url in SUBSCRIPTION_URLS:
            content = await _fetch_url(session, url)
            if not content:
                continue
            decoded = decode_subscription(content)
            configs = extract_configs(decoded)
            count = 0
            for cfg in configs:
                if cfg.raw not in seen:
                    seen.add(cfg.raw)
                    all_configs.append(cfg)
                    count += 1
            logger.info("Subscription %s: %d new configs", url[:60], count)
            await asyncio.sleep(1)

    logger.info("Subscriptions: %d total configs", len(all_configs))
    return _filter_configs(all_configs)


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

    logger.info("Scraped %d unique configs from GitHub search", len(all_configs))
    return _filter_configs(all_configs)


async def scrape_all() -> list[ParsedConfig]:
    c1, c2, c3 = await asyncio.gather(
        scrape_known_repos(),
        scrape_subscriptions(),
        scrape_github(),
    )
    seen = set()
    result = []
    for cfg in c1 + c2 + c3:
        if cfg.raw not in seen:
            seen.add(cfg.raw)
            result.append(cfg)
    return result
