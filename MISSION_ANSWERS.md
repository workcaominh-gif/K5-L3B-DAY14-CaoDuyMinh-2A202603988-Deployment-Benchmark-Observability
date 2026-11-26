# MISSION_ANSWERS — Day 14 (K5, cá nhân)

# Mission Answers — CP1, CP2, CP3, CP4, CP6

(CP5/CP7/CP8 and `06-lab-complete/`, `benchmark-observability/` content were produced by a different pass — not rewritten here.)

---

## Part 3 — Cloud Deployment (CP6)

### Deploy thật trên Railway

Agent Part 6 (`06-lab-complete/`) deploy trên **Railway**, không phải app mẫu `03-cloud-deployment/`.

- Tạo project rỗng trên Railway, gắn service từ GitHub repo fork, đặt **Root Directory = `06-lab-complete`** (Railway build bằng chính `06-lab-complete/Dockerfile` theo `railway.toml`).
- Thêm Redis managed trên cùng project; biến `REDIS_URL` của agent trỏ bằng tham chiếu Railway `${{Redis.REDIS_URL}}`, không gõ tay connection string.
- Đặt `AGENT_API_KEY` (random, sinh bằng `secrets.token_urlsafe`), `ENVIRONMENT=production`, `RATE_LIMIT_PER_MINUTE=60`, `DAILY_BUDGET_USD=5`, `MONTHLY_BUDGET_USD=100` qua Railway Dashboard (Raw Editor), không commit giá trị thật — xem `.env.example` trong `06-lab-complete/`.
- URL public: **https://k5-l3b-day14-caoduyminh-2a202603988-deployment-b-production.up.railway.app**

4 lệnh tự kiểm CP6 chạy thật trên URL trên (xem [DEPLOYMENT.md](DEPLOYMENT.md), [screenshots/test.txt](screenshots/test.txt)):

```
GET  /health                         → 200
GET  /ready                          → 200
POST /ask (không có X-API-Key)       → 401
POST /ask (có X-API-Key đúng)        → 200
```

Khớp đúng 4 kết quả CHECKPOINTS.md yêu cầu — agent đang chạy thật trên cloud, có Redis, có auth.

### So sánh `railway.toml` với `render.yaml` (06-lab-complete/)

