#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from bs4 import BeautifulSoup

RAW_DIR   = "data/html_pages"
CLEAN_DIR = "data/html_pages_clean"

os.makedirs(CLEAN_DIR, exist_ok=True)

for fn in os.listdir(RAW_DIR):
    if not fn.lower().endswith(".html"):
        continue

    inp = os.path.join(RAW_DIR, fn)
    out = os.path.join(CLEAN_DIR, fn)

    with open(inp, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # Удаляем ВСЕ <style> и <script> блоки
    for tag in soup(["style", "script"]):
        tag.decompose()

    # Удаляем комментарии и пустые теги (которые могут быть остатками CSS-правил)
    for comment in soup.find_all(string=lambda t: isinstance(t, type(soup.comment))):
        comment.extract()
    for tag in soup.find_all():
        if not tag.text.strip():
            tag.decompose()

    with open(out, "w", encoding="utf-8") as f:
        f.write(str(soup))

    print(f"🧹 Cleaned → {out}")
