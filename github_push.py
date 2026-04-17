import base64
import logging
from datetime import datetime, timezone

from github import Github, GithubException
from config import GITHUB_TOKEN, PUSH_REPO, PUSH_BRANCH

logger = logging.getLogger(__name__)

WORKING_FILE = "working.txt"
WORKING_BASE64_FILE = "working_base64.txt"
README_FILE = "configs_readme.md"


def _gh():
    return Github(GITHUB_TOKEN)


def _make_base64(configs: list[str]) -> str:
    joined = "\n".join(configs)
    return base64.b64encode(joined.encode()).decode()


def _make_readme(working: int, dead: int, updated: str) -> str:
    return f"""# V2Ray Working Configs

Auto-collected from GitHub and subscription sources.

- Working configs: **{working}**
- Removed dead configs: **{dead}**
- Last updated: {updated}
- Check interval: every 60 minutes

## Files

- `working.txt` — raw config URLs (one per line)
- `working_base64.txt` — base64-encoded subscription format

## Supported protocols

vmess, vless, trojan, shadowsocks

## Source

Collected by [v2ray-bot](https://github.com/{PUSH_REPO})
"""


def push_working_configs(working_raw: list[str], dead_count: int):
    if not GITHUB_TOKEN or not PUSH_REPO:
        logger.warning("GITHUB_TOKEN or PUSH_REPO not set, skipping push")
        return
    if not working_raw:
        logger.info("No working configs to push")
        return

    try:
        gh = _gh()
        repo = gh.get_repo(PUSH_REPO)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        raw_content = "\n".join(working_raw)
        b64_content = _make_base64(working_raw)
        readme_content = _make_readme(len(working_raw), dead_count, now)

        for path, content, msg in [
            (WORKING_FILE, raw_content, f"Update working configs ({len(working_raw)}) - {now}"),
            (WORKING_BASE64_FILE, b64_content, f"Update base64 subscription - {now}"),
            (README_FILE, readme_content, f"Update stats - {now}"),
        ]:
            try:
                existing = repo.get_contents(path, ref=PUSH_BRANCH)
                repo.update_file(
                    path=path,
                    message=msg,
                    content=content,
                    sha=existing.sha,
                    branch=PUSH_BRANCH,
                )
            except GithubException as e:
                if e.status == 404:
                    repo.create_file(
                        path=path,
                        message=msg,
                        content=content,
                        branch=PUSH_BRANCH,
                    )
                else:
                    raise

        logger.info("Pushed %d working configs to %s", len(working_raw), PUSH_REPO)

    except Exception as e:
        logger.error("Failed to push to GitHub: %s", e)
