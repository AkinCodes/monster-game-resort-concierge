Below is a single **Confluence page** you can copy/paste. It captures the *important stuff*, the *exact commands*, and the *hiccups + fixes* from your journey (Colima/Docker Compose/Grafana/Prometheus + audit/stress scripts). 

---

# Monster Resort Concierge — Local Observability + Reliability Setup (Mac + Colima)

**Audience:** beginners (you), but written like an internal production runbook. 
**Goal:** get the “Triple Threat” running locally:

* **API (FastAPI)** on `http://localhost:8000`
* **Grafana** on `http://localhost:3000`
* **Prometheus** on `http://localhost:9090`

Then run:

* **Quality Audit:** `run_audit.py` (RAG grounding + RAGAS evaluation)
* **Stress Test:** `stress_test.py` (latency + throughput under load)

---

## 1) Why Grafana still matters (even if you have scripts)

Your scripts are *point-in-time*. Grafana/Prometheus are *always-on observability*.

* `run_audit.py` tells you if the AI is **faithful** to your documents (hallucination risk).
* `stress_test.py` tells you how the system behaves when multiple guests hit it at once.
* **Grafana** shows you *why* things spike (CPU/mem/request duration) while tests run, and it keeps history.

This is why the project includes Grafana/Prometheus alongside your test scripts. 

---

## 2) Preconditions (Mac / Colima mental model)

On Mac, Docker needs a “daemon” running. You’re using **Colima** (not Docker Desktop), so this is the critical dependency:

✅ **Colima must be running** before `docker-compose up -d` works.
If it’s not running, you’ll see the exact error you hit:

> “Cannot connect to the Docker daemon at … .colima … docker.sock” 

---

## 3) Quick Start (copy/paste commands)

### 3.1 Start Colima (the Docker engine)

```bash
colima start
```

Expected: output ends with something like `done` / “ready”. 

### 3.2 Start the full stack (API + Prometheus + Grafana)

From inside your project folder:

```bash
docker-compose up -d
```

**Common harmless warning**
You may see:

> `the attribute version is obsolete...`
> This warning is safe to ignore; it will not block startup. 

### 3.3 Confirm containers are running

```bash
docker ps
```

You should see at least:

* `monster-resort-concierge-api-1` (or similar)
* `monster-resort-concierge-prometheus-1`
* `monster-resort-concierge-grafana-1`
* `monster-resort-concierge-mlflow-1`

### 3.4 Open the UIs

* API docs: `http://localhost:8000/docs`
* Grafana: `http://localhost:3000` (default login admin/admin)
* Prometheus: `http://localhost:9090`
* MLflow UI: `http://localhost:5000` (experiment tracking and model registry)

### New Production Feature Files (Reference)

The following files implement the 6 new production features. Refer to them for implementation details:

| Feature | File(s) | Purpose |
| --- | --- | --- |
| Multi-Model LLM Orchestration | `app/llm_providers.py` | ModelRouter with OpenAI->Anthropic->Ollama fallback chain |
| Hallucination Mitigation | `app/hallucination.py` | HallucinationDetector with ConfidenceLevel scoring |
| MLflow MLOps Platform | `app/mlflow_tracking.py` | Experiment tracking, model versioning at http://localhost:5000 |
| LangChain vs Custom RAG | `app/langchain_rag.py`, `scripts/benchmark_rag.py` | Benchmark LangChain RAG against custom AdvancedRAG |
| AWS Cloud Deployment | `deploy/aws/` | ECS Fargate, ECR, CloudWatch, CI/CD pipeline |
| Centralized Config | `app/config.py` | All MRC_ prefixed environment variables |

---

## 4) Grafana first-time setup (Prometheus data source)

Once you can open Grafana at `localhost:3000`:

1. Login (default): **admin / admin**
2. Add Data Source:

   * Go to **Connections → Data sources → Add data source**
   * Choose **Prometheus**
   * URL:

     ```text
     http://prometheus:9090
     ```
   * Click **Save & Test**
     Expected: “Data source is working”. 

**Why that URL?**
Inside Docker Compose networking, containers refer to each other by service name (Prometheus service = `prometheus`). 

---

## 5) Daily Operating Protocol (SOP)

### 5.1 Start-of-day (or before testing)

```bash
colima start
docker-compose up -d
docker ps
```

### 5.2 Run the reliability scripts

```bash
python run_audit.py
python stress_test.py
```

For stress test, pick **Option 2 (Standard)** if prompted. 

### 5.3 End-of-day (don’t just close the laptop)

```bash
docker-compose down
```

This stops containers cleanly and saves resources. 

---

