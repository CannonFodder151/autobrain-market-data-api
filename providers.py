import asyncio
import re

import httpx

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

YEAR_WINDOW = 5


def _clean_price(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else None


def _clean_km(text: str | None) -> int | None:
    if not text:
        return None
    m = re.match(r"([\d,]+)", text.strip())
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


async def _carsguide(make: str, model: str, query: str, year: int | None) -> list[dict]:
    """CarsGuide listings via the public AutoTrader listings API."""
    params = {"source": "CG", "paginate": 50, "sortBy": "listing_updated", "orderBy": "desc"}
    if make and model:
        params["make"] = make
        params["model"] = model
    elif query:
        params["q"] = query
    if year:
        params["year_from"] = year - YEAR_WINDOW
        params["year_to"] = year + YEAR_WINDOW
    async with httpx.AsyncClient(timeout=45, headers={"User-Agent": UA}) as client:
        resp = await client.get(
            "https://listings.platform.autotrader.com.au/api/v3/search", params=params
        )
        resp.raise_for_status()
        data = resp.json()
    listings = []
    for raw in (data.get("data") or []):
        s = raw.get("_source") or {}
        price = (s.get("price") or {}).get("advertised_price")
        y = s.get("manu_year")
        if year and y:
            lo, hi = year - YEAR_WINDOW, year + YEAR_WINDOW
            if not (lo <= y <= hi):
                continue
        listings.append({
            "title": f"{y} {s.get('make','')} {s.get('model','')} {s.get('variant','')}".strip()
            if y else f"{s.get('make','')} {s.get('model','')} {s.get('variant','')}".strip(),
            "price": price,
            "year": y,
            "odometer_km": s.get("odometer"),
            "source": "carsguide",
            "url": f"https://www.carsguide.com.au/{s['url']}" if s.get("url") else "",
        })
    return listings


def _parse_carsales_cards(html: str) -> list[dict]:
    """Parse server-rendered CarSales search results into listing dicts."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("/cars/details/"):
            continue
        base = href.split("?")[0]
        if base in seen:
            continue
        seen.add(base)
        card = a.find_parent(class_=lambda c: c and "k1c10j0" in c) or a.parent
        title = None
        for sp in card.find_all("span"):
            if "line-clamp" in (sp.get("style") or ""):
                title = sp.get_text(strip=True)
                break
        price = None
        for sp in card.find_all("span"):
            t = sp.get_text(strip=True)
            if t.startswith("$") and re.match(r"^\$[\d,]+$", t):
                price = _clean_price(t)
                break
        km = None
        for t in card.find_all("title"):
            txt = t.get_text(strip=True)
            if re.match(r"^[\d,]+ km$", txt):
                km = _clean_km(txt)
                break
        out.append({
            "title": title or "",
            "price": price,
            "year": None,
            "odometer_km": km,
            "source": "carsales",
            "url": f"https://www.carsales.com.au{base}",
        })
    return out


async def _carsales(make: str, model: str, query: str, year: int | None) -> list[dict]:
    """CarSales listings via the server-rendered search results page."""
    if make and model:
        path = f"/cars/{make}/{model}/"
    elif query:
        path = f"/cars/?q={query.replace(' ', '+')}"
    else:
        return []
    async with httpx.AsyncClient(timeout=45, headers={
        "User-Agent": UA,
        "Accept-Language": "en-AU,en;q=0.9",
    }, follow_redirects=True) as client:
        resp = await client.get(f"https://www.carsales.com.au{path}")
        resp.raise_for_status()
        html = resp.text
    listings = _parse_carsales_cards(html)
    for lst in listings:
        m = re.match(r"^(\d{4})\s+", lst["title"] or "")
        lst["year"] = int(m.group(1)) if m else None
    if year:
        listings = [l for l in listings if l["year"] and abs(l["year"] - year) <= YEAR_WINDOW]
    return listings


async def search_listings(query: str, make: str, model: str, year: int | None) -> dict:
    make = (make or "").strip().lower()
    model = (model or "").strip().lower()
    query = (query or "").strip()
    cg, cs = await asyncio.gather(
        _carsguide(make, model, query, year),
        _carsales(make, model, query, year),
    )
    listings = cg + cs
    return {"source": "combined", "listings": listings}
