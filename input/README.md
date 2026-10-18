# Upload new guide here

Upload ONLY `epg-lite.xml.gz` downloaded from the provider through your browser.

Do not upload IPTV playlists, stream URLs, passwords, tokens, or screenshots of IPTV account details.

Workflow `Publish SS IPTV EPG` runs after any commit that changes `input/epg-lite.xml.gz`, then creates a standalone XMLTV (<=4.5 MB) on GitHub Pages.

For an update: open this folder in GitHub, click **Add file > Upload files**, drag `epg-lite.xml.gz`, commit to `main`, and verify both GitHub Actions jobs are green.

Your TV does not read this compressed file. It reads the generated public address:
https://tsvetkoff81.github.io/SS_IPTV_EPG/epg.xml

The published programme is only as current as the latest uploaded snapshot.