## 6) Master script (optional) — run Audit then Stress

You attempted `master_check.py`. The idea is correct: one command to run both checks. 

**But**: if the API is “unhealthy” or not responding, a master script can *feel frozen* because it’s waiting for requests to complete. 

If you use a master script, make sure you can load:

* `http://localhost:8000/docs` first, *then* run the master script. 

---

## 7) Hiccups you hit (and the correct fixes)

This section is the real gold. It’s the “things that will bite you again”.

---

### Hiccup A — “Cannot connect to Docker daemon… colima docker.sock”

**Symptom**

```text
Cannot connect to the Docker daemon at unix:///Users/.../.colima/default/docker.sock
```



**Cause**
Colima (Docker runtime) wasn’t running yet.

**Fix**

```bash
colima start
docker-compose up -d
```



---

### Hiccup B — Docker Compose looks “hung/frozen” on first build

**Symptom**
Terminal appears stuck after:

```bash
docker-compose up -d
```

…especially after the obsolete `version` warning. 

**Reality**
Not frozen. BuildKit is doing heavy download + disk writes (you saw high NET I/O and multi-GB BLOCK I/O). 

**How to verify it’s alive**
Open a *second terminal*:

```bash
docker stats --no-stream
```

If CPU/NET/BLOCK numbers are moving, it’s working. 

**If it truly is stuck (or you want to restart clean)**

```bash
docker-compose stop
docker-compose up -d --build
```



**If performance is slow (Colima memory)**
Colima defaults can be tight for AI-ish stacks.

```bash
colima stop
colima start --memory 4
```

(4GB is a decent baseline for local dev.) 

---

### Hiccup C — `docker ps` shows only `buildkitd` (no api/grafana/prometheus)

**Symptom**
You ran `docker ps` and saw only BuildKit running. 

**Cause**
Compose didn’t actually start your stack yet (or failed early).

**Fix**

```bash
docker-compose up -d
docker ps
```

If still missing:

```bash
docker-compose logs --tail=20
```



---

### Hiccup D — Network shows Error, but containers start anyway

**Symptom**
Compose output shows:

```text
✘ Network monster-resort-concierge_default Error
```

…but containers show `Started`. 

**Cause**
Often a partially created network from a prior run. Docker can complain but continue.

**Fix**
Usually none needed if containers are running.
If you want “clean state”:

```bash
docker-compose down
docker-compose up -d
```



---

### Hiccup E — API container shows `(unhealthy)` in `docker ps`

**Symptom**
`docker ps` shows:

```text
Up ... (unhealthy)
```

for the API container. 

**What “unhealthy” means**
Docker healthcheck failed. This does **not always** mean the API is dead; it can be slow to start (vector DB / app init / network calls).

**Manual truth test**
Open:

* `http://localhost:8000/docs`

If FastAPI docs load, the API is functionally up. 

**If it’s genuinely unhealthy**
Check logs:

```bash
docker-compose logs --tail=50 api
```

Then restart:

```bash
docker-compose down
docker-compose up -d --build
```

---

### Hiccup F — `master_check.py` feels frozen

**Symptom**
Running:

```bash
python master_check.py
```

…appears to hang. 

**Likely causes**

1. API not responding / unhealthy (script waits).
2. Your stress test script is interactive (waiting for menu selection).
3. Network calls to model provider taking time / timeouts.

**Fix checklist**

1. Confirm API docs load: `http://localhost:8000/docs` 
2. Run components individually first:

```bash
python run_audit.py
python stress_test.py
```

3. Only then re-run master script.

**Pro tip (novice-friendly)**
If the stress test script prompts for options, it will look “frozen” until you choose an option. (This catches a lot of beginners.)

---

## 8) The big Audit failure you hit (RAGAS / embeddings mismatch)

You got through retrieval + answer generation successfully, then it blew up in evaluation/reporting.

### 8.1 What went right (important!)

Your logs showed:

* contexts retrieved correctly
* answers generated
* **faithfulness ~ 0.8333** (this is good!)


### 8.2 What failed (the actual issues)

You hit:

1. **Version mismatch / embeddings API mismatch**

```text
AttributeError('OpenAIEmbeddings' object has no attribute 'embed_query')
```



2. **Report generation crash**

```text
KeyError: 0
```

…triggered when the script tries to index evaluation results as if it’s a dict/list in the old format. 

3. “LLM returned 1 generations instead of requested 3”
   This is usually non-fatal; evaluation continues but with fewer samples. 

### 8.3 Fix path (dependencies)

You have two viable routes:

#### Route A — Upgrade the relevant libraries (fastest for a novice)

If you’re using `uv` tooling:

