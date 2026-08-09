# Local SearXNG

This instance is intentionally bound to `127.0.0.1` and is not a public
search service. The local bot limiter is disabled to avoid false 429s from
same-machine calls; the project adapter still enforces a one-second delay. It
provides the second-layer Web retrieval path for the local
XZD API.

Before starting the stack, copy `.env.example` to `.env` and replace
`SEARXNG_SECRET` with a locally generated random value. The secret is injected
at startup and is intentionally not stored in the tracked `settings.yml`.

## Start

From this directory:

```powershell
docker compose up -d
docker compose ps
```

## Verify JSON search

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8080/search?q=柔性电子器件&format=json"
```

The response must contain a top-level `results` array with `title`, `url`,
and optionally `content`, `publishedDate`, or `engine`.

## Stop

```powershell
docker compose down
```

The named volumes are retained by default so the service can be restarted
without losing its cache. Use `docker compose down -v` only when the local
SearXNG cache and Valkey data can be discarded.
