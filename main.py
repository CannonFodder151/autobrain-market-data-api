import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from providers import search_listings

app = FastAPI(title="Market Data API", version="1.0.0")

API_KEY = os.getenv("API_KEY", "")


class SearchRequest(BaseModel):
    query: str = ""
    make: str = ""
    model: str = ""
    year: Optional[int] = None


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/search")
async def search(req: SearchRequest, x_api_key: Optional[str] = Header(None)):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid API key")
    try:
        result = await search_listings(
            query=req.query,
            make=req.make,
            model=req.model,
            year=req.year,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"upstream error: {exc}")
    return result