```bash
uv pip install --upgrade langchain-openai ragas
uv run python run_audit.py
```



If you’re using pip inside your venv:

```bash
./.venv/bin/pip install --upgrade langchain-openai ragas
./.venv/bin/python run_audit.py
```



#### Route B — Patch the code to match the new RAGAS return type

Your doc notes that RAGAS moved from returning a normal dict to an object-like result, which breaks `.get()` and other dict assumptions. 

**Typical patch idea (conceptual)**
Where you have something like:

* `eval_results.get("faithfulness", 0.0)`
  Switch to:
* `eval_results["faithfulness"]`

This aligns with the guidance in the notes. 

### 8.4 Why you got `nan` and zeros in some metrics

Your evaluation printed something like:

* `answer_relevancy: nan`
* `context_precision: 0.0000`
* `context_recall: 0.0000`
  …and then failed. 

**Interpretation**

* The embeddings mismatch can prevent some metrics from being computed reliably.
* The script then tries to generate a report that assumes those fields exist → crash.

---

## 9) What to capture in Confluence after a successful run (evidence)

When it works, you want artefacts you can attach/link:

### 9.1 Expected output files (evidence)

Look for files like:

* `rag_audit_*.json`
* `stress_test_*.json`
  These are your “proof” for quality and capacity readiness. 

### 9.2 What to screenshot (novice-friendly)

* Grafana dashboard while running stress test (requests climbing)
* Prometheus target page (showing scrape success)
* The audit final summary table (faithfulness/relevancy)

---

## 10) Practical monitoring checks (Prometheus + Grafana)

### 10.1 Prometheus: are we scraping anything?

Open Prometheus:

* `http://localhost:9090`

Check Targets (UI):

* Status → Targets
* You want “UP” for your app target.

If you see “gaps” (no metrics changing), it can mean Prometheus isn’t scraping your API metrics endpoint correctly. 

### 10.2 Grafana: simple “proof of life” queries

Once Prometheus is connected as a data source, try:

* total requests counter (if your app exposes one)
* request duration histogram/summary (if instrumented)

The notes mention watching something like `mrc_bookings_total` increasing during stress tests as a sign the pipeline is wired. 

---

## 11) Troubleshooting playbook (fast decisions)

### 11.1 Nothing works / Docker commands fail

* Run: `colima start` 
* Then: `docker ps`

### 11.2 Compose “hangs”

* Run: `docker stats --no-stream` to see activity 
* If needed:

  ```bash
  docker-compose stop
  docker-compose up -d --build
  ```

### 11.3 Containers start but API is “unhealthy”

* Check: `http://localhost:8000/docs` 
* Logs:

  ```bash
  docker-compose logs --tail=100 api
  ```

### 11.4 Audit fails with `embed_query` / `KeyError`

* Upgrade deps (uv or pip) 
* Re-run audit:

  ```bash
  uv run python run_audit.py
  ```

---

## 12) Recommended “golden commands” list (paste-friendly)

### Colima / Docker engine

```bash
colima start
colima stop
colima start --memory 4
```



### Compose lifecycle

```bash
docker-compose up -d
docker-compose up -d --build
docker-compose down
docker-compose stop
```



### Inspect state

```bash
docker ps
docker stats --no-stream
docker-compose logs --tail=50
docker-compose logs --tail=50 api
```



### URLs

```text
http://localhost:8000/docs
http://localhost:3000
http://localhost:9090
http://localhost:5000
```



### Run scripts

```bash
python run_audit.py
python stress_test.py
python master_check.py
```



### Dependency fixes (choose one approach)

**uv**

```bash
uv pip install --upgrade langchain-openai ragas
uv sync
uv run python run_audit.py
```



**pip in venv**

```bash
./.venv/bin/pip install --upgrade langchain-openai ragas
./.venv/bin/python run_audit.py
```



---

## 13) What “good” looks like (so you know you’re done)

### Infrastructure ✅

* `docker ps` shows **grafana**, **prometheus**, **api**, **mlflow** running
* `http://localhost:3000` loads Grafana login
* `http://localhost:8000/docs` loads FastAPI docs 
* Grafana data source “Save & Test” succeeds against `http://prometheus:9090` 

### Quality Audit ✅

* Audit completes and writes a report file
* Faithfulness >= **0.80** is a solid baseline (you saw ~0.83 even before fixing report generation) 

### Stress Test ✅

* You can run Option 2 (Standard)
* Grafana shows metrics changing during the run 

---

## 14) Notes for “future you” (the real beginner trap list)

