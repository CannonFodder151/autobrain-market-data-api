import os
import hmac
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from providers import search_listings

APP_VERSION = "1.2.0"

_API_KEY = os.getenv("API_KEY", "")
_API_KEY_FILE = os.getenv("API_KEY_FILE", "")
if not _API_KEY and _API_KEY_FILE:
    _p = Path(_API_KEY_FILE)
    if _p.is_file():
        _API_KEY = _p.read_text(encoding="utf-8").strip()
API_KEY = _API_KEY

ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
docs_url_open = "/docs" if ENVIRONMENT != "production" else None
redoc_url_open = None if ENVIRONMENT == "production" else None
openapi_url_open = None if ENVIRONMENT == "production" else "/openapi.json"

app = FastAPI(
    title="Market Data API",
    version=APP_VERSION,
    docs_url=docs_url_open,
    redoc_url=redoc_url_open,
    openapi_url=openapi_url_open,
)

RATE_LIMIT_IP = os.getenv("RATE_LIMIT_IP", "30/minute")
RATE_LIMIT_KEY = os.getenv("RATE_LIMIT_KEY", "120/minute")

TRUSTED_NETWORKS = [
    ipaddress.ip_network(p.strip(), strict=False)
    for p in os.getenv("TRUSTED_PROXIES", "").split(",")
    if p.strip()
]

import ipaddress as _ipaddress


def _client_ip(request: Request) -> str:
    peer = get_remote_address(request)
    fwd = request.headers.get("x-forwarded-for")
    if TRUSTED_NETWORKS and fwd:
        try:
            peer_ip = _ipaddress.ip_address(peer)
        except ValueError:
            return peer
        if any(peer_ip in net for net in TRUSTED_NETWORKS):
            for hop in reversed([h.strip() for h in fwd.split(",")]):
                try:
                    hop_ip = _ipaddress.ip_address(hop)
                except ValueError:
                    return hop
                if not any(hop_ip in net for net in TRUSTED_NETWORKS):
                    return hop
    return peer


def _api_key(request: Request) -> str:
    return request.headers.get("x-api-key") or "anon"


limiter = Limiter(key_func=_api_key, headers_enabled=True)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class SearchRequest(BaseModel):
    query: str = ""
    make: str = ""
    model: str = ""
    year: int | None = None
    vehicle_type: str = "car"


class SearchResponse(BaseModel):
    source: str
    listings: list[dict]
    note: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


@app.post("/search", response_model=SearchResponse)
@limiter.limit(RATE_LIMIT_IP, key_func=_client_ip)
@limiter.limit(RATE_LIMIT_KEY, key_func=_api_key)
async def search(
    request: Request, response: Response,
    req: SearchRequest, x_api_key: str | None = Header(None),
):
    if not API_KEY or not hmac.compare_digest(x_api_key or "", API_KEY):
        raise HTTPException(status_code=401, detail="invalid API key")
    query = (req.query or " ".join(x for x in (req.make, req.model) if x)).strip()
    if not query:
        raise HTTPException(status_code=400, detail="query or make/model required")
    vehicle_type = (req.vehicle_type or "car").lower()
    try:
        if vehicle_type in ("motorcycle", "bike", "motorbike"):
            from bikesguide import search_bikesguide
            return await search_bikesguide(query, req.year)
        from carsguide import search_carsguide
        return await search_carsguide(query, req.year)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"upstream error: {exc}")


class SCALookupRequest(BaseModel):
    rego: str = ""
    state: str = ""
    make: str = ""
    model: str = ""
    year: int | None = None


class SCALookupResponse(BaseModel):
    source: str
    vehicle: dict | None = None
    parts: list[dict] = []
    categories: list[dict] = []
    note: str | None = None


@app.post("/sca-parts", response_model=SCALookupResponse)
@limiter.limit(RATE_LIMIT_IP, key_func=_client_ip)
@limiter.limit(RATE_LIMIT_KEY, key_func=_api_key)
async def sca_parts(
    request: Request, response: Response,
    req: SCALookupRequest, x_api_key: str | None = Header(None),
):
    if not API_KEY or not hmac.compare_digest(x_api_key or "", API_KEY):
        raise HTTPException(status_code=401, detail="invalid API key")
    rego = (req.rego or "").strip()
    state = (req.state or "").upper()
    make = (req.make or "").strip()
    model = (req.model or "").strip()
    year = req.year
    try:
        from sca import search_sca
        result = await search_sca(
            rego=rego if rego else None, state=state if state else None,
            make=make, model=model, year=year,
        )
        return result
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"upstream error: {exc}")
