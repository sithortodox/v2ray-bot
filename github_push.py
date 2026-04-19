import base64
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone

from config import GITHUB_TOKEN, PUSH_REPO, PUSH_BRANCH

logger = logging.getLogger(__name__)

WORKING_FILE = "working.txt"
WORKING_BASE64_FILE = "working_base64.txt"
README_FILE = "configs_readme.md"
REPO_URL = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{PUSH_REPO}.git"


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

    tmpdir = tempfile.mkdtemp(prefix="v2ray_push_")
    try:
        r = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", PUSH_BRANCH, REPO_URL, tmpdir],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            logger.error("git clone failed: %s", r.stderr[:200])
            return

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        raw_content = "\n".join(working_raw)
        b64_content = _make_base64(working_raw)
        readme_content = _make_readme(len(working_raw), dead_count, now)

        for path, content in [
            (WORKING_FILE, raw_content),
            (WORKING_BASE64_FILE, b64_content),
            (README_FILE, readme_content),
        ]:
            full_path = os.path.join(tmpdir, path)
            os.makedirs(os.path.dirname(full_path) or ".", exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)

        subprocess.run(["git", "add", "-A"], cwd=tmpdir, capture_output=True, timeout=10)

        subprocess.run(
            ["git", "config", "user.email", "bot@v2ray.local"],
            cwd=tmpdir, capture_output=True, timeout=5,
        )
        subprocess.run(
            ["git", "config", "user.name", "v2ray-bot"],
            cwd=tmpdir, capture_output=True, timeout=5,
        )

        r = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=tmpdir, capture_output=True, timeout=10,
        )
        if r.returncode == 0:
            logger.info("No changes to push")
            return

        subprocess.run(
            ["git", "commit", "-m", f"Update working configs ({len(working_raw)}) - {now}"],
            cwd=tmpdir, capture_output=True, text=True, timeout=10,
        )

        r = subprocess.run(
            ["git", "push"],
            cwd=tmpdir, capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            logger.error("git push failed: %s", r.stderr[:200])
        else:
            logger.info("Pushed %d working configs to %s", len(working_raw), PUSH_REPO)

    except Exception as e:
        logger.error("Failed to push to GitHub: %s", e)
    finally:
        subprocess.run(["rm", "-rf", tmpdir], capture_output=True)
