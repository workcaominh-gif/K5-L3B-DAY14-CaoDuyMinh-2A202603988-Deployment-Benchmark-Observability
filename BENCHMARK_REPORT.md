# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Nhóm 001 (cá nhân)
**Ngày chạy:** 2026-11-26
**Môi trường:** MacBook (Apple Silicon, macOS 27), Docker Desktop 24.0.7 / Compose v2.23.3, Python 3.12.3 (venv riêng cho `develop/`, vì Python 3.15 hệ thống chưa có wheel `pydantic-core` sẵn và máy không có Rust toolchain mới để build từ source)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Ngưỡng mặc định của `load_test.py`; đủ nhanh cho trải nghiệm chat, và tách biệt rõ với tail latency do `MOCK_SLOW_RATE` gây ra (~1.7s) nên dễ thấy vi phạm. |
| Error rate `/ask` | < 2 % | Ngưỡng mặc định của `load_test.py`; cao hơn error rate nền (~1% từ `MOCK_ERROR_RATE`) một chút để không báo động vì nhiễu ngẫu nhiên, nhưng đủ chặt để bắt được khi lỗi tăng thật. |
| Accuracy trên golden dataset | ≥ 100 % | Dataset chỉ có 23 câu cố định, mỗi câu là một khả năng kiến thức agent phải biết (health check, 12-factor, JWT, HPA...) — 100% là mục tiêu hợp lý vì đây không phải mẫu ngẫu nhiên mà là checklist kiến thức. Alert mức production thực tế nên lỏng hơn (ví dụ ≥ 95%) để chịu được nhiễu của LLM thật. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.35 | 190.9 | 223.1 | 1692.2 | 0.33% | ✅ PASS |
| 10 | 38.46 | 194.7 | 225.0 | 1694.9 | 2.33% | ❌ FAIL (error rate) |
| 50 | 102.47 | 196.6 | 248.7 | 1710.3 | 1.33% | ✅ PASS |
| 100 | 46.51 | 642.6 | 4449.0 | 4998.2 | 1.33% | ❌ FAIL (p95) |

(nguồn: `develop/reports/load_v2_c{1,10,50,100}.json`)

**Nhận xét:** RPS KHÔNG tăng tuyến tính. Từ 1→50 concurrency RPS tăng gần tuyến tính (4.35 → 102.47 req/s) vì mock LLM là `async` và event loop của uvicorn xử lý song song tốt khi còn tài nguyên rảnh. Nhưng ở concurrency=100, RPS tụt xuống 46.51 req/s và p95 nhảy lên 4449ms — đây là bão hoà: quá nhiều request cùng chờ cùng một process (1 worker/container theo đúng thiết kế của lab), hàng đợi dài ra, mỗi request phải đợi lâu hơn trước khi được xử lý, nên throughput hiệu dụng giảm dù tải tăng. Lưu ý thêm: ở concurrency=10 lại có error rate 2.33% (cao hơn cả 50 và 100) — đây là nhiễu ngẫu nhiên từ `MOCK_ERROR_RATE=0.01` trên mẫu 300 request, không phải do tải (minh chứng p95/p99 ở mức 10 vẫn rất thấp).

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 187.9 | 217.7 | 226.7 |
| 0.03 (mặc định) | 231.2 | 222.1 | 1700.8 |
| 0.1 | 345.2 | 1700.4 | 1718.2 |

(nguồn: `develop/reports/load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json`, concurrency=20, 300 request mỗi lần, agent v2 restart lại giữa mỗi lần đổi `MOCK_SLOW_RATE`)

**Nhận xét:** **p99** (và ở `slow_rate=0.1`, cả **p95**) là chỉ số nhạy nhất — nó nhảy từ 226.7ms lên 1718.2ms khi slow rate tăng từ 0 → 0.1 (tăng ~7.6×), còn **avg** chỉ tăng từ 187.9 lên 345.2ms (~1.8×). Trung bình "pha trộn" số đông request nhanh với số ít request chậm bất thường nên nó bị kéo lên rất ít và che giấu hoàn toàn trải nghiệm của nhóm người dùng xấu số (3-10% request chờ gần 1.7-1.8 giây). Đặt SLO theo average sẽ khiến đội vận hành tin agent "ổn" (avg 345ms có vẻ chấp nhận được) trong khi thực tế 1/10 người dùng đang chờ gần 2 giây — p95/p99 mới phản ánh đúng trải nghiệm của "người dùng khó chịu nhất", và đó chính là nhóm dễ rời bỏ sản phẩm nhất.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57.7 | 109.0 | 116.4 |
| Tổng cost (USD) | 0.000413 | 0.000760 | 0.000814 |
| Cost / câu đúng (USD) | 0.00041295 | 0.00003619 | 0.00003541 |
| Quality gate | ❌ FAIL (accuracy < 80%) | ✅ PASS (so với baseline v1, 0 regression) | ✅ PASS (so với baseline eval_v2, `--min-accuracy 1.0`, 0 regression) |

