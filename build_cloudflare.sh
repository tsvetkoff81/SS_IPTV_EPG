#!/usr/bin/env bash
set -euo pipefail
# Cloudflare Pages: public EPG + public diagnostic test only; no subscriber IPTV streams.
python3 -m pip install --disable-pip-version-check --target "${PWD}/.cloudflare-epg-deps" -r requirements.txt
export PYTHONPATH="${PWD}/.cloudflare-epg-deps"
python3 build_epg.py
python3 prepare_cloudflare_m3u.py
test -s site/epg.xml
test -s site/bcu-epg-test.m3u
test -s site/_headers
# Optional private playlist is encrypted BEFORE being uploaded to the public repo.
# Only ciphertext goes into site; decryption happens at request time in a Pages Function.
if [ -s input/playlist.enc ]; then
  cp input/playlist.enc site/playlist.enc
  echo "Private playlist ciphertext copied; keys are Cloudflare secrets only."
fi
echo "Cloudflare Pages output ready: site/"
