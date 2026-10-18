#!/usr/bin/env python3
"""Build SS IPTV XMLTV from a manually uploaded gzip file.

The input contains only public programme information. No stream URLs,
playlist access keys, or credentials are used or published.
"""
from __future__ import annotations

import base64
import gzip
import zlib
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "input" / "epg-lite.xml.gz"
IDS = ROOT / "selected_ids.zlib64"
OUTPUT = ROOT / "site" / "epg.xml"
MAX_BYTES = 4_500_000
LOCAL_TZ = timezone(timedelta(hours=3))


def selected_channels() -> set[str]:
    packed = IDS.read_text(encoding="ascii").strip()
    decoded = zlib.decompress(base64.b64decode(packed, validate=True))
    ids = set(decoded.decode("utf-8").splitlines())
    if len(ids) != 766:
        raise ValueError(f"Unexpected selection of EPG channels: {len(ids)}")
    return ids


def parse_input(wanted, beginning, latest):
    channels = {}
    programmes = []
    with gzip.open(INPUT, "rb") as xml:
        for _, elem in etree.iterparse(
            xml, events=("end",), tag=("channel", "programme"),
            no_network=True, resolve_entities=False, load_dtd=False
        ):
            if elem.tag == "channel":
                id_ = elem.get("id")
                if id_ in wanted:
                    channels[id_] = etree.tostring(elem, encoding="utf-8")
            else:
                id_ = elem.get("channel")
                if id_ in wanted:
                    try:
                        start = datetime.strptime(elem.get("start"), "%Y%m%d%H%M%S %z")
                        stop = datetime.strptime(elem.get("stop"), "%Y%m%d%H%M%S %z")
                    except (TypeError, ValueError):
                        pass
                    else:
                        if start < latest and stop > beginning:
                            programmes.append(
                                (start, id_, etree.tostring(elem, encoding="utf-8"))
                            )
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
    return channels, programmes


def choose_xml(channels, programmes, day_begin):
    header = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<tv generator-info-name="SS IPTV EPG (manual upload)">'
    )
    for horizon_hours in (72, 60, 48, 42, 36, 30, 27, 24, 18, 12):
        cutoff = day_begin + timedelta(hours=horizon_hours)
        eligible = [(channel, raw) for start, channel, raw in programmes if start < cutoff]
        ids_in_guide = {channel for channel, _ in eligible}
        body = b"".join(channels[id_] for id_ in sorted(ids_in_guide) if id_ in channels)
        programs = b"".join(raw for _, raw in eligible)
        xml = header + body + programs + b"</tv>\n"
        if len(xml) <= MAX_BYTES and len(eligible) >= 100 and len(ids_in_guide) >= 25:
            return xml, len(eligible), len(ids_in_guide), horizon_hours
    raise RuntimeError("No suitable XMLTV data fitting the 4.5MB limit")


def main():
    if not INPUT.exists():
        raise FileNotFoundError(
            "Upload input/epg-lite.xml.gz from your browser; no direct provider requests"
        )
    wanted = selected_channels()
    now = datetime.now(LOCAL_TZ)
    day_begin = datetime.combine(now.date(), time.min, LOCAL_TZ)
    channels, programmes = parse_input(wanted, day_begin, day_begin + timedelta(days=3))
    if not any(start.astimezone(LOCAL_TZ).date() == day_begin.date() for start, _, _ in programmes):
        raise RuntimeError(f"Source XMLTV has no programmes for {now.date()} (outdated?)")
    xml, count, n_channels, hours = choose_xml(channels, programmes, day_begin)
    etree.fromstring(xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(xml)
    (OUTPUT.parent / "index.html").write_text(
        '<!doctype html><html lang="ru"><meta charset="utf-8">'
        '<title>SS IPTV EPG</title><body><a href="epg.xml">EPG XMLTV</a></body></html>\n',
        encoding="utf-8",
    )
    print(
        f"Published EPG: {len(xml)} bytes, {n_channels} channels, "
        f"{count} programmes, horizon {hours} hours from today's midnight"
    )


if __name__ == "__main__":
    main()
