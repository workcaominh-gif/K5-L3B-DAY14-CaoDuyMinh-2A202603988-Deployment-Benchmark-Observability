# Deployment Information

## Public URL
https://k5-l3b-day14-caoduyminh-2a202603988-deployment-b-production.up.railway.app

## Platform
Railway. Project created as an Empty Project, then a GitHub Repository service was attached pointing at this fork's `main` branch with **Root Directory = `06-lab-complete`** (so Railway builds from `06-lab-complete/Dockerfile`, per `railway.toml`). A managed Redis database was added in the same Railway project and linked to the agent via the `REDIS_URL` variable reference (`${{Redis.REDIS_URL}}`), so the connection string is never hardcoded.

## Test Commands

### Health Check
```bash
curl https://k5-l3b-day14-caoduyminh-2a202603988-deployment-b-production.up.railway.app/health
# Returns: {"status":"ok"}
```

### Readiness Check
```bash
curl https://k5-l3b-day14-caoduyminh-2a202603988-deployment-b-production.up.railway.app/ready
# Returns: 200 while Redis is reachable (503 if Redis goes down, verified locally in CP5)
```

### API Test (with authentication)
```bash
curl -X POST https://k5-l3b-day14-caoduyminh-2a202603988-deployment-b-production.up.railway.app/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

### CP6 self-test (CHECKPOINTS.md), run against the live URL above

```bash
BASE="https://k5-l3b-day14-caoduyminh-2a202603988-deployment-b-production.up.railway.app"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # → 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # → 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # → 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # → 200
```

Real output captured at deploy time (key redacted) is saved at [screenshots/test.txt](screenshots/test.txt): `200 / 200 / 401 / 200`, matching the checkpoint exactly.

## Environment Variables Set (on Railway, not committed)
- `AGENT_API_KEY` — generated secret, set via the Railway dashboard's Raw Editor
- `REDIS_URL` — Railway variable reference `${{Redis.REDIS_URL}}`, resolved to the managed Redis instance in the same project
- `ENVIRONMENT=production`
- `RATE_LIMIT_PER_MINUTE=60`
- `DAILY_BUDGET_USD=5`
- `MONTHLY_BUDGET_USD=100`

`PORT` is injected automatically by Railway; the Dockerfile's `CMD` already reads `${PORT:-8000}` so no extra variable was needed for it.

## Screenshots
- [Railway project dashboard](screenshots/dashboard.png) — agent service (Online) + Redis service, variable link shown on canvas
- [Service running](screenshots/running.png) — live `/health` response in-browser
- [Self-test results](screenshots/test.txt) — the 4-command CP6 self-test, real HTTP codes
