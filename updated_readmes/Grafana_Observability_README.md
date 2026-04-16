# Monster Resort Heartbeat Monitor - Grafana Observability

**Document ID:** MR-OPS-001
**Owner:** Monster Resort Operations & Management
**Status:** FINAL

---

## 1. Introduction: Why Your Resort Needs a "Digital Pulse"

In the physical world of the **Monster Resort**, we have security cameras to watch the hallways, thermometers to check the temperature of the lava pits, and clipboards to track guest check-ins. In the digital world, our AI Concierge is a complex "black box." Without the right tools, we have no idea if it is happy, tired, or completely broken until a frustrated vampire starts yelling at the front desk.

**Grafana** is our solution. It is a world-class visualization platform that transforms invisible streams of data—like how long the AI takes to think or how many people are talking to it—into beautiful, easy-to-read graphs and gauges.

### The Medical Analogy

Think of our RAG (Retrieval-Augmented Generation) system as a living patient.

* **The Scripts (`run_audit.py`):** These are like a monthly physical exam. They are deep, thorough, but only happen once in a while. They tell you how the system *was* performing during the test.
* **Grafana:** This is the heart rate monitor and the pulse oximeter. It stays attached to the patient 24/7. It tells you what is happening *right now*.

If a sudden influx of 500 ghosts hits the server at 3:00 AM, a script won't help you because you aren't running it. Grafana, however, will show a massive spike on the screen, potentially triggering an alarm to wake up the manager on duty.

---

## 2. Core Importance: Why This Isn't Just "Optional"

For a non-developer, it might seem like we are just adding "pretty pictures" to the project. However, Grafana is a non-negotiable part of a high-value production environment for several critical reasons:

### 2.1 Real-Time Awareness vs. Point-in-Time Blindness

Most computer programs only tell you there is a problem *after* they crash. Grafana allows us to see the problem *developing*. We can watch the memory usage of the AI slowly climb over eight hours. In the world of developers, this is called a "Memory Leak." To a resort manager, it looks like a slow-motion car crash that we have time to prevent by restarting the system before it actually fails.

### 2.2 Visualizing the "Hiccups"

During our development, we saw errors like `Connection Refused` or `Read Timeout`. In a text-based terminal, these are just lines of ugly code that are easy to miss. In Grafana:

* **Timeouts** appear as jagged red lines that break the flow of the graph.
* **Connection Drops** appear as flat-lined "gaps" in the data.
* **Successes** appear as steady green blocks, giving the staff peace of mind.

### 2.3 Correlating Data (The Superpower)

Grafana’s "Superpower" is correlation. It can overlay two different pieces of information. For example, we can see if the AI gets slower (Latency) at the exact same time the number of guests (Traffic) increases. This helps us decide if we need a "bigger brain" (more server power) or if the AI is just having a "bad day" due to a specific bug.

---

## 3. The Step-by-Step Setup Guide (Layperson Friendly)

Setting up a professional monitoring suite sounds intimidating, but we have simplified the process into four main phases.

### Phase 1: Awakening the Monitoring Stack (Docker)

We use a tool called **Docker-Compose** to manage our monitoring tools. Think of this like a "Master Power Switch" for the resort's security office.

1. **Open the Terminal:** This is the command-line app on your computer.
2. **Navigate to the Folder:** Ensure you are in the `monster-resort-concierge` folder.
3. **Flip the Switch:** Type `docker-compose up -d` and press Enter.
* *What is happening?* The `-d` stands for "detached." It means the monitoring tools will run quietly in the background, like a silent security guard, without cluttering your screen.
* *What comes online?* Docker-Compose starts **6 services**: `api`, `postgres`, `redis`, `prometheus`, `grafana`, and `mlflow`.

### Phase 2: Accessing the Dashboard

Grafana is web-based. You don't need special software to see it; you just need a browser.

1. Open Chrome, Firefox, or Safari.
2. Type `http://localhost:3000` into the address bar.
3. **The Login:** If it’s your first time, the default username and password are usually `admin` / `admin`. The system will ask you to change it—please use a "Monster-Proof" password.

### Phase 3: Connecting the Data Source (Prometheus)

Grafana is the "TV Screen," but it needs a "Cable Box" to provide the signal. That cable box is a database called **Prometheus**.