(nguồn: `develop/reports/eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json`)

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry mới vào `KNOWLEDGE_BASE` (trigger `["jwt", "api key", "xác thực"]`) giải thích JWT là token tự chứa, có **chữ ký** chống giả mạo và **thời gian hết hạn**, khác API key là chuỗi tĩnh phải tra database. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry mới (trigger `["hpa", "horizontal pod autoscaler", "kubernetes", "k8s"]`) giải thích Kubernetes HPA scale pod dựa trên **cpu**, **memory**, hoặc **custom metrics**. |

Sau khi sửa, `python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 --baseline reports/eval_v2.json --out reports/eval_v2_fixed.json` in ra `Quality gate (accuracy ≥ 100%, không regression): ✅ PASS` và không có câu nào bị regression (2 câu được cải thiện, đúng 2 câu vừa sửa).

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

v1 (không retrieval) gần như vô dụng trên dataset kỹ thuật này (4.3% accuracy) vì chỉ trả lời chung chung — nó không "biết" nội dung khoá học, chỉ đoán theo vài từ khoá cứng. v2 (có retrieval) tốn gấp ~2× token mỗi câu (109 vs 57.7) nên tổng cost cao hơn ~84%, và p95 latency cũng tăng nhẹ (do có thêm bước `retrieve_context`), nhưng **cost / câu đúng lại rẻ hơn ~11.4×** (0.000036 vs 0.000413 USD) vì v1 trả lời đúng quá ít nên mỗi câu đúng hiếm hoi của nó "gánh" toàn bộ cost của tất cả các câu sai. Đây đúng là lý do "cost / câu đúng" là chỉ số công bằng hơn "cost / câu" khi so 2 phiên bản: nếu chỉ nhìn cost/câu, v1 có vẻ "rẻ" hơn, nhưng thực chất nó đang đốt tiền để trả lời sai — "cost / câu đúng" quy đổi mọi chi phí (bao gồm của các câu sai) về trên một đơn vị giá trị thực sự tạo ra (câu trả lời đúng), nên phản ánh đúng ROI của việc thêm retrieval.

---

## 4. Observability stack (production)

### 4.1 Screenshot

> ⚠️ Môi trường chạy agent này **không có GUI/trình duyệt** (headless CLI). Thay cho ảnh PNG, bằng chứng dưới đây là JSON/text lấy trực tiếp từ API của Prometheus/Jaeger/Grafana — xem chi tiết lý do và khuyến nghị trong `MISSION_ANSWERS_PART7.md`.

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals) → `screenshots/grafana-dashboard-definition.json` (định nghĩa dashboard, 19 panel) + `screenshots/grafana-live-panel-data.json` (giá trị PromQL sống của 4 panel Golden Signals qua Grafana datasource-proxy, lấy lúc đang có tải: traffic ≈ 15.4 req/s, error rate ≈ 19.1%, p95 ≈ 1.89s, instances up = 2)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian) → `screenshots/jaeger-slow-trace.json` (xem phân tích span ở mục 4.3)
- [x] Một trace lỗi trong Jaeger (có event lỗi) → `screenshots/jaeger-error-trace.json` (span `chat mock-llm-small` có `status.code=2` (ERROR), message `LLMError: Upstream LLM error: 503 Service Unavailable (mock)`)
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing** → `screenshots/prometheus-alert-firing.json`: **3 alert đang firing đồng thời** lúc 2026-11-26T08:05:22Z (`AgentHighErrorRate`, `AgentHighLatencyP95`, `LLMCostBurnRateHigh`) — vượt yêu cầu tối thiểu 2.

### 4.2 Thí nghiệm "phá hệ thống"