1. **Colima first** — without it, Docker looks broken. 
2. **First compose build can look frozen** — confirm via `docker stats`. 
3. **Network error is often harmless** if containers start; clean with `docker-compose down` if needed. 
4. **API “unhealthy” is not always fatal** — check `localhost:8000/docs` for truth. 
5. **Audit can “work” but fail at the end** due to RAGAS object/dict API changes—fix via upgrades or small code patch. 
6. **If master script seems frozen**, run audit and stress separately first to isolate what’s waiting. 

---

If you want, I can also produce a **second Confluence page** that’s just: *“Copy/paste dashboards + recommended PromQL queries + what charts to pin for stress tests”* (so you don’t have to guess what to build in Grafana).





# Grafana “Monster Dashboard” — Copy/Paste Panels + PromQL (Stress-Test Ready)

> **Purpose:** a ready-to-build Grafana dashboard that instantly shows whether your FastAPI concierge is *alive*, *fast*, *stable under load*, and whether Prometheus is scraping correctly. This is designed to be used while you run `python stress_test.py` (Option 2/3) and watch the lines move.  

---

## 0) Preconditions (so the dashboard will actually show data)

### 0.1 Stack is running

```bash
colima start
docker-compose up -d
docker ps
```

You should see Grafana on **3000**, Prometheus on **9090**, and API on **8000**. 

### 0.2 Grafana is connected to Prometheus (one-time)

Grafana → **Connections** → **Data sources** → **Add data source** → Prometheus → URL:

```text
http://prometheus:9090
```

Click **Save & Test**. 

### 0.3 “No data” gotcha (super common)

If you see **No data** in Grafana, it often means you haven’t triggered any requests yet (so counters like `http_requests_total` haven’t moved). 

Send a “pulse” request to your API:

```bash
curl http://localhost:8000/chat \
  -X POST \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Wake up, Grafana!"}'
```

Then change the Grafana time range to **Last 5 minutes** and click **Run queries**. 

---

## 1) Dashboard Build Instructions (fastest way)

1. Grafana → **Dashboards** → **New** → **New dashboard**
2. Click **Add visualization**
3. Select your **Prometheus** data source
4. Paste a PromQL query (from below)
5. Panel Title → use the suggested title
6. Repeat for each panel
7. Save dashboard as:
   **Monster Resort — Stress Test Control Room**

**Time range for stress tests:**

* Use **Last 5m** or **Last 15m** during active testing (so you see immediate spikes). 

---

## 2) Panels to Pin (the “must-haves”)

### Panel A — Service Up (Proof of Life)

**Title:** `Service Up (API Target)`

```promql
up
```

**What you want:** value = `1` for your API scrape target.

---

### Panel B — Request Rate (Requests/sec)

**Title:** `Inbound Requests (RPS)`

```promql
sum(rate(http_requests_total[1m]))
```

This is the first “feel good” graph: during `stress_test.py` it should climb quickly. Your doc explicitly references `http_requests_total` as the metric you’ll see spike. 

**If you want per-endpoint:**

```promql
sum by (handler) (rate(http_requests_total[1m]))
```

(Only works if your instrumentation includes a `handler` or `path` label.)

---

### Panel C — Error Rate (4xx/5xx)

**Title:** `HTTP Errors (4xx + 5xx per sec)`

```promql
sum(rate(http_requests_total{status=~"4..|5.."}[1m]))
```

**Optional split:**

```promql
sum(rate(http_requests_total{status=~"4.."}[1m]))
```

```promql
sum(rate(http_requests_total{status=~"5.."}[1m]))
```

**How to interpret:**

* 4xx spikes can indicate auth/rate-limit issues (e.g., 401/429).
* 5xx spikes indicate server failure or timeouts.

---

### Panel D — Latency (P50 / P95 / P99)

Your notes specifically emphasize **P99 latency** as the “worst-case guest experience” metric during load. 

If you have the common Prometheus histogram metric: `http_request_duration_seconds_bucket`

**Title:** `Latency P50/P95/P99 (seconds)`

```promql
histogram_quantile(0.50, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))
```

```promql
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))
```

```promql
histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))
```

If instead you only have `http_request_duration_seconds` (summary/gauge style), use whichever label exists (often `quantile`):

```promql
http_request_duration_seconds{quantile="0.99"}
```

Your doc explicitly mentions watching `http_request_duration_seconds` in Grafana during the stress test. 

---

### Panel E — Throughput (Total Requests)

**Title:** `Total Requests (Counter)`

```promql
sum(http_requests_total)
```

This should always increase (monotonic). It’s great for “before/after” comparisons across multiple stress runs.

---

### Panel F — “Custom Business Metric” (Bookings Counter)

