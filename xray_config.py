import base64
import json
import logging
from urllib.parse import unquote

logger = logging.getLogger(__name__)


def _pad(s: str) -> str:
    return s + "=" * (4 - len(s) % 4) if len(s) % 4 else s


def _parse_vmess(raw: str) -> dict | None:
    try:
        encoded = raw.replace("vmess://", "")
        d = json.loads(base64.b64decode(_pad(encoded)))
        tls_val = d.get("tls", "")
        if not tls_val or tls_val == "0" or tls_val.lower() == "false":
            tls_val = "none"
        elif tls_val.lower() == "tls" or tls_val == "1" or tls_val.lower() == "true":
            tls_val = "tls"
        return {
            "address": d.get("add", ""),
            "port": int(d.get("port", 0)),
            "uuid": d.get("id", ""),
            "alterId": int(d.get("aid", 0)),
            "network": d.get("net", "tcp") or "tcp",
            "security": tls_val,
            "host": d.get("host", ""),
            "path": d.get("path", ""),
            "sni": d.get("sni", d.get("host", "")),
            "serviceName": d.get("serviceName", d.get("service", "")),
            "fp": d.get("fp", ""),
            "pbk": d.get("pbk", ""),
            "sid": d.get("sid", ""),
            "alpn": d.get("alpn", ""),
            "scy": d.get("scy", d.get("security", "auto")),
            "insecure": d.get("insecure", d.get("allowInsecure", "")),
        }
    except Exception:
        return None


def _parse_vless(raw: str) -> dict | None:
    try:
        body = raw.replace("vless://", "")
        if "#" in body:
            body = body.rsplit("#", 1)[0]
        params_str = ""
        if "?" in body:
            body, params_str = body.split("?", 1)
        uuid, host_port = body.split("@", 1)
        server, port_str = host_port.rsplit(":", 1)
        params = {}
        if params_str:
            for p in params_str.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = unquote(v)
        security = params.get("security", "none")
        if not security or security == "0":
            security = "none"
        return {
            "address": server,
            "port": int(port_str),
            "uuid": uuid,
            "network": params.get("type", "tcp") or "tcp",
            "security": security,
            "sni": params.get("sni", ""),
            "path": params.get("path", ""),
            "host": params.get("host", ""),
            "flow": params.get("flow", ""),
            "serviceName": params.get("serviceName", ""),
            "fp": params.get("fp", ""),
            "pbk": params.get("pbk", ""),
            "sid": params.get("sid", ""),
            "alpn": params.get("alpn", ""),
        }
    except Exception:
        return None


def _parse_trojan(raw: str) -> dict | None:
    try:
        body = raw.replace("trojan://", "")
        if "#" in body:
            body = body.rsplit("#", 1)[0]
        params_str = ""
        if "?" in body:
            body, params_str = body.split("?", 1)
        password, host_port = body.split("@", 1)
        server, port_str = host_port.rsplit(":", 1)
        params = {}
        if params_str:
            for p in params_str.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = unquote(v)
        security = params.get("security", "tls")
        if not security:
            security = "tls"
        return {
            "address": server,
            "port": int(port_str),
            "password": unquote(password),
            "network": params.get("type", "tcp") or "tcp",
            "security": security,
            "sni": params.get("sni", ""),
            "path": params.get("path", ""),
            "host": params.get("host", ""),
            "serviceName": params.get("serviceName", ""),
            "alpn": params.get("alpn", ""),
            "fp": params.get("fp", ""),
            "allowInsecure": params.get("allowInsecure", "0") == "1",
        }
    except Exception:
        return None


def _parse_ss(raw: str) -> dict | None:
    try:
        body = raw.replace("ss://", "")
        if "#" in body:
            body = body.rsplit("#", 1)[0]
        if "@" in body:
            encoded_part, host_port = body.split("@", 1)
            decoded = base64.b64decode(_pad(encoded_part)).decode("utf-8")
            method, password = decoded.split(":", 1)
            server, port_str = host_port.rsplit(":", 1)
        else:
            decoded = base64.b64decode(_pad(body)).decode("utf-8")
            method_pass, host_port = decoded.split("@", 1)
            method, password = method_pass.split(":", 1)
            server, port_str = host_port.rsplit(":", 1)
        return {
            "address": server,
            "port": int(port_str),
            "method": method,
            "password": password,
        }
    except Exception:
        return None