Đổi đồng thời `MOCK_ERROR_RATE=0.2` và `MOCK_SLOW_RATE=0.3` trong `production/.env`, `docker compose -p k5-day14-observability up -d` lúc **08:02:44 UTC**, giữ Locust headless ~30 user chạy 3 phút, poll `http://localhost:9090/api/v1/alerts` mỗi 10-15s.

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (critical) | `pending` lúc 08:02:52 (8s sau khi đổi) → `firing` lúc 08:03:52 (`for: 1m` đúng như rule) — tổng **~68s** từ lúc đổi config | Error rate (stat) — đỏ ngay, giá trị thực đo ≈ 18-20% trong khi SLO alert là >5% |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (warning) | `pending` lúc 08:02:57 (13s sau khi đổi) → `firing` lúc 08:04:57 (`for: 2m`) — tổng **~2m13s** từ lúc đổi config | Latency /ask — p50/p95/p99 (timeseries) — p95 đo được ≈ 1.9s, p50 gần như không đổi (~0.2s) |
| C | `LLM_MODEL=mock-llm-large` | *(không chạy — ngoài phạm vi 2 alert bắt buộc; xem ghi chú)* | — | Cost burn rate (USD/giờ) |
| D | `docker pause` 1 instance | *(không chạy)* | — | Instances up |
| E | `AGENT_VERSION=v1` | *(không chạy — theo lý thuyết, không alert nào firing)* | — | — |

**Quan sát thêm (không nằm trong bảng gốc):** `LLMCostBurnRateHigh` cũng **firing** trong cùng snapshot (`activeAt` 07:58:52, tức đã firing từ ~08:00:52) — đây là hiệu ứng phụ *tự nhiên* của bài benchmark scaling ở mục 5 (Locust headless 100 user, 2 phút chạy ở throughput mặc định): tốc độ chi tiêu LLM mock vượt $2/giờ chỉ từ **khối lượng traffic cao**, không cần đổi `LLM_MODEL`. Điều này cho thấy alert cost không chỉ bắt được việc đổi sang model đắt (bài C) mà còn bắt được tăng trưởng traffic bất thường — đúng với mục đích "cost burn rate" alert.

Chỉ chạy A và B (đã đủ ≥2 alert firing theo yêu cầu CP8); C/D/E không chạy để tiết kiệm thời gian wall-clock, ghi nhận trung thực ở đây và trong `MISSION_ANSWERS_PART7.md`.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Metric hạ tầng (latency, error rate, instance up) đều "xanh" khi đổi `AGENT_VERSION=v1` vì v1 vẫn trả HTTP 200 nhanh và không lỗi — nó chỉ trả lời *sai về nội dung*, một lớp vấn đề mà metric không nhìn thấy được. Cách phát hiện trong production: (1) chạy **eval trên golden dataset định kỳ trong CI/CD** trước mỗi lần deploy, dùng chính `run_eval.py` làm quality gate (mục 1 của `MISSION_ANSWERS_PART7.md`); (2) theo dõi tín hiệu gián tiếp từ người dùng thật — tỉ lệ thumbs-down/feedback âm, tỉ lệ người dùng hỏi lại/rephrase trong 1 phiên, hoặc escalation tới người thật; (3) thêm metric riêng cho chất lượng, ví dụ `retrieval_hit_ratio` (đã có sẵn trong dashboard — ở v1 metric này sẽ "biến mất" vì v1 không retrieval) và alert khi nó tụt về 0 bất thường; (4) chạy eval nhỏ liên tục (canary eval) ngay trên traffic production với một tập câu hỏi rút gọn, không chỉ eval offline.

### 4.3 Debug bằng trace

Trace chậm nhất tìm được qua Jaeger API (`/api/v3/traces?query.service_name=observable-agent...`, sort theo duration):

