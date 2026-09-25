"""Standalone local Playwright render service (replaces Rendex).

Run on a separate machine (exposed via ngrok):

    pip install -r requirements-renderer.txt
    playwright install chromium
    python render_service.py
    # or: uvicorn render_service:app --host 0.0.0.0 --port 11435

Endpoint:
    POST /render  (Content-Type: text/html, raw HTML in body)
    -> 200 image/png (raw PNG bytes, 1080x1350 viewport)
    -> 500 text/plain on failure
"""

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.concurrency import run_in_threadpool
from playwright.sync_api import sync_playwright

app = FastAPI(title="StudyReel Render Service")


def _do_render(html: str) -> bytes:
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            page = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
            page.set_content(html, wait_until="networkidle")
            page.wait_for_timeout(500)
            png = page.screenshot(type="png")
            return png
        finally:
            b.close()


@app.post("/render")
async def render(request: Request) -> Response:
    raw = await request.body()
    html_len = len(raw)
    print(
        f"[render-service] POST /render: {html_len} bytes, "
        f"content-type={request.headers.get('content-type')}",
        flush=True,
    )
    if not raw:
        msg = "empty HTML body"
        print(f"[render-service] 500: {msg}", flush=True)
        return Response(content=msg, media_type="text/plain", status_code=500)
    try:
        html = raw.decode("utf-8")
    except Exception as exc:
        msg = f"body is not valid utf-8 html: {exc}"
        print(f"[render-service] 500: {msg}", flush=True)
        return Response(content=msg, media_type="text/plain", status_code=500)
    if not html.strip():
        msg = "empty HTML body"
        print(f"[render-service] 500: {msg}", flush=True)
        return Response(content=msg, media_type="text/plain", status_code=500)

    try:
        png_bytes = await run_in_threadpool(_do_render, html)
        print(f"[render-service] 200: rendered {len(png_bytes)} bytes PNG", flush=True)
        return Response(content=png_bytes, media_type="image/png")
    except Exception as exc:
        msg = f"render failed: {exc}"
        print(f"[render-service] 500: {msg}", flush=True)
        return Response(content=msg, media_type="text/plain", status_code=500)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "render-service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=11435)
