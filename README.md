# AutoBrain Market Data API

Self-hosted CarsGuide/CarSales market-data scraper for AutoBrain car
valuations. Mirrors the `rego-lookup-api` deployment pattern: a tiny FastAPI
service behind an API key, never called directly by clients — only the
AutoBrain backend talks to it (via `MARKET_DATA_URL` + `MARKET_DATA_API_KEY`).

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | none | Liveness check |
| POST | `/search` | API key | Search live CarsGuide + CarSales listings |

### POST /search

Request:

```json
{ "query": "toyota crown", "make": "toyota", "model": "crown", "year": 1997 }
```

`year` is optional. When set, listings are filtered to `year ± 5`.

Auth: `X-API-Key: <key>` header.

Response (alias-resilient — the AutoBrain backend parses this shape):

```json
{
  "source": "combined",
  "listings": [
    {
      "title": "1997 Toyota Crown Royal Saloon",
      "price": 15000,
      "year": 1997,
      "odometer_km": 120000,
      "source": "carsguide",
      "url": "https://www.carsguide.com.au/car/..."
    }
  ]
}
```

Aggregates (median / low / high / sample_size) are computed server-side by the
AutoBrain backend.

## Providers

- **CarsGuide** — hits the public AutoTrader listings API
  (`listings.platform.autotrader.com.au/api/v3/search`) that the CarsGuide
  search UI itself uses. JSON, no rendering.
- **CarSales** — fetches the server-rendered search results page
  (`carsales.com.au/cars/{make}/{model}/`) and parses the listing cards.

Both send a desktop browser `User-Agent`; no headless browser required.

## Configuration

| Env | Description |
|---|---|
| `API_KEY` | Shared secret the backend sends as `X-API-Key` |

## Run

```bash
docker build -t market-data-api .
docker run -p 8012:8000 -e API_KEY=changeme market-data-api
```

## Deploy

`main` push builds `ghcr.io/cannonfodder151/market-data-api:<tag>` and
`cannonfodder151/market-data-api:<tag>` and auto-redeploys the Portainer stacks
(`market-data` on endpoint 5 AutoBrain-Hosted and endpoint 2 dev tier).