Your notes call out a specific sanity-check metric: `mrc_bookings_total` and say: *if it doesn’t go up during stress tests, Prometheus scraping/instrumentation is broken.* 

**Title:** `mrc_bookings_total (Business Pulse)`

```promql
mrc_bookings_total
```

**And its rate:**

```promql
rate(mrc_bookings_total[1m])
```

---

## 3) Panels that explain “WHY” things got slow

### Panel G — CPU Usage (Container)

(Requires node exporter / cAdvisor metrics. If your stack doesn’t include these, you won’t see data.)

**Title:** `CPU Usage (Containers)`

```promql
sum by (container) (rate(container_cpu_usage_seconds_total[1m]))
```

---

### Panel H — Memory Usage (Container)

**Title:** `Memory Usage (Containers)`

```promql
sum by (container) (container_memory_working_set_bytes)
```

**Tip:** if you see memory climbing steadily during stress and not dropping, you might be leaking or caching too aggressively.

---

### Panel I — Restart Count (Crash/Boot Loops)

**Title:** `Container Restarts`

```promql
increase(container_start_time_seconds[15m])
```

(Availability varies depending on exporters; if missing, ignore.)

---

### Panel J — Prometheus Scrape Health (Is it collecting reliably?)

**Title:** `Scrape Duration (Prometheus)`

```promql
scrape_duration_seconds
```

**Title:** `Scrape Failures`

```promql
scrape_samples_scraped
```

(These are useful to catch “gaps in the graph” situations your notes mention—often caused by bad `prometheus.yml` target config or multiprocess setup issues. )

---

## 4) Stress Test Workflow (Dashboard-first, then hammer)

1. Open Grafana dashboard: `http://localhost:3000`

2. Set time range: **Last 5 minutes** 

3. Start stress test:

   ```bash
   python stress_test.py
   ```

   * Option 2 = Standard (100)
   * Option 3 = Extreme (500) 

4. Watch these panels in order:

   * **Inbound Requests (RPS)** should spike
   * **Latency P99** should rise but stabilize
   * **HTTP Errors** should ideally remain low
   * **CPU/Memory** explains spikes
   * **mrc_bookings_total** should climb if business flow is active 

---

## 5) “No data” troubleshooting (fast diagnosis)

### Case 1 — Grafana loads, but all panels say “No data”

* Trigger requests (curl / run stress test) so counters move. 
* Set time range to **Last 5 minutes**. 
* Confirm Prometheus data source URL is `http://prometheus:9090`. 

### Case 2 — Stress test runs but graphs don’t change

This is the exact “gaps in the graph” hiccup described in your notes: Prometheus likely isn’t scraping your app correctly. 

Quick checks:

* Prometheus UI → Status → Targets → your API should be **UP**
* Verify the API metrics endpoint exists and is reachable from Prometheus (inside compose network)
* If using multi-worker (gunicorn/uvicorn workers), ensure multiprocess metrics are configured (your notes mention `PROMETHEUS_MULTIPROC_DIR` can matter). 

### Case 3 — API container shows (unhealthy) and dashboard is flat

Your notes mention that “unhealthy” can happen while the AI/vector DB is still loading, causing scripts to hang waiting for responses. 

Manual truth test:

* Open `http://localhost:8000/docs`
  If it loads, API is likely usable even if Docker’s healthcheck is pessimistic. 

---

## 6) Suggested Dashboard Layout (what to pin top-to-bottom)

**Row 1 — Proof of Life**

* Service Up (API Target)
* Total Requests (Counter)

**Row 2 — Guest Experience**

* Inbound Requests (RPS)
* Latency P50/P95/P99
* HTTP Errors (4xx/5xx)

**Row 3 — Business Pulse**

* `mrc_bookings_total`
* `rate(mrc_bookings_total[1m])` 

**Row 4 — System Health (Root Cause)**

* CPU Usage (Containers)
* Memory Usage (Containers)
* Scrape Duration

---

## 7) “Ready for production” thresholds (simple rules of thumb)

These align with how your project frames reliability in a high-value environment (latency/throughput focus). 

* **P99 latency**: try to keep under ~10–15s under standard load (you can set your internal “guest experience” bar here). 
* **5xx errors**: should be near zero; spikes mean instability.
* **RPS**: should rise smoothly with stress test load; “sawtooth” + high errors usually means saturation.

---

If you paste me **one screenshot of your Prometheus metric dropdown** (or the raw metric names you see when you type `http_` in Grafana), I can tailor these queries exactly to *your* labels (e.g., whether it’s `path`, `route`, `handler`, `method`, etc.) and remove any panels that won’t work with your current exporters.
