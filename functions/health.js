export function onRequestGet() {
  return new Response('ss-iptv-pages-functions-ok\n', {
    status: 200,
    headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' }
  });
}