1. On the left-hand sidebar, hover over the **Connections** icon (it looks like a plug) and click **Data Sources**.
2. Click the blue **Add data source** button.
3. Select **Prometheus** from the list of options.
4. **The URL:** In the "Connection" section, look for the "Prometheus server URL" field. Type: `http://prometheus:9090`.
5. **Test it:** Scroll all the way to the bottom and click **Save & Test**.
* **The Green Success:** You are looking for a green box that says *"Successfully queried the Prometheus API"*. This means the "TV" is now receiving the "Signal."

### Phase 4: Building Your First "Health Stat"

1. Click the **Dashboards** icon (four squares) in the sidebar.
2. Click **New** > **Add visualization**.
3. Select the **Prometheus** source you just created.
4. In the Query box, type: `http_requests_total`.
5. On the right side, change the "Visualization" type from "Time Series" to **"Stat."**
6. Click **Apply** in the top right. You now have a giant number showing every time a guest has ever talked to the concierge!

---

## 4. Hiccups and "Ghostly" Errors (Troubleshooting)

Even the best systems have issues. Here are the most common "Hiccups" we encountered during the Monster Resort setup and how to fix them without calling a developer.

### 4.1 The "Connection Refused" Ghost

**Symptom:** You try to go to `localhost:3000` and the browser says "This site can't be reached".
**Why it happens:** Either Docker crashed, or the computer's internal "port" for Grafana (3000) was blocked by another app.
**The Fix:** 1.  Check if Docker is running (look for the whale icon in your taskbar).
2.  If you are on a Mac, use the "Exorcism" command to force-restart the service: `brew services restart grafana`.

### 4.2 The "No Data" Void

**Symptom:** You see the dashboard, but the graphs are empty and say "No Data".
**Why it happens:** This is the most common hiccup! It happens because the AI Concierge (the "Brain") hasn't sent any information to the "Cable Box" (Prometheus) yet.
**The Fix:** You need to "pulse" the system.

1. Open your terminal.
2. Copy and paste this "Pulse Command":
```bash
curl http://localhost:8000/chat -X POST -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" -d '{"message": "Wake up!"}'
```

3. As soon as the AI answers, the "No Data" will disappear and turn into a "1" on your dashboard.

### 4.3 The "Port 8000 Hijack"

**Symptom:** The developer terminal says `[Errno 48] Address already in use`.
**Why it happens:** A previous version of the concierge didn't shut down correctly and is "haunting" the port, preventing the new one from starting.
**The Fix:** Use the **Exorcism One-Liner** to clear the "ghost":
`lsof -ti:8000 | xargs kill -9 && uv run uvicorn app.main:app --reload`.

---

## 5. Non-Developer Best Practices

To keep the Resort's monitoring healthy, follow these rules:

1. **Don't "Double-Tap":** If the dashboard is slow to load, don't keep clicking refresh. Prometheus takes a few seconds to "scrape" (collect) data from the AI.
2. **Use the "Last 5 Minutes" View:** When checking if the concierge is alive, look at the top right of Grafana and set the time range to "Last 5 minutes." Looking at "Last 24 hours" makes it harder to see if there is a problem happening *right now*.
3. **Keep it Running:** Always leave one terminal window open running the `uvicorn` command. If that window closes, the concierge goes home, and the dashboard flat-lines.

---

## 6. MLflow as an Additional Observability Tool

In addition to Grafana and Prometheus, the project now includes **MLflow** (`http://localhost:5000`) as part of the docker-compose stack. While Grafana provides real-time dashboards for operational metrics, MLflow provides experiment-level tracking for model performance and RAG evaluation runs.

A key metric to consider visualizing in Grafana is the **hallucination confidence score** returned by the `/chat` endpoint. The `confidence` field (0.0-1.0), produced by `app/hallucination.py`, indicates how grounded each AI response is in the knowledge base. Plotting this over time in Grafana can reveal trends in response quality and help detect degradation.

---

## 7. Conclusion

Grafana is the eyes and ears of the Monster Resort Concierge. It transforms a "hidden" AI into a transparent, manageable resort utility. By following this guide, any staff member can ensure our supernatural guests receive the high-voltage luxury service they expect without the fear of a silent system failure.

---