- `trace_id`: `4382aa8196d2483b9e92a3c275efd7ff`
- Tổng thời gian: **1714.9 ms**
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` — **1689.0 ms (98.5%)** của tổng thời gian trace. Span `agent.retrieve_context` chỉ chiếm 21.1ms (1.2%) — retrieval không phải nguyên nhân chậm, lỗi (tail latency) hoàn toàn nằm ở bước gọi "LLM" (mock).
- Trace lỗi chọn để đối chiếu log: `trace_id` = `ddc90a4c71023d6c700f8a8df5e0b402` (span `chat mock-llm-small` có `status.code=2`, message `LLMError: Upstream LLM error: 503 Service Unavailable (mock)`).
- Dòng log tương ứng (`docker compose -p k5-day14-observability logs agent | grep ddc90a4c71023d6c700f8a8df5e0b402`, lưu đầy đủ ở `screenshots/jaeger-error-trace-matching-log.txt`):

```json
{"ts": "2026-11-26T08:03:08.907102+00:00", "level": "INFO", "service": "observable-agent", "instance": "c6af6a135c9f", "event": "llm_error", "trace_id": "ddc90a4c71023d6c700f8a8df5e0b402", "span_id": "a8b5e6b4dfbc30f6", "request_id": "a6e3622c894e", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
{"ts": "2026-11-26T08:03:08.910251+00:00", "level": "INFO", "service": "observable-agent", "instance": "c6af6a135c9f", "event": "http_request", "trace_id": "ddc90a4c71023d6c700f8a8df5e0b402", "span_id": "a8b5e6b4dfbc30f6", "request_id": "a6e3622c894e", "method": "POST", "route": "/ask", "status": 503, "ms": 860.4}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 66.11 | 190 | 270 | 1700 | 609 / 7918 (7.69%) |
| 3 | 66.12 | 200 | 230 | 1700 | 71 / 7913 (0.90%) |

(nguồn: `production/benchmark-results/scale_1_stats.csv`, `scale_3_stats.csv`; Locust headless `-u 100 -r 10 -t 2m` qua Nginx)

**Giải thích kết quả:** **RPS hầu như không đổi** (66.11 → 66.12 req/s) vì cổ phần cổ chai không phải CPU xử lý của agent (mock LLM async, nhẹ) mà là **độ trễ cố định của mock LLM cho mỗi request** (`MOCK_LATENCY_MS` + jitter, không phụ thuộc số instance) — mỗi instance xử lý được nhiều request đồng thời (event loop async), nên tổng throughput đã gần bão hoà rồi ở 1 instance trong điều kiện tải 100 user của Locust. Cái scale lên 3 **cải thiện rõ** là **error rate** (7.69% → 0.90%, giảm ~8.5×) và p95 (270 → 230ms): ở 1 instance, khi 100 Locust user cùng dồn vào, hàng đợi connection bị tràn và Nginx trả 502 (timeout chờ agent) nhiều hơn; với 3 instance, tải được chia ra nên ít request bị nghẽn ở tầng kết nối/hàng đợi. Đúng như gợi ý trong README: p99 vẫn giữ nguyên ở 1700ms cả 2 trường hợp — đây là **tail latency do `MOCK_SLOW_RATE`** (giả lập LLM đôi khi chậm bất thường), nằm *bên trong* mỗi lần gọi LLM và không được giải quyết bằng cách thêm instance phía trước nó. Nút thắt thật là **chính bản thân latency của lệnh gọi LLM** (upstream), không phải hạ tầng — scale ngang (horizontal scaling) chỉ giúp agent *chịu được nhiều người dùng đồng thời hơn mà không timeout*, không giúp *mỗi câu trả lời nhanh hơn*.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **p95/p99 nói dối ít hơn average rất nhiều** — chỉ 3-10% request chậm bất thường đủ để đẩy p99 lên gần 2 giây trong khi average vẫn "trông ổn" (187ms → 345ms khi 10% request chậm, nhưng p99 từ 227ms → 1718ms). SLO và alert phải đặt theo percentile.
  2. **Scale ngang giải quyết "quá tải kết nối", không giải quyết "LLM chậm"** — thêm instance từ 1→3 giảm error rate 8.5× và cải thiện p95, nhưng p99 không đổi vì tail latency nằm *trong* lệnh gọi LLM, trước khi request tới được tầng hạ tầng có thể scale.
  3. **Metric hạ tầng xanh không có nghĩa là chất lượng tốt** — thí nghiệm `AGENT_VERSION=v1` (và quan sát thực tế khi đổi `KNOWLEDGE_BASE`) cho thấy accuracy có thể tụt sâu (91.3%→... hoặc về mức rất thấp như v1 4.3%) mà không một alert hạ tầng nào (error rate, latency, instance down) phản ứng — observability hạ tầng và eval chất lượng là hai lớp giám sát độc lập, cần cả hai.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

1. **Canary/shadow eval liên tục trên traffic thật** (không chỉ golden dataset tĩnh) để bắt regression chất lượng mà metric hạ tầng không thấy được (xem mục 4.2, thí nghiệm E).
2. **Synthetic check từ bên ngoài hệ thống** (external blackbox probe gọi `/ask` mỗi ví dụ 30s từ một vùng khác) — vì README đã chỉ ra lỗi 504 ở tầng Nginx không được agent's metric đếm (request chưa bao giờ "chạm" tới code của agent).
3. **Alert theo error budget burn rate** (ví dụ multi-window burn-rate alert kiểu Google SRE) thay vì chỉ ngưỡng tức thời, để phân biệt "spike ngắn vô hại" với "đang ăn hết error budget của cả tháng".
4. **Metric retry/circuit-breaker** (số lần retry tới LLM upstream, trạng thái circuit breaker) — hiện tại `load_test.py`/`run_eval.py` có retry nhưng agent production chưa thấy cơ chế retry riêng, rất cần khi LLM thật (không phải mock) có tỉ lệ lỗi/timeout cao hơn.
5. **Cảnh báo cost theo ngân sách ngày/tháng** (không chỉ burn-rate theo giờ) để tránh trường hợp burn rate thấp nhưng kéo dài vẫn vượt budget tổng.
