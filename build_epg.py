#!/usr/bin/env python3
"""Build a small BCU-only XMLTV from manually uploaded provider XMLTV gzip.

This repository is public: never store a personalized IPTV M3U or stream URLs here.
"""
from __future__ import annotations

import gzip
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from lxml import etree

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "input" / "epg-lite.xml.gz"
OUTPUT = ROOT / "site" / "epg.xml"
MOSCOW = timezone(timedelta(hours=3))
MAX_BYTES = 4_500_000
BCU_PREFIX = "Xbcu-"


def main():
    if not INPUT.is_file():
        raise FileNotFoundError("Upload input/epg-lite.xml.gz before building EPG")

    today = datetime.now(MOSCOW)
    beginning = datetime.combine(today.date(), time.min, MOSCOW)
    limit = beginning + timedelta(days=3)

    channels: dict[str, bytes] = {}
    programmes: list[tuple[str, bytes, datetime]] = []
    dates: list[datetime] = []

    with gzip.open(INPUT, "rb") as raw:
        for _, elem in etree.iterparse(
            raw,
            events=("end",),
            tag=("channel", "programme"),
            no_network=True,
            resolve_entities=False,
            load_dtd=False,
        ):
            key = elem.get("id") if elem.tag == "channel" else elem.get("channel")
            if key and key.startswith(BCU_PREFIX):
                if elem.tag == "channel":
                    channels[key] = etree.tostring(elem, encoding="utf-8")
                else:
                    try:
                        start = datetime.strptime(elem.get("start"), "%Y%m%d%H%M%S %z")
                        stop = datetime.strptime(elem.get("stop"), "%Y%m%d%H%M%S %z")
                    except (TypeError, ValueError):
                        pass
                    else:
                        if start < limit and stop > beginning:
                            programmes.append((key, etree.tostring(elem, encoding="utf-8"), start))
                            dates.append(start)
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

    if len(channels) < 25 or len(programmes) < 50:
        raise RuntimeError(
            f"Missing BCU EPG for {today.date()}: "
            f"{len(channels)} channels, {len(programmes)} programmes"
        )

    # Keep all BCU channel elements, even those with temporarily absent programmes.
    guide = etree.Element("tv", {"generator-info-name": "SS IPTV BCU-only EPG"})
    for id_ in sorted(channels):
        guide.append(etree.fromstring(channels[id_]))
    for id_, raw, start in programmes:
        if id_ in channels:
            guide.append(etree.fromstring(raw))

    content = etree.tostring(guide, xml_declaration=True, encoding="UTF-8")
    if len(content) > MAX_BYTES:
        raise RuntimeError(f"BCU XMLTV unexpectedly exceeds limit: {len(content)} bytes")

    OUTPUT.parent.mkdir(exist_ok=True, parents=True)
    OUTPUT.write_bytes(content)
    (OUTPUT.parent / "index.html").write_text(
        '<!doctype html><html lang="ru"><meta charset="utf-8">'
        '<title>BCU EPG</title><body><a href="epg.xml">BCU XMLTV</a></body></html>\n',
        encoding="utf-8",
    )
    print(
        f"BCU EPG: {len(channels)} channel IDs, {len(programmes)} programmes; "
        f"{len(content)} bytes; latest programme begins "
        f"{max(dates).astimezone(MOSCOW).isoformat()}"
    )


if __name__ == "__main__":
    main()
