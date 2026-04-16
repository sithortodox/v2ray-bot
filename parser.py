import base64
import json
import re
from urllib.parse import unquote, urlparse, parse_qs
from dataclasses import dataclass


@dataclass
class ParsedConfig:
    protocol: str
    raw: str
    server: str
    port: int
    name: str


def _add_padding(s: str) -> str:
    return s + "=" * (4 - len(s) % 4) if len(s) % 4 else s


def parse_vmess(raw: str) -> ParsedConfig | None:
    try:
        encoded = raw.replace("vmess://", "")
        decoded = base64.b64decode(_add_padding(encoded)).decode("utf-8")
        data = json.loads(decoded)
        return ParsedConfig(
            protocol="vmess",
            raw=raw,
            server=data.get("add", ""),
            port=int(data.get("port", 0)),
            name=data.get("ps", "unnamed"),
        )
    except Exception:
        return None


def parse_vless(raw: str) -> ParsedConfig | None:
    try:
        body = raw.replace("vless://", "")
        fragment = ""
        if "#" in body:
            body, fragment = body.rsplit("#", 1)
            fragment = unquote(fragment)
        if "?" in body:
            body, _ = body.split("?", 1)
        uuid, host_port = body.split("@", 1)
        if ":" in host_port:
            server, port_str = host_port.rsplit(":", 1)
            port = int(port_str)
        else:
            return None
        return ParsedConfig(
            protocol="vless",
            raw=raw,
            server=server,
            port=port,
            name=fragment or "unnamed",
        )
    except Exception:
        return None


def parse_trojan(raw: str) -> ParsedConfig | None:
    try:
        body = raw.replace("trojan://", "")
        fragment = ""
        if "#" in body:
            body, fragment = body.rsplit("#", 1)
            fragment = unquote(fragment)
        if "?" in body:
            body, _ = body.split("?", 1)
        password, host_port = body.split("@", 1)
        if ":" in host_port:
            server, port_str = host_port.rsplit(":", 1)
            port = int(port_str)
        else:
            return None
        return ParsedConfig(
            protocol="trojan",
            raw=raw,
            server=server,
            port=port,
            name=fragment or "unnamed",
        )
    except Exception:
        return None


def parse_ss(raw: str) -> ParsedConfig | None:
    try:
        body = raw.replace("ss://", "")
        fragment = ""
        if "#" in body:
            body, fragment = body.rsplit("#", 1)
            fragment = unquote(fragment)

        if "@" in body:
            encoded_part, host_port = body.split("@", 1)
            decoded = base64.b64decode(_add_padding(encoded_part)).decode("utf-8")
            method, _ = decoded.split(":", 1)
            server, port_str = host_port.rsplit(":", 1)
            port = int(port_str)
        else:
            decoded = base64.b64decode(_add_padding(body)).decode("utf-8")
            if "@" not in decoded:
                return None
            method_pass, host_port = decoded.split("@", 1)
            method, _ = method_pass.split(":", 1)
            server, port_str = host_port.rsplit(":", 1)
            port = int(port_str)

        return ParsedConfig(
            protocol="ss",
            raw=raw,
            server=server,
            port=port,
            name=fragment or "unnamed",
        )
    except Exception:
        return None


PARSERS = {
    "vmess": parse_vmess,
    "vless": parse_vless,
    "trojan": parse_trojan,
    "ss": parse_ss,
}

CONFIG_PATTERN = re.compile(r"(vmess://|vless://|trojan://|ss://)[^\s<>\"']+")


def extract_configs(text: str) -> list[ParsedConfig]:
    results = []
    seen = set()
    for match in CONFIG_PATTERN.finditer(text):
        raw = match.group(0).strip()
        if raw in seen:
            continue
        seen.add(raw)
        protocol = raw.split("://")[0]
        parser = PARSERS.get(protocol)
        if parser:
            parsed = parser(raw)
            if parsed and parsed.server and parsed.port > 0:
                results.append(parsed)
    return results


def decode_subscription(text: str) -> str:
    try:
        cleaned = text.strip()
        decoded = base64.b64decode(_add_padding(cleaned)).decode("utf-8")
        if any(proto in decoded for proto in ["vmess://", "vless://", "trojan://", "ss://"]):
            return decoded
    except Exception:
        pass
    return text