def _build_stream(params: dict) -> dict:
    network = params.get("network", "tcp")
    if network == "h2":
        network = "http"
    security = params.get("security", "none")
    stream = {"network": network}

    if security == "reality":
        stream["security"] = "reality"
        rset = {}
        if params.get("sni"):
            rset["serverName"] = params["sni"]
        rset["fingerprint"] = params.get("fp") or "chrome"
        if params.get("pbk"):
            rset["publicKey"] = params["pbk"]
        if params.get("sid") is not None:
            rset["shortId"] = params["sid"]
        stream["realitySettings"] = rset

    elif security in ("tls",):
        stream["security"] = "tls"
        tset = {}
        sni = params.get("sni", "")
        if not sni and params.get("host"):
            sni = params["host"]
        if sni:
            tset["serverName"] = sni
        else:
            tset["allowInsecure"] = True
        if params.get("allowInsecure"):
            tset["allowInsecure"] = True
        if params.get("insecure") and str(params["insecure"]) not in ("0", "false", ""):
            tset["allowInsecure"] = True
        alpn = params.get("alpn", "")
        if alpn:
            tset["alpn"] = [a.strip() for a in alpn.split(",")]
        stream["tlsSettings"] = tset

    else:
        stream["security"] = "none"

    if network == "ws":
        ws = {}
        path = params.get("path", "")
        if path:
            ws["path"] = path
        else:
            ws["path"] = "/"
        host_val = params.get("host", "")
        if host_val:
            ws["headers"] = {"Host": host_val}
        stream["wsSettings"] = ws
    elif network == "grpc":
        grpc = {}
        if params.get("serviceName"):
            grpc["serviceName"] = params["serviceName"]
        stream["grpcSettings"] = grpc
    elif network == "http":
        h2 = {}
        path = params.get("path", "")
        if path:
            h2["path"] = path
        host_val = params.get("host", "")
        if host_val:
            h2["host"] = [h.strip() for h in host_val.split(",")]
        stream["httpSettings"] = h2
    elif network == "kcp":
        kcp = {}
        if params.get("serviceName"):
            kcp["header"] = {"type": params["serviceName"]}
        stream["kcpSettings"] = kcp

    return stream


PARSERS = {
    "vmess": _parse_vmess,
    "vless": _parse_vless,
    "trojan": _parse_trojan,
    "ss": _parse_ss,
}


def generate_xray_config(raw_url: str, local_port: int) -> dict | None:
    protocol = raw_url.split("://")[0]
    params = PARSERS.get(protocol, lambda x: None)(raw_url)
    if not params:
        return None

    if protocol == "vmess":
        scy = params.get("scy", "auto")
        if scy in ("auto", "none", ""):
            scy = "auto"
        outbound = {
            "protocol": "vmess",
            "settings": {
                "vnext": [{
                    "address": params["address"],
                    "port": params["port"],
                    "users": [{"id": params["uuid"], "alterId": params["alterId"], "security": scy}],
                }]
            },
            "streamSettings": _build_stream(params),
        }
    elif protocol == "vless":
        user = {"id": params["uuid"], "encryption": "none"}
        flow = params.get("flow", "")
        if flow and flow != "none":
            user["flow"] = flow
        outbound = {
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": params["address"],
                    "port": params["port"],
                    "users": [user],
                }]
            },
            "streamSettings": _build_stream(params),
        }
    elif protocol == "trojan":
        outbound = {
            "protocol": "trojan",
            "settings": {
                "servers": [{
                    "address": params["address"],
                    "port": params["port"],
                    "password": params["password"],
                }]
            },
            "streamSettings": _build_stream(params),
        }
    elif protocol == "ss":
        outbound = {
            "protocol": "shadowsocks",
            "settings": {
                "servers": [{
                    "address": params["address"],
                    "port": params["port"],
                    "method": params["method"],
                    "password": params["password"],
                }]
            },
        }
    else:
        return None

    return {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "port": local_port,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "settings": {"auth": "noauth", "udp": False},
        }],
        "outbounds": [outbound],
    }
