#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""易經解掛工具 - 本機伺服器

9080：HTTP 直接提供網站（iPhone 最穩，先這樣用）
9443：HTTPS（之後要離線 PWA / Service Worker 再用）
"""

from __future__ import annotations

import ipaddress
import shutil
import socket
import ssl
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HTTP_PORT = 9080
HTTPS_PORT = 9443
ROOT = Path(__file__).resolve().parent
CERT_DIR = ROOT / ".certs"
CERT_FILE = CERT_DIR / "cert.pem"
KEY_FILE = CERT_DIR / "key.pem"
CRT_DOWNLOAD = ROOT / "iching-local.crt"
IP_RECORD = CERT_DIR / "bound-ips.txt"

OPENSSL_CANDIDATES = [
    Path(r"C:\Program Files\Git\usr\bin\openssl.exe"),
    Path(r"C:\Program Files (x86)\Git\usr\bin\openssl.exe"),
]

VPN_HINTS = (
    "vpn", "tap", "tun", "tunnel", "wintun", "wireguard", "nordlynx",
    "zerotier", "hamachi", "outline", "clash", "meta", "vnic", "hyper-v",
    "vethernet", "docker", "wsl", "virtualbox", "vmware", "loopback",
)


def _is_private_ipv4(ip: str) -> bool:
    try:
        addr = ipaddress.IPv4Address(ip)
    except ValueError:
        return False
    return addr.is_private and not addr.is_loopback


def list_lan_ipv4() -> list[str]:
    preferred: list[str] = []
    others: list[str] = []
    ps = (
        "Get-NetIPAddress -AddressFamily IPv4 | "
        "Where-Object { $_.IPAddress -notlike '127.*' } | "
        "ForEach-Object { '{0}`t{1}' -f $_.IPAddress, $_.InterfaceAlias }"
    )
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
        )
        for line in out.splitlines():
            line = line.strip()
            if not line or "\t" not in line:
                continue
            ip, alias = line.split("\t", 1)
            ip, alias = ip.strip(), alias.strip().lower()
            if not _is_private_ipv4(ip):
                continue
            if any(h in alias for h in VPN_HINTS):
                continue
            if any(k in alias for k in ("wi-fi", "wifi", "wlan", "ethernet", "乙太", "本地")):
                if ip not in preferred:
                    preferred.append(ip)
            elif ip not in others and ip not in preferred:
                others.append(ip)
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        pass

    if preferred or others:
        return preferred + [ip for ip in others if ip not in preferred]

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if _is_private_ipv4(ip):
                return [ip]
    except OSError:
        pass
    return ["127.0.0.1"]


def find_openssl() -> str:
    found = shutil.which("openssl")
    if found:
        return found
    for path in OPENSSL_CANDIDATES:
        if path.exists():
            return str(path)
    return ""


def sync_download_cert() -> None:
    if CERT_FILE.exists():
        CRT_DOWNLOAD.write_bytes(CERT_FILE.read_bytes())


def ensure_firewall_rule() -> None:
    for port, name in (
        (HTTP_PORT, "Iching HTTP 9080"),
        (HTTPS_PORT, "Iching HTTPS 9443"),
    ):
        try:
            check = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            text = check.stdout or ""
            if "Enabled:" in text or "已啟用" in text:
                continue
            result = subprocess.run(
                [
                    "netsh", "advfirewall", "firewall", "add", "rule",
                    f"name={name}", "dir=in", "action=allow", "protocol=TCP",
                    f"localport={port}", "profile=any",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            out = (result.stdout or "") + (result.stderr or "")
            if result.returncode != 0 or "elevation" in out.lower() or "administrator" in out.lower():
                print("  [提示] 若 iPhone 連不上，請右鍵以系統管理員執行 open-firewall.bat", flush=True)
                return
        except OSError:
            return


def ensure_certs(ips: list[str]) -> bool:
    """產生 HTTPS 憑證；失敗時仍可只跑 HTTP。"""
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    wanted = ",".join(ips)
    existing = IP_RECORD.read_text(encoding="utf-8").strip() if IP_RECORD.exists() else ""
    if CERT_FILE.exists() and KEY_FILE.exists() and existing == wanted:
        sync_download_cert()
        return True

    for path in (CERT_FILE, KEY_FILE):
        if path.exists():
            path.unlink()

    openssl = find_openssl()
    if not openssl:
        print("  [提示] 找不到 OpenSSL，略過 HTTPS（仍可用 HTTP 9080）", flush=True)
        return False

    primary = ips[0] if ips else "127.0.0.1"
    alt_lines = ["DNS.1 = localhost", "IP.1 = 127.0.0.1"]
    idx = 2
    for ip in ips:
        if ip == "127.0.0.1":
            continue
        alt_lines.append(f"IP.{idx} = {ip}")
        idx += 1

    cfg = CERT_DIR / "san.cnf"
    cfg.write_text(
        "\n".join([
            "[req]",
            "distinguished_name = req_distinguished_name",
            "x509_extensions = v3_req",
            "prompt = no",
            "[req_distinguished_name]",
            f"CN = iching-local-{primary}",
            "[v3_req]",
            "basicConstraints = CA:FALSE",
            "keyUsage = digitalSignature, keyEncipherment",
            "extendedKeyUsage = serverAuth",
            "subjectAltName = @alt",
            "[alt]",
            *alt_lines,
        ])
        + "\n",
        encoding="ascii",
    )
    cmd = [
        openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(KEY_FILE), "-out", str(CERT_FILE),
        "-days", "825", "-config", str(cfg),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        print("  [提示] 憑證產生失敗，略過 HTTPS：", flush=True)
        print("  ", (exc.stderr or exc.stdout or str(exc))[:200], flush=True)
        return False

    IP_RECORD.write_text(wanted, encoding="utf-8")
    sync_download_cert()
    return True


class StaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        path = self.path.split("?", 1)[0]
        if path.endswith(".webmanifest"):
            self.send_header("Content-Type", "application/manifest+json")
        elif path.endswith(".crt"):
            self.send_header("Content-Type", "application/x-x509-ca-cert")
        # 避免快取舊版
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))
        sys.stderr.flush()


class ReuseHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False


class HTTPSServer(ReuseHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, ssl_context: ssl.SSLContext):
        self.ssl_context = ssl_context
        super().__init__(server_address, RequestHandlerClass)

    def get_request(self):
        newsocket, fromaddr = self.socket.accept()
        try:
            return self.ssl_context.wrap_socket(newsocket, server_side=True), fromaddr
        except ssl.SSLError as exc:
            sys.stderr.write("TLS 握手失敗（%s）：%s\n" % (fromaddr[0], exc))
            sys.stderr.flush()
            try:
                newsocket.close()
            except OSError:
                pass
            raise OSError("TLS handshake failed") from exc


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ips = list_lan_ipv4()
    primary = ips[0] if ips else "127.0.0.1"
    ensure_firewall_rule()
    https_ok = ensure_certs(ips)

    try:
        http_srv = ReuseHTTPServer(("0.0.0.0", HTTP_PORT), StaticHandler)
    except OSError as exc:
        print(f"無法綁定 {HTTP_PORT}：{exc}")
        print("請先關閉所有舊的 start-server 黑色視窗（尤其還寫著 8080 的那個）後再試。")
        raise SystemExit(1) from exc

    https_srv = None
    if https_ok:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))
        try:
            https_srv = HTTPSServer(("0.0.0.0", HTTPS_PORT), StaticHandler, ctx)
        except OSError as exc:
            print(f"  [提示] HTTPS {HTTPS_PORT} 無法啟動：{exc}", flush=True)
            https_srv = None

    http_urls = [f"     http://{ip}:{HTTP_PORT}" for ip in ips] or [f"     http://127.0.0.1:{HTTP_PORT}"]

    lines = [
        "",
        "=" * 44,
        "  易經解掛工具伺服器  【版本 9080】",
        "=" * 44,
        "",
        "  ★ 請關掉所有還顯示 :8080 的舊視窗",
        "",
        "  iPhone Safari 請開（用 http，不用憑證）：",
        "",
        *http_urls,
        "",
    ]
    if https_srv:
        lines += [
            "  （進階／離線 PWA 才用 https）",
            f"     https://{primary}:{HTTPS_PORT}",
            "",
        ]
    lines += [
        "  關閉此視窗即停止伺服器",
        "=" * 44,
        "",
    ]
    print("\n".join(lines), flush=True)

    if https_srv:
        threading.Thread(target=https_srv.serve_forever, daemon=True).start()

    try:
        http_srv.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器已停止。", flush=True)
        http_srv.shutdown()
        if https_srv:
            https_srv.shutdown()


if __name__ == "__main__":
    main()
