#!/usr/bin/env python3
"""Adapt the public six-channel diagnostic M3U to the Cloudflare Pages URL.

This file does NOT contain subscriber IPTV links. It only references a public demo video.
"""
import os
from pathlib import Path

folder = Path(__file__).resolve().parent / "site"
m3u = folder / "bcu-epg-test.m3u"
url = os.environ.get("CF_PAGES_URL", "").rstrip("/")
if not url.startswith("https://"):
    raise SystemExit("CF_PAGES_URL must be provided by Cloudflare Pages")
old = "https://tsvetkoff81.github.io/SS_IPTV_EPG/epg.xml"
original = m3u.read_text(encoding="utf-8")
if old not in original:
    raise SystemExit("The test M3U no longer has the expected GitHub EPG URL")
m3u.write_text(original.replace(old, url + "/epg.xml"), encoding="utf-8")
print("BCU diagnostic M3U will fetch EPG from", url + "/epg.xml")