| | `railway.toml` | `render.yaml` |
| --- | --- | --- |
| Build | `builder = "DOCKERFILE"` trỏ thẳng `Dockerfile` trong cùng thư mục | `runtime: docker` + `dockerfilePath`/`dockerContext` trỏ vào `06-lab-complete/` từ gốc repo (vì Render Blueprint đọc từ gốc repo, không phải từ root directory như Railway) |
| Redis | Không khai báo trong file — phải tự thêm Redis service qua Dashboard hoặc CLI rồi set biến `REDIS_URL` thủ công (đây là việc nhóm đã làm ở Railway) | Khai báo Redis ngay trong blueprint (`type: redis`, `name: agent-cache`) và nối `REDIS_URL` bằng `fromService` — toàn bộ hạ tầng (web + Redis) tạo trong một lần "New → Blueprint" |
| Secret `AGENT_API_KEY` | Đặt qua `railway variables set` (ngoài file, không commit) | Đặt `generateValue: true` ngay trong file — Render tự sinh giá trị random, không ai (kể cả người viết file) nhìn thấy giá trị |
| Healthcheck | `healthcheckPath = "/health"`, `healthcheckTimeout = 30`, có `restartPolicy` riêng (`ON_FAILURE`, tối đa 3 lần) | `healthCheckPath: /health` — Render tự rollback/restart khi fail, không có tham số retry riêng trong file |
| Biến môi trường thường (không phải secret) | Không khai báo trong file — set qua Dashboard/CLI mỗi lần | Khai báo thẳng trong `envVars` (`ENVIRONMENT`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`) — tái lập được chỉ bằng file, không cần nhớ set tay |

Tóm lại: `render.yaml` là Infrastructure-as-Code đầy đủ hơn (cả Redis, cả biến môi trường không-nhạy-cảm đều nằm trong file, chỉ secret là `generateValue`), còn `railway.toml` chỉ khai báo phần build/deploy của riêng service agent — phần hạ tầng còn lại (Redis, biến môi trường) phải làm tay trên Dashboard, đúng như nhóm đã làm thật ở trên.

### Exercise 3.3 — Cloud Run (chỉ đọc, không deploy)

`cloudbuild.yaml` định nghĩa pipeline 4 bước chạy tự động mỗi khi push lên `main`: (1) cài dependency và chạy `pytest` — build dừng ngay nếu test đỏ; (2) `docker build` image gắn tag theo `$COMMIT_SHA` và `latest`, tận dụng `--cache-from` để build nhanh hơn ở các lần sau; (3) push cả hai tag lên Container Registry; (4) deploy lên Cloud Run bằng chính image vừa push. `service.yaml` là phần mô tả hạ tầng đích dạng Knative: `minScale: 1` giữ sẵn một instance để tránh cold start, `maxScale: 10` giới hạn chi phí, mỗi instance nhận tối đa 80 request đồng thời (`containerConcurrency: 80`) — tách bạch rõ "pipeline build gì" (cloudbuild.yaml) khỏi "hạ tầng chạy thế nào" (service.yaml), giống tinh thần `railway.toml`/`render.yaml` nhưng tường minh hơn về scaling.

---

## Part 1 — Localhost vs Production (CP1)

### Real call to the `develop` app

Started with `cd 01-localhost-vs-production/develop && python3 -m venv .venv && pip install -r requirements.txt && python app.py`, then:

```
$ curl -X POST "http://localhost:8000/ask?question=Hello"
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Server log for that request (note the secret key being printed straight to stdout):

```
INFO:     Will watch for changes in these directories: [...develop']
INFO:     Uvicorn running on http://localhost:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [62400] using WatchFiles
Starting agent on localhost:8000...
INFO:     Started server process [62451]
INFO:     Application startup complete.
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
[DEBUG] Response: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.
INFO:     127.0.0.1:51669 - "POST /ask?question=Hello HTTP/1.1" 200 OK
```

### Real anti-patterns found in `01-localhost-vs-production/develop/app.py`

1. **Hardcoded secrets in source code**
   ```python
   OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"
   DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"
   ```
   If this file is pushed to a public repo, the key and DB credentials leak immediately — and git history keeps them even after a later "fix."

2. **Secret leaked into logs via `print`**
   ```python
   print(f"[DEBUG] Using key: {OPENAI_API_KEY}")  # ❌ log ra secret!
   ```
   Confirmed live in the captured server log above (`[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this`). Any log aggregator (Datadog, CloudWatch, etc.) now stores the real key.

3. **`print()` instead of structured logging**
   ```python
   print(f"[DEBUG] Got question: {question}")
   ...
   print(f"[DEBUG] Response: {response}")
   ```
   No log levels, no timestamps/JSON structure, can't be filtered/shipped reliably, and can't be turned off per-environment.

4. **No health-check endpoint** — only `/` and `/ask` exist. There's no `/health` or `/ready`, so a platform (Railway/Render/K8s) has no way to know if the process is alive or ready to receive traffic; a hung process just keeps "running."

5. **Debug/reload mode + hardcoded host/port — not container/cloud friendly**
   ```python
   uvicorn.run(
       "app:app",
       host="localhost",   # ❌ chỉ chạy được trên local
       port=8000,          # ❌ cứng port
       reload=True         # ❌ debug reload trong production
   )
   ```
   `host="localhost"` means the server only accepts loopback connections — inside a Docker container this makes it unreachable from outside the container. `reload=True` watches the filesystem and restarts the worker on every file change, which is CPU overhead and instability you never want in prod. The port is hardcoded instead of read from the `PORT` env var that platforms like Railway/Render inject.

6. **No config management via environment variables** (bonus 6th finding)
   ```python
   DEBUG = True
   MAX_TOKENS = 500
   ```
   These are compile-time constants, not env-driven settings — can't change behavior per environment (dev/staging/prod) without editing and redeploying code.

7. **No graceful shutdown handling** — there is no `SIGTERM` handler and no lifespan/shutdown hook, so in-flight requests can be cut off mid-response when the container is stopped/rescheduled.

### Develop vs Production comparison table

| Aspect | `develop/app.py` | `production/app.py` + `config.py` | Why it matters |
|---|---|---|---|
| Secrets | Hardcoded `OPENAI_API_KEY`, `DATABASE_URL` in source | Loaded via `config.py` → `pydantic`-style `settings` object, sourced from environment variables | Hardcoded secrets leak via git/logs; env-based config keeps secrets out of source control |
| Logging | `print()` statements, including one that prints the secret key | `logging` module, structured JSON format (`'{"time":...,"level":...,"msg":...}'`), never logs secrets | JSON logs are parseable by log aggregators (Datadog/Loki); printing secrets is a security incident waiting to happen |
| Health check | None | `GET /health` (liveness: uptime, version, timestamp) | Platforms restart a crashed/stuck container only if they can detect via a health endpoint |
| Readiness | None | `GET /ready` (returns 503 until `is_ready` flag is set during startup) | Load balancers must not route traffic to an instance that hasn't finished initializing |
| Graceful shutdown | None — process just dies on SIGTERM/SIGKILL | `signal.signal(signal.SIGTERM, handle_sigterm)` + `lifespan` shutdown block that logs and sleeps briefly before exiting | Lets in-flight requests finish instead of being dropped when the platform reschedules/kills the container |
| Host binding | `host="localhost"` (loopback only) | `host=settings.host` → `0.0.0.0` | `0.0.0.0` is required so traffic from outside the container (or from a reverse proxy) can reach the process |
| Port | Hardcoded `8000` | `port=settings.port` sourced from `PORT` env var | Cloud platforms (Railway/Render) inject their own `PORT`; hardcoding breaks deployment |
| Debug / reload | `reload=True` always on | `reload=settings.debug` — only true when `DEBUG` env var says so | `reload=True` in production wastes CPU watching the filesystem and can cause instability |
| CORS | Not configured | `CORSMiddleware` with `allow_origins=settings.allowed_origins` | Prevents arbitrary origins from calling the API from a browser |
| Metrics | None | `GET /metrics` (uptime, env, version) | Lets Prometheus-style scraping monitor the service |
| Config source | Python literals (`DEBUG = True`, `MAX_TOKENS = 500`) | `config.py` `settings` object reading from env | 12-factor apps change behavior per environment without code changes |

---

## Part 2 — Docker (CP2)

Built both images **from the repo root** (not `cd`-ing into the subfolder), exactly as README note #4 requires:

```
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
```

Both builds completed successfully (`DONE` on final layer, image IDs written).

### Exercise 2.1 answers (reading `02-docker/develop/Dockerfile`)

1. **Base image:** `python:3.11` — the full Python distribution (~1 GB), not the slim variant.
2. **Working directory:** `WORKDIR /app` — all subsequent `COPY`/`RUN` operate relative to `/app` inside the container.
3. **Why `COPY requirements.txt` before `COPY app.py`:** Docker caches each layer. If `requirements.txt` is copied and `pip install` run *before* the application source is copied, then changing only the app code (not dependencies) on a rebuild reuses the cached dependency-install layer instead of re-running `pip install` — much faster rebuilds. If source were copied first, any code change would invalidate the cache for everything after it, including the slow `pip install` step.
4. **CMD vs ENTRYPOINT:** `CMD` sets the *default* command/arguments for the container, but it can be fully overridden by whatever is passed after the image name on `docker run` (e.g. `docker run my-image bash` ignores the Dockerfile's `CMD`). `ENTRYPOINT` sets a fixed executable that always runs; anything passed on `docker run` is appended as arguments to it rather than replacing it. This Dockerfile uses `CMD ["python", "app.py"]`, so a user can override the whole command if needed, whereas an `ENTRYPOINT` would lock the container to always execute that program.

### Container run + call confirmation (real output)

Develop container (`docker run -d -p 8000:8000 my-agent:develop`):
```
$ curl -X POST "http://localhost:8000/ask?question=Hello"
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Production/advanced container (`docker run -d -p 8001:8000 my-agent:advanced`, uses JSON body per its own `main.py`):
```
$ curl http://localhost:8001/health
{"status":"ok","uptime_seconds":3.2,"version":"2.0.0","timestamp":"2026-11-26T07:49:23.594061"}

$ curl -X POST http://localhost:8001/ask -H "Content-Type: application/json" -d '{"question": "What is Docker?"}'
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

Both containers were stopped and removed immediately after (`docker stop`/`docker rm`) to free ports.

### Real measured image sizes

```
$ docker images my-agent --format "{{.Repository}}:{{.Tag}}\t{{.Size}}"
my-agent:advanced   188MB
my-agent:develop    1.17GB

$ docker inspect my-agent:develop  --format='{{.Size}}'   → 1,169,510,072 bytes
$ docker inspect my-agent:advanced --format='{{.Size}}'   →   188,415,952 bytes
```

**% difference (computed from real bytes, not copied from README):**

```
(1,169,510,072 − 188,415,952) / 1,169,510,072 × 100 ≈ 83.9%
```

The multi-stage production image is **~83.9% smaller** than the single-stage develop image (≈ 981 MB saved). This comes from: (a) `python:3.11-slim` base vs full `python:3.11` in Stage 2's runtime image, and (b) the Stage 1 "builder" layer (which contains `gcc`, `libpq-dev`, pip caches, build tooling) never being copied into the final runtime image — only the installed `site-packages` under `/root/.local` are copied over.

### Exercise 2.4 — Compose stack through Nginx

Per README note #5, created the missing env file first: `touch 02-docker/production/.env.local`.

Ran: `docker compose -p k5-day14-docker up -d --build` inside `02-docker/production/`.

**Services started (from `docker-compose.yml`) and real `docker compose ps` output:**

```
NAME                       SERVICE   STATUS
k5-day14-docker-agent-1    agent     Up (health: starting → healthy)
k5-day14-docker-nginx-1    nginx     Up   (0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp)
k5-day14-docker-qdrant-1   qdrant    Up (healthy)
k5-day14-docker-redis-1    redis     Up (healthy)
```

**Stack diagram (text):**

```
                     ┌─────────────┐
   client (curl) ──► │   nginx     │  :80 published to host
                     │ (reverse    │  - rate limiting (10 r/s, burst 20)
                     │  proxy/LB)  │  - security headers
                     └──────┬──────┘
                            │ proxy_pass → upstream agent_backend
                            ▼
                     ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
                     │   agent     │ ───► │   redis     │      │   qdrant    │
                     │ (FastAPI,   │      │ (session/   │      │ (vector DB  │
                     │  depends_on │      │  rate-limit │      │  for RAG)   │
                     │  redis+     │      │  cache)     │      │             │
                     │  qdrant     │ ───────────────────────► │             │
                     │  healthy)   │                           └─────────────┘
                     └─────────────┘
   All four services share the "internal" bridge network.
   Only nginx publishes a port to the host (80/443); agent/redis/qdrant
   are reachable only from inside the internal network.
```

**Nginx test results (real curl -i output):**

```
$ curl -i http://localhost/health
HTTP/1.1 200 OK
Server: nginx
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"status":"ok","uptime_seconds":21.0,"version":"2.0.0","timestamp":"2026-11-26T07:51:52.158948"}

$ curl -i -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question": "Explain microservices"}'
HTTP/1.1 200 OK
Server: nginx
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Nginx correctly proxies to the agent container and injects the security headers defined in `nginx.conf`. Torn down afterward with `docker compose -p k5-day14-docker down` (containers, network all removed).

---

## Part 4 — API Gateway / Security (CP3)

### Develop app (API key auth) — real output

Started with `AGENT_API_KEY=secret-key-123 python app.py` in `04-api-gateway/develop/` (per README note #6).

```
$ curl -i -X POST -H "Content-Type: application/json" -d '{"question":"hello"}' http://localhost:8000/ask
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

$ curl -i -X POST -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d '{"question":"hello"}' http://localhost:8000/ask
HTTP/1.1 200 OK
{"question":"hello","answer":"Đây là câu trả lời từ AI agent (mock)..."}
```

Stopped the develop server before starting production (same port 8000).

### Production app (JWT + rate limit + cost guard) — real output

Installed `04-api-gateway/production/requirements.txt` in its own venv, started with `python app.py`.

**401 — no/bad token:**
```
$ curl -i -X POST -H "Content-Type: application/json" -d '{"question":"hello"}' http://localhost:8000/ask
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":"Authentication required. Include: Authorization: Bearer <token>"}
```

**Getting a real token** (per README note #6: `POST /auth/token` with `student`/`demo123`, NOT `/token` + `admin`/`secret` as `CODE_LAB.md` incorrectly states):
```
$ curl -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" \
       -d '{"username":"student","password":"demo123"}'
# → {"access_token":"<REDACTED>", "token_type":"bearer", "expires_in_minutes":60, ...}
```

**200 — valid token:**
```
$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer <REDACTED>" \
       -H "Content-Type: application/json" -d '{"question":"what is docker?"}'
HTTP/1.1 200 OK
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block

{"question":"what is docker?","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

**429 — rate limited** (looped the same token's `/ask` call >10 times inside one minute — the `student` account is capped at 10 req/min):
```
req 1  -> 200
req 2  -> 200
...
req 9  -> 200
req 10 -> 429
req 11 -> 429
...
req 15 -> 429
```
Full `-i` output of one 429:
```
$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer <REDACTED>" -H "Content-Type: application/json" -d '{"question":"one more"}'
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795679654
retry-after: 51

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":51}}
```

Server was killed afterward to free port 8000.

### Rate limit vs cost guard — two different protections

- **Rate limiting** (`rate_limiter.py`, enforced per-user with a sliding window, e.g. 10 req/min for `student`, 100 req/min for `teacher`) protects against *speed/abuse*: it stops one caller from hammering the API faster than the service (or the downstream LLM) can handle, regardless of how cheap or expensive each individual call is. It's a request-count-per-time-window check, independent of money.
- **Cost guard** (`cost_guard.py`) protects against *budget overrun*: it tracks actual token usage per user per day (`input_tokens`/`output_tokens` converted to USD via `PRICE_PER_1K_INPUT_TOKENS` / `PRICE_PER_1K_OUTPUT_TOKENS`) against a `daily_budget_usd` (per-user, e.g. $1/day) and a `global_daily_budget_usd` (e.g. $10/day total), raising an `HTTPException` once the budget is exhausted — even if the caller is well within their rate limit.
- **Why both are needed:** a user could stay under 10 requests/minute (passing rate limiting) but each request could ask for a huge, expensive completion — rate limiting alone wouldn't catch a surprise bill. Conversely, cost guard alone wouldn't stop someone from firing hundreds of cheap, tiny requests per second and overwhelming the server/LLM provider with raw request volume. Together they cover both the "too fast" axis and the "too expensive" axis.

---

## Part 5 — Scaling & Reliability (CP4)

Per README note #7, the production stack runs on **port 8080** with endpoint **`POST /chat`** (not port 80/`/ask`).

Ran `touch 05-scaling-reliability/production/.env.local` first, then:
```
docker compose -p k5-day14-scaling up -d --build --scale agent=3
```

**Blocker encountered and resolved:** host port 8080 was already bound by a *different* parallel agent's stack (`k5-day14-observability-nginx-1`, from the `06-lab-complete/benchmark-observability` work another agent was doing concurrently). To avoid touching that other agent's work, I temporarily edited only *this* file's nginx port mapping from `8080:80` to `8091:80`, ran the test against port 8091, then reverted the file back to `8080:80` immediately after tearing the stack down — so the committed file still matches the lab's documented port (8080).

Compose started 5 containers: 3× `agent` (replicas), 1× `redis`, 1× `nginx` (load balancer). All agent instances reported `healthy`.

**Real `python test_stateless.py` output** (sending 5 questions on one session):
```
Session ID: 41630afd-572e-42be-b510-d32bf7326a32

Request 1: [instance-a1ca1c]  Q: What is Docker?
Request 2: [instance-68e799]  Q: Why do we need containers?
Request 3: [instance-09fc97]  Q: What is Kubernetes?
Request 4: [instance-a1ca1c]  Q: How does load balancing work?
Request 5: [instance-68e799]  Q: What is Redis used for?
------------------------------------------------------------
Total requests: 5
Instances used: {'instance-68e799', 'instance-a1ca1c', 'instance-09fc97'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi...
  ... (all 5 Q/A pairs present)
✅ Session history preserved across all instances via Redis!
```

**Explanation of the result:** Nginx load-balances the 5 `/chat` requests across all 3 agent replicas round-robin (3 distinct `instance-*` IDs seen across only 5 requests, confirming more than one instance served the same logical session). Despite different containers handling different requests, `GET /chat/{session_id}/history` returns the complete, correctly-ordered 10-message history — because the agent code (`save_session`/`load_session` in `app.py`) stores session state in **Redis**, a shared store external to any single container, rather than in that container's own process memory. Any instance can read/write the same session key.

Torn down with `docker compose -p k5-day14-scaling down` to free the port.

### Liveness (`/health`) vs readiness (`/ready`), and why in-RAM state breaks with multiple instances

- **`/health` (liveness):** answers "is this process alive and not deadlocked?" It returns basic uptime/version/instance info and (when Redis is configured) whether that *specific instance's* Redis connection responds to `PING`. A platform/orchestrator polls this to decide whether to **restart** the container. It does not guarantee the service is ready to usefully serve traffic yet — just that the process hasn't crashed.
- **`/ready` (readiness):** answers "should the load balancer send this instance traffic right now?" In this app it actively checks `_redis.ping()` and raises `HTTPException(503, ...)` if Redis is unreachable. A load balancer (or Kubernetes) uses this to decide whether to **route** requests to the instance — an instance can be "alive" (passes `/health`) but not "ready" (fails `/ready`) during startup or if its dependency (Redis) is temporarily down, and should be pulled out of rotation without being killed.
- **Why in-RAM state breaks when scaled to multiple instances:** if session data were kept in each process's own memory (the fallback `_memory_store` dict used when `USE_REDIS` is false), then session A's data would exist only inside whichever single container handled the first request for that session. The moment Nginx load-balances a follow-up request for the same `session_id` to a *different* container (which is exactly what round-robin does, and what the test above demonstrated), that container's in-memory dict has no record of the session — the conversation history would appear to vanish or reset. Centralizing state in Redis (shared across all replicas) is what makes the agent *stateless* at the process level and therefore safely horizontally scalable; any instance can serve any request for any session.

---

# Part 6 — Production AI Agent — Kết quả

Scope: chỉ `06-lab-complete/` (các thư mục 01/02/04/05 và `benchmark-observability/` do agent khác xử lý, không chạm vào).

## Kết quả chấm

Chạy đầy đủ (build + run Docker image thật, Docker Desktop 24.0.7 / Compose v2.23.3):

```
python3 check_production_ready.py
```

**PASS 12/12 — PRODUCTION READY** (43/43 checks passed).

### 📋 Checklist Deliverable (output verbatim)

```
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

Docker build detail from that run: image built in 36s, final size **184 MB** (well under the 500 MB cap), `docker stop` exited cleanly in **0.5s** (well under 10s).

## What was implemented

- `app/config.py` — all settings (`PORT`, `ENVIRONMENT`, `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`, `MONTHLY_BUDGET_USD`) read from env vars with sane local defaults, no hard-coded secrets.
- `app/auth.py` — `verify_api_key` dependency using `APIKeyHeader("X-API-Key")`, constant-time compare, raises 401 on missing/wrong key.
- `app/redis_client.py` — lazy `redis.from_url(...)` client (no ping at import time, so the app still boots with Redis down); `redis_healthy()` pings and swallows `RedisError`.
- `app/rate_limiter.py` — Redis sorted-set sliding window (`ZREMRANGEBYSCORE` → `ZCARD` → `ZADD` → `EXPIRE`), 429 with `Retry-After` header when the per-key limit is exceeded; state survives agent restarts since it lives in Redis.
- `app/cost_guard.py` — per-day/per-month spend accumulated in Redis via `INCRBYFLOAT`; `check_budget()` raises 402 once spend ≥ `DAILY_BUDGET_USD` (or `MONTHLY_BUDGET_USD` if set); `record_cost()` adds the request's token cost after the LLM call.
- `app/main.py` — `/health` (always 200), `/ready` (503 when Redis unreachable), `/ask` wired as `Depends(verify_api_key)` → `check_rate_limit` → `check_budget` → LLM call → `record_cost`; a JSON-logging middleware (`log_json`) emits one JSON object per request (`ts/lvl/event/path/status/ms`); a `lifespan` context handles startup/shutdown logging (graceful shutdown itself relies on uvicorn's own SIGTERM handling, since the Dockerfile CMD execs uvicorn as PID 1).
- `Dockerfile` — multi-stage (`python:3.11-slim` builder → `python:3.11-slim` runtime), non-root `app` user, `HEALTHCHECK` hitting `/health` via stdlib `urllib`, `CMD ["sh","-c","exec uvicorn ... --port ${PORT:-8000} --workers 2"]` so uvicorn is PID 1 and receives `SIGTERM` directly.
- `docker-compose.yml` — `agent` (build from Dockerfile, port 8000, env vars with `${VAR:-default}` substitution from an optional `.env`) + `redis` (`redis:7-alpine` with a healthcheck); agent has `REDIS_URL=redis://redis:6379/0` and `depends_on: redis (condition: service_healthy)`. Note: the installed Compose version (v2.23.3) does not support the long-form `env_file: [{path, required}]` syntax, so instead we rely on Compose's built-in behavior of auto-loading an optional `.env` file in the project directory purely for `${VAR}` substitution — functionally equivalent and doesn't require `.env` to exist.
- `.dockerignore` — excludes `.env`/`.env.*` (keeps `.env.example`), `__pycache__/`, `venv/`/`.venv/`, `.git/`, docs, `benchmark-observability/`, the checker script.
- `.env.example` — lists all required vars with safe placeholder/default values.

## railway.toml / render.yaml

- **`railway.toml`**: `[build] builder = "DOCKERFILE"` (uses this directory's Dockerfile), `[deploy] healthcheckPath = "/health"` + restart policy. `PORT` comes from Railway automatically and is already handled by the Dockerfile's `CMD`, so no `startCommand` override is needed. Secrets (`AGENT_API_KEY`, `REDIS_URL`, etc.) are documented as `railway variables set ...`, never committed.
- **`render.yaml`**: one `type: web, runtime: docker` service pointing at this directory's Dockerfile (`dockerfilePath`/`dockerContext`), `healthCheckPath: /health`; plus a `type: redis` service, wired into the web service via `fromService` for `REDIS_URL`. `AGENT_API_KEY` uses `generateValue: true` (no plaintext secret in the file).

Both files were validated against the static checker's regexes (criterion 12) and pass.

## Blockers encountered (resolved)

- The host's default `python3` is **3.15**, for which no prebuilt wheel of `pydantic-core==2.9.0` exists and building from source failed (needs a newer `rustc` than installed). Worked around by creating a local `.venv` for this lab using the already-installed Homebrew `python3.11` to install `requirements.txt` and run `check_production_ready.py` — this doesn't affect the app/Docker image itself (Dockerfile builds on `python:3.11-slim`, unaffected by the host's Python version).
- Compose v2.23.3 doesn't support the long-form `env_file:` entry with `required: false` — switched to the `.env`-for-substitution approach described above, which satisfies the same "don't fail without a `.env` file" requirement.

All Docker containers/images created by the checker run were already cleaned up automatically by the script's own `atexit` handler (verified via `docker ps -a` / `docker images` afterward — nothing left behind).

---

# Mission Answers — Part 7 (Benchmark & Observability)

Tài liệu này trả lời các câu hỏi "Cần hiểu" / bài tập ở CP7 và CP8 của `CHECKPOINTS.md`, bổ sung cho các số liệu đã điền trong `BENCHMARK_REPORT.md`.

---

## 1. Exercise 7.3 — CI job / exit-code gating của `run_eval.py`

`eval/run_eval.py` được viết sẵn để dùng trong CI: ở cuối `main()` nó gọi

```python
raise SystemExit(0 if gate_ok else 1)
```

với `gate_ok = report["accuracy"] >= args.min_accuracy and not regressions`. Nghĩa là **process exit code** chính là kết quả của quality gate: `0` = PASS (accuracy đạt ngưỡng tối thiểu VÀ không có câu nào từ "đúng" (ở baseline) chuyển thành "sai"), `1` = FAIL.

Một CI pipeline (GitHub Actions) chặn merge bằng cách thêm một **step** chạy đúng lệnh này và để CI tự đọc exit code của step đó — không cần parse output. Ví dụ:

```yaml
jobs:
  quality-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r 06-lab-complete/benchmark-observability/develop/requirements.txt
      - name: Start agent v2 (background)
        run: |
          cd 06-lab-complete/benchmark-observability/develop
          AGENT_VERSION=v2 PORT=8002 nohup python app.py &
          sleep 3
      - name: Eval quality gate (so với baseline đã commit trong repo)
        run: |
          cd 06-lab-complete/benchmark-observability/develop
          python eval/run_eval.py --url http://localhost:8002 \
            --min-accuracy 0.95 \
            --baseline reports/eval_baseline.json \
            --out reports/eval_pr.json
        # Step FAIL (exit code 1) ⇒ job FAIL ⇒ GitHub coi check này là "failing"
```

Vì GitHub Actions tự fail một job khi bất kỳ step nào exit non-zero, chỉ cần đặt rule **branch protection: "Require status checks to pass before merging"** và chọn job `quality-gate` — khi `run_eval.py` trả `1` (accuracy dưới ngưỡng hoặc có regression so với baseline đã commit), check này đỏ và GitHub tự chặn nút Merge trên PR, không cần logic chặn merge viết tay. `--baseline` nên trỏ tới một file report đã được review và commit vào repo (ví dụ `eval_baseline.json` ở lần release ổn định gần nhất), để mọi PR sau đều so sánh với "phiên bản đang chạy production", không phải so với chính nó.

**Thử gọi với vai trò ngược lại:** chạy `python eval/run_eval.py --url http://localhost:8001 --baseline reports/eval_v2.json` (eval v1, baseline là v2) → vì v1 chỉ đạt 4.3% accuracy trong khi baseline v2 đạt 91.3%, hầu hết các câu v2 đã "đúng" giờ "sai" ở v1 ⇒ có `regressions` ⇒ `gate_ok = False` ⇒ `exit code = 1`. Đây đúng là hành vi mong muốn: nếu ai đó vô tình deploy nhầm bản v1 (hoặc revert code dẫn tới hành vi giống v1), CI sẽ chặn ngay.

---

## 2. Vì sao SLO nên đặt theo p95/p99, không theo trung bình

Latency trung bình là một con số "pha trộn" (blended) — nó cộng gộp số đông request nhanh với số ít request chậm bất thường rồi chia đều ra, nên vài request rất chậm chỉ kéo average lên một chút, trong khi percentile cao (p95, p99) trực tiếp trả lời "ngưỡng mà X% request tệ nhất đang chịu". Số liệu đo được trong lab minh hoạ rõ: khi `MOCK_SLOW_RATE` tăng từ 0 → 0.1 (10% request bị chậm thêm ~1.5s), **average** chỉ tăng từ 187.9ms lên 345.2ms (~1.8×) nhưng **p99** tăng từ 226.7ms lên 1718.2ms (~7.6×) — một SLO đặt theo average (ví dụ "average < 400ms") sẽ **vẫn PASS** trong tình huống mà 1/10 người dùng đang chờ gần 2 giây. Trải nghiệm thực của người dùng không phải là "trung bình của mọi người", mà là trải nghiệm của riêng họ — và percentile cao gần với trải nghiệm của "người dùng khó chịu nhất", chính là nhóm dễ rời bỏ sản phẩm hoặc report lỗi nhất. Đó là lý do ngành công nghiệp (và Google SRE Book) luôn đặt SLO theo p95/p99 chứ không theo mean.

---

## 3. Vì sao "cost / câu đúng" tốt hơn "cost / câu" khi so 2 phiên bản

"Cost / câu" (tổng cost ÷ tổng số câu hỏi) không phân biệt được việc *trả tiền để nhận câu trả lời đúng* với *trả tiền để nhận câu trả lời sai* — nó coi 2 đồng chi cho một câu đúng và 2 đồng chi cho một câu sai là như nhau. Trong lab, agent v1 có cost/câu thấp hơn v2 một chút về bản chất prompt ngắn hơn, nhưng ích lợi (số câu đúng) của nó gần như bằng 0 (chỉ 1/23). Khi quy đổi cost theo **"cost / câu đúng"** (tổng cost ÷ số câu đúng), con số của v1 bị "phình to" đúng với thực tế là *toàn bộ chi phí của 22 câu sai* vẫn phải tính vào, chỉ chia cho 1 câu đúng duy nhất ⇒ v1 = $0.00041295/câu đúng. Ngược lại v2 trả lời đúng 21/23 câu nên chi phí "lãng phí" cho câu sai rất ít ⇒ v2 = $0.00003619/câu đúng, **rẻ hơn ~11.4×**. "Cost / câu đúng" chính là thước đo ROI thật: nó trả lời câu hỏi kinh doanh thực sự — "để có một câu trả lời hữu ích, tôi phải trả bao nhiêu" — còn "cost/câu" có thể đánh lừa người ra quyết định chọn phiên bản rẻ hơn nhưng vô dụng hơn.

---

## 4. Ghi chú trung thực về "screenshot" của Part 7

Agent chạy phần CP7/CP8 này **không có quyền truy cập GUI/trình duyệt** (môi trường headless CLI). Vì vậy 4 "ảnh chụp màn hình" mà CODE_LAB.md/README yêu cầu (dashboard Grafana, 1 trace chậm trong Jaeger, 1 trace lỗi trong Jaeger kèm log, trang Alerts của Prometheus đang firing) đã được thay bằng **bằng chứng kéo trực tiếp qua API** của từng dịch vụ, lưu dưới dạng `.json`/`.txt` trong `screenshots/`:

| File | Thay cho ảnh gì | Lấy bằng |
|---|---|---|
| `screenshots/grafana-dashboard-definition.json` | Ảnh dashboard Grafana | `GET /api/dashboards/uid/day14-agent-overview` (Grafana API, admin/admin) |
| `screenshots/grafana-live-panel-data.json` | Số liệu sống trên dashboard lúc có tải | `GET /api/datasources/proxy/uid/prometheus/api/v1/query` qua Grafana (chạy đúng PromQL của 4 panel Golden Signals) |
| `screenshots/jaeger-slow-trace.json` | Ảnh 1 trace chậm trong Jaeger | `GET /api/v3/traces/{trace_id}` (Jaeger v3 query API) |
| `screenshots/jaeger-error-trace.json` | Ảnh 1 trace lỗi trong Jaeger | `GET /api/v3/traces/{trace_id}` |
| `screenshots/jaeger-error-trace-matching-log.txt` | Dòng log JSON khớp `trace_id` của trace lỗi | `docker compose -p k5-day14-observability logs agent \| grep <trace_id>` |
| `screenshots/prometheus-alerts.json`, `prometheus-alert-firing.json` | Ảnh trang Alerts của Prometheus đang firing | `GET /api/v1/alerts` |

Những file này chứa **dữ liệu thật, đo được, không bịa** — API trả JSON có cấu trúc đầy đủ (span, timestamp, giá trị metric, trạng thái alert) nên về nội dung thông tin không kém ảnh PNG, chỉ khác định dạng hiển thị. Tuy nhiên đây **không phải ảnh PNG thật** như bài yêu cầu theo đúng nghĩa đen ("Chụp một ảnh trang Alerts..."), và không cho thấy giao diện trực quan (màu đỏ/xanh của panel, layout dashboard) mà giảng viên/rubric có thể muốn nhìn thấy khi chấm bài.

**Khuyến nghị:** trước khi nộp bài, bạn (người dùng) nên tự mở `http://localhost:3000` (Grafana), `http://localhost:16686` (Jaeger), `http://localhost:9090/alerts` (Prometheus) trong trình duyệt thật và chụp 4 ảnh PNG theo đúng yêu cầu gốc của CODE_LAB.md/README, để vừa có bằng chứng JSON (dữ liệu thô, dùng để đối chiếu số liệu trong `BENCHMARK_REPORT.md`) vừa có ảnh PNG (bằng chứng trực quan, đúng định dạng rubric mong đợi). Stack đã được `docker compose down -v` sau khi agent hoàn thành CP7/CP8 — cần `docker compose -p k5-day14-observability up -d --build` lại và chạy Locust/driving-fault lại nếu muốn tái tạo đúng trạng thái "đang có tải + alert firing" lúc chụp ảnh.

---

## 5. Tóm tắt thực thi (tham chiếu nhanh)

- CP7 (`develop/`): agent v1 (8001) / v2 (8002) chạy bằng Python 3.12 venv riêng (Python 3.15 hệ thống không build được `pydantic-core`). 4 load test theo concurrency, 3 load test theo `MOCK_SLOW_RATE`, eval v1/v2/v2_fixed — tất cả file JSON nằm trong `develop/reports/`. Sửa `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` (và đồng bộ sang `production/utils/mock_llm.py`) để đạt accuracy 100%, quality gate PASS.
- CP8 (`production/`): phát hiện và vá một lỗi thật trong `production/Dockerfile` (container agent crash-loop vì `ModuleNotFoundError: No module named 'uvicorn'` — xem chi tiết bug ở mục 6) trước khi stack chạy được. Sau khi vá, stack lên đủ 6 service, Locust headless scale 1→3 lưu CSV, 2 alert firing thật (có snapshot 3 alert firing đồng thời), trace chậm/lỗi lấy qua Jaeger API, log khớp `trace_id`.

---

## 6. Bug phát hiện và đã vá: `production/Dockerfile`

Khi build/chạy stack lần đầu, container `agent` crash-loop liên tục với:

```
ModuleNotFoundError: No module named 'uvicorn'
```

Nguyên nhân: Dockerfile dùng multi-stage build, cài package bằng `pip install --user` ở stage builder (ghi vào `/root/.local`), rồi `COPY --from=builder /root/.local /home/agent/.local` sang stage runtime. Nhưng user `agent` được tạo bằng `useradd -r -g agent -d /app agent` — tức **home directory của user `agent` là `/app`**, không phải `/home/agent`. Python's `site` module chỉ tự thêm `$HOME/.local/lib/pythonX.Y/site-packages` vào `sys.path`, nên với `HOME=/app` nó tìm sai chỗ (`/app/.local/...` không tồn tại) dù `PATH` đã trỏ đúng tới `/home/agent/.local/bin/uvicorn` (binary chạy được, nhưng import bên trong nó thất bại).

Đã vá bằng cách thêm `ENV HOME=/home/agent` ngay trước khi set `PATH`/`PYTHONPATH` trong `production/Dockerfile`, khớp với nơi `COPY --from=builder` đã đặt `.local`. Sau khi vá và `docker compose up -d --build`, agent lên `healthy` và trả 200 qua Nginx. Đây là một bug thật trong repo gốc (không phải lỗi cấu hình của người làm bài), ảnh hưởng trong phạm vi `06-lab-complete/benchmark-observability/production/` nên đã sửa trực tiếp để CP8 chạy được.
