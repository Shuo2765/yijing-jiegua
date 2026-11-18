#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 index.html + iching-data.js + 圖示 合成單一 HTML（給 iPhone 單機用）"""

from __future__ import annotations

import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "易經解掛-單機.html"


def main() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    data_js = (ROOT / "iching-data.js").read_text(encoding="utf-8")

    icon_tag = ""
    icon_path = ROOT / "icon-180.png"
    if icon_path.exists():
        b64 = base64.b64encode(icon_path.read_bytes()).decode("ascii")
        icon_tag = f'<link rel="apple-touch-icon" href="data:image/png;base64,{b64}">\n    <link rel="icon" type="image/png" href="data:image/png;base64,{b64}">'

    # 拿掉需伺服器的資源
    html = re.sub(r'\s*<link rel="manifest"[^>]*>', "", html)
    html = re.sub(r'\s*<link rel="apple-touch-icon"[^>]*>', "", html)
    html = re.sub(r'\s*<link rel="icon"[^>]*>', "", html)
    if icon_tag:
        html = html.replace(
            '<title>易經數理占卜 - 六十四卦完整解掛</title>',
            icon_tag + '\n    <title>易經數理占卜 - 六十四卦完整解掛</title>',
        )

    tip = """    <div id="homescreenTip" class="homescreen-tip">
        <strong>單機版使用方式（不需電腦伺服器）</strong><br>
        1. 用 AirDrop／檔案 App 把本檔放到 iPhone<br>
        2. 用 <strong>Safari</strong> 開啟此 HTML<br>
        3. 可點分享 <strong>□↑</strong> →「加入主畫面」方便之後開啟<br>
        4. 檔案在手機裡即可離線使用，不必再開電腦
        <div class="tip-actions">
            <button type="button" class="btn-tip-ok" onclick="dismissHomescreenTip(false)">知道了</button>
            <button type="button" class="btn-tip-hide" onclick="dismissHomescreenTip(true)">不再顯示</button>
        </div>
    </div>"""
    html = re.sub(
        r'<div id="homescreenTip" class="homescreen-tip">[\s\S]*?</div>\s*<h1>',
        tip + "\n    <h1>",
        html,
        count=1,
    )

    # 內嵌卦象資料，移除外部 script 與 service worker
    html = html.replace(
        '<script src="iching-data.js"></script>\n<script>',
        "<script>\n" + data_js + "\n",
    )
    html = re.sub(
        r'if \("serviceWorker" in navigator\) \{\s*window\.addEventListener\("load", \(\) => \{\s*navigator\.serviceWorker\.register\("\./sw\.js"\)\.catch\(\(\) => \{\}\);\s*\}\);\s*\}\s*',
        "",
        html,
    )

    OUT.write_text(html, encoding="utf-8")
    print(f"已產生：{OUT}")
    print(f"大小：{OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
