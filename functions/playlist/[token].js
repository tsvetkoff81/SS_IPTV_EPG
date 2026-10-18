/**
 * Authenticated personal M3U for SS IPTV.
 * The only playlist stored in PUBLIC GitHub is AES-256-GCM encrypted.
 * Both encryption key and access token live in encrypted Cloudflare Pages secrets.
 *
 * Playlist link: https://<project>.pages.dev/playlist/<IPTV_ACCESS_TOKEN>.m3u
 * NEVER publish the original unencrypted M3U, stream URLs, or secrets.
 */
function isAuthorized(context) {
  const supplied = String(context.params.token || "");
  const expected = String(context.env.IPTV_ACCESS_TOKEN || "");
  if (!expected || expected.length < 32) return false;
  return supplied === expected + ".m3u";
}

function base64ToBytes(input) {
  const decoded = atob(input);
  return Uint8Array.from(decoded, ch => ch.charCodeAt(0));
}

function headers() {
  return {
    "Content-Type": "application/x-mpegurl; charset=utf-8",
    "Cache-Control": "private, no-store, max-age=0",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  };
}

export async function onRequest(context) {
  const method = context.request.method;
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    return new Response("Method not allowed", { status: 405 });
  }
  if (!isAuthorized(context)) {
    return new Response("Not found", { status: 404, headers: {"Cache-Control": "no-store"} });
  }
  if (method === "OPTIONS") {
    return new Response(null, { status: 204, headers: headers() });
  }
  if (method === "HEAD") {
    return new Response(null, { status: 200, headers: headers() });
  }

  const key = context.env.IPTV_AES_KEY;
  if (!key) {
    return new Response("Cloudflare secret IPTV_AES_KEY is not configured", { status: 503 });
  }

  try {
    const assetURL = new URL("/playlist.enc", context.request.url);
    const encryptedResponse = await context.env.ASSETS.fetch(
      new Request(assetURL.toString(), { method: "GET" })
    );
    if (!encryptedResponse.ok) {
      return new Response("Encrypted playlist has not been uploaded", { status: 503 });
    }
    const encrypted = new Uint8Array(await encryptedResponse.arrayBuffer());
    if (encrypted.byteLength < 29) {
      return new Response("Invalid encrypted playlist", { status: 503 });
    }
    const cipherKeyBytes = base64ToBytes(key);
    if (cipherKeyBytes.length !== 32) {
      return new Response("Invalid key configuration", { status: 503 });
    }
    const cipherKey = await crypto.subtle.importKey(
      "raw", cipherKeyBytes, { name: "AES-GCM" }, false, ["decrypt"]
    );
    const plain = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: encrypted.subarray(0, 12), tagLength: 128 },
      cipherKey,
      encrypted.subarray(12)
    );
    return new Response(plain, { status: 200, headers: headers() });
  } catch (_error) {
    // Do not leak decrypt or provider credentials to visitors or logs.
    return new Response("Playlist temporarily unavailable", { status: 503 });
  }
}
