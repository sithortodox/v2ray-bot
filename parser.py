import base64
import json
import re
from urllib.parse import unquote
from dataclasses import dataclass


@dataclass
class ParsedConfig:
    protocol: str
    raw: str
    server: str
    port: int
    name: str
    has_encryption: bool


def _pad(s: str) -> str:
    return s + "=" * (4 - len(s) % 4) if len(s) % 4 else s


def _detect_encryption_vmess(d: dict) -> bool:
    tls = d.get("tls", "")
    if tls in ("tls", "1", True):
        return True
    net = d.get("net", "tcp")
    if net in ("ws", "grpc", "h2", "http"):
        return True
    return False


def _detect_encryption_vless(params: dict) -> bool:
    security = params.get("security", "none")
    if security in ("tls", "reality"):
        return True
    net = params.get("type", "tcp")
    if net in ("ws", "grpc", "h2"):
        if security in ("tls", "reality"):
            return True
        return False
    return False


def _detect_encryption_trojan(params: dict) -> bool:
    security = params.get("security", "tls")
    if security in ("tls", "reality"):
        return True
    net = params.get("type", "tcp")
    if net in ("ws", "grpc", "h2"):
        return True
    return True


def parse_vmess(raw: str) -> ParsedConfig | None:
    try:
        encoded = raw.replace("vmess://", "")
        decoded = base64.b64decode(_pad(encoded)).decode("utf-8")
        data = json.loads(decoded)
        return ParsedConfig(
            protocol="vmess",
            raw=raw,
            server=data.get("add", ""),
            port=int(data.get("port", 0)),
            name=data.get("ps", "unnamed"),
            has_encryption=_detect_encryption_vmess(data),
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
        params_str = ""
        if "?" in body:
            body, params_str = body.split("?", 1)
        uuid, host_port = body.split("@", 1)
        if ":" in host_port:
            server, port_str = host_port.rsplit(":", 1)
            port = int(port_str)
        else:
            return None
        params = {}
        if params_str:
            for p in params_str.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = unquote(v)
        return ParsedConfig(
            protocol="vless",
            raw=raw,
            server=server,
            port=port,
            name=fragment or "unnamed",
            has_encryption=_detect_encryption_vless(params),
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
        params_str = ""
        if "?" in body:
            body, params_str = body.split("?", 1)
        password, host_port = body.split("@", 1)
        if ":" in host_port:
            server, port_str = host_port.rsplit(":", 1)
            port = int(port_str)
        else:
            return None
        params = {}
        if params_str:
            for p in params_str.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = unquote(v)
        return ParsedConfig(
            protocol="trojan",
            raw=raw,
            server=server,
            port=port,
            name=fragment or "unnamed",
            has_encryption=_detect_encryption_trojan(params),
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
            decoded = base64.b64decode(_pad(encoded_part)).decode("utf-8")
            method, _ = decoded.split(":", 1)
            server, port_str = host_port.rsplit(":", 1)
            port = int(port_str)
        else:
            decoded = base64.b64decode(_pad(body)).decode("utf-8")
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
            has_encryption=False,
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
        decoded = base64.b64decode(_pad(cleaned)).decode("utf-8")
        if any(proto in decoded for proto in ["vmess://", "vless://", "trojan://", "ss://"]):
            return decoded
    except Exception:
        pass
    return text
