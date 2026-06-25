import sys
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import httpx

if len(sys.argv) < 3:
    print("Usage: python proxy_server.py <target_port> <proxy_port>")
    sys.exit(1)

target_port = int(sys.argv[1])
proxy_port = int(sys.argv[2])
app = FastAPI()

# httpx Client
client = httpx.AsyncClient(base_url=f"http://127.0.0.1:{target_port}", follow_redirects=False)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy(request: Request, path: str):
    url = httpx.URL(path=request.url.path, query=request.url.query.encode("utf-8"))
    
    forward_headers = {}
    for k, v in request.headers.items():
        if k.lower() not in ["host", "content-length"]:
            forward_headers[k] = v

    req = client.build_request(
        request.method, 
        url, 
        headers=forward_headers, 
        content=request.stream()
    )
    
    try:
        r = await client.send(req, stream=True)
    except httpx.ConnectError:
        return StreamingResponse(iter(["Target server not reachable"]), status_code=502)

    headers = dict(r.headers)
    
    # Strip security headers that prevent iframe embedding
    headers.pop("x-frame-options", None)
    headers.pop("content-security-policy", None)
    
    # Handle Location headers for redirects (e.g. Spring Security redirect to /login)
    if "location" in headers:
        location = headers["location"]
        if f"127.0.0.1:{target_port}" in location:
            headers["location"] = location.replace(str(target_port), str(proxy_port))
        elif f"localhost:{target_port}" in location:
            headers["location"] = location.replace(str(target_port), str(proxy_port))

    # Remove Transfer-Encoding and Content-Encoding from httpx so FastAPI chunking doesn't clash
    headers.pop("transfer-encoding", None)
    headers.pop("content-encoding", None)

    return StreamingResponse(
        r.aiter_raw(),
        status_code=r.status_code,
        headers=headers,
        background=r.aclose
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=proxy_port)
