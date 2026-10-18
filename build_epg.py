#!/usr/bin/env python3
"""Build compact XMLTV from public channel IDs; no M3U credentials or stream URLs."""
from __future__ import annotations

import base64
import gzip
import shutil
import zlib
from datetime import datetime, timedelta, time, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from lxml import etree

ROOT = Path(__file__).resolve().parent
XMLTV_URLS = (
    "https://bobor.pm/epg/epg-lite.xml",
    "https://bobor.pm/epg/epg-lite.xml.gz",
    "https://bobor.pm/epg/epg.xml",
    "https://bobor.pm/epg/epg.xml.gz",
)
MAX_XML_BYTES = 4_500_000
MOSCOW = timezone(timedelta(hours=3))
OUTPUT = ROOT / "site" / "epg.xml"


def selected_channels() -> set[str]:
    packed = (ROOT / "selected_ids.zlib64").read_text(encoding="ascii").strip()
    ids = set(zlib.decompress(base64.b64decode(packed, validate=True)).decode("utf-8").splitlines())
    if len(ids) != 766:
        raise ValueError(f"Expected 766 unique EPG channel IDs, got {len(ids)}")
    return ids


def build_xml(xml_path: Path, wanted: set[str], now: datetime, lookahead_hours: int):
    start_of_day = datetime.combine(now.date(), time.min, MOSCOW)
    cutoff = now + timedelta(hours=lookahead_hours)
    guide = etree.Element("tv", {"generator-info-name": "SS IPTV selected EPG"})
    n_channels = 0
    n_programmes = 0
    for _, element in etree.iterparse(
        str(xml_path), events=("end",), tag=("channel", "programme"),
        no_network=True, resolve_entities=False, load_dtd=False,
    ):
        name = element.get("id" if element.tag == "channel" else "channel")
        use = name in wanted
        if use and element.tag == "programme":
            try:
                begin = datetime.strptime(element.get("start"), "%Y%m%d%H%M%S %z")
                end = datetime.strptime(element.get("stop"), "%Y%m%d%H%M%S %z")
                use = begin < cutoff and end > start_of_day
            except (TypeError, ValueError):
                use = False
        if use:
            guide.append(etree.fromstring(etree.tostring(element)))
            if element.tag == "channel":
                n_channels += 1
            else:
                n_programmes += 1
        element.clear()
        while element.getprevious() is not None:
            del element.getparent()[0]
    return etree.tostring(guide, xml_declaration=True, encoding="UTF-8"), n_channels, n_programmes


def main() -> None:
    channel_ids = selected_channels()
    temp = ROOT / "_full_xmltv_download.tmp"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        downloaded = False
        for url in XMLTV_URLS:
            request = Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
                "Accept": "application/xml,text/xml,*/*",
            })
            try:
                print(f"Trying {url}", flush=True)
                with urlopen(request, timeout=25) as resp, temp.open("wb") as target:
                    if url.endswith(".gz") or resp.headers.get("Content-Type", "").startswith("application/gzip"):
                        with gzip.GzipFile(fileobj=resp) as raw_xml:
                            shutil.copyfileobj(raw_xml, target)
                    else:
                        shutil.copyfileobj(resp, target)
                if temp.stat().st_size < 100_000:
                    raise ValueError("Downloaded XMLTV seems incomplete")
                downloaded = True
                print(f"Downloaded {temp.stat().st_size} bytes", flush=True)
                break
            except (HTTPError, URLError, OSError, ValueError, EOFError) as error:
                print(f"EPG source failed: {url}: {type(error).__name__}: {error}", flush=True)
        if not downloaded:
            raise RuntimeError("All 4 official XMLTV sources are blocked or unavailable from GitHub Actions")
        now = datetime.now(MOSCOW)
        for hours in (48, 36, 24, 18, 12, 6):
            xml, channels, programmes = build_xml(temp, channel_ids, now, hours)
            if len(xml) <= MAX_XML_BYTES and channels >= 50 and programmes >= 100:
                OUTPUT.write_bytes(xml)
                (OUTPUT.parent / "index.html").write_text(
                    '<!doctype html><html><head><meta charset="utf-8"><title>SS IPTV EPG</title></head>'
                    '<body><a href="epg.xml">EPG XMLTV</a></body></html>\n',
                    encoding="utf-8",
                )
                print(f"OK: {len(xml)} bytes, {channels} channels, {programmes} programmes, {hours}h lookahead")
                return
        raise ValueError("No usable schedule could be kept below 4.5 MB")
    finally:
        temp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
