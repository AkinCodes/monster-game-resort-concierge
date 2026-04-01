# Confluence: Monster Resort Concierge (MRC) Technical Deployment & Architecture Guide

## **1. Project Overview**

The **Monster Resort Concierge (MRC)** is a high-performance, AI-integrated hospitality management system. It utilizes a modern tech stack to provide automated guest services, real-time resort information via Retrieval-Augmented Generation (RAG), and a robust monitoring suite. This document serves as the definitive guide for deploying, operating, and monitoring the full-service stack.

**Note:** The Prometheus metrics layer is now complemented by **MLflow** (`http://localhost:5000`) for experiment-level tracking. While Prometheus excels at real-time operational metrics (request rates, latency, error counts), MLflow tracks model experiments, RAG evaluation scores, and hallucination confidence over time. Both are included as services in `docker-compose.yml` (api, prometheus, grafana, mlflow). The `/chat` endpoint now returns a `confidence` field (0.0-1.0) from the hallucination detection system.

---

## **2. Environment Prerequisites**

Before initializing the terminals, ensure the following environment is established:

* **Python Version**: 3.12.12.
* **Virtual Environment**: Active at `/.venv`.
* **Knowledge Base**: Files `amenities.txt` and `checkin_checkout.txt` must reside in `/data/knowledge/`.
* **Database**: SQLite instance `monster_resort.db`.

---

## **3. Deployment: The Three-Terminal Architecture**

To achieve **Full Capacity**, the system must be launched in three separate, synchronized terminal sessions.

### **Terminal 1: The Backend Engine (FastAPI)**

This is the heart of the resort, handling AI logic, database transactions, and Prometheus metrics.

* **Command**:
```bash
./.venv/bin/python -m uvicorn app.main:app --reload --port 8000

```


* **What to Expect**:
* Initialization of the `ToolRegistry`.
* Database initialization message: `DEBUG [DB]: Database initialized at monster_resort.db`.
* Knowledge ingestion: The system will scan the `/data/knowledge` folder.
* **Ingest Note**: You should see a log confirming the ingestion of documents from your text files.



### **Terminal 2: The Metrics Dashboard (Gradio & Prometheus)**

This terminal provides the visual interface for system health and business analytics.

* **Command**:
```bash
./.venv/bin/python -m app.metrics_dashboard

```


* **Endpoint**: `http://127.0.0.1:7862`
* **What to Expect**:
* A Gradio-based interface showing Prometheus metrics.
* If the Backend is on Port 8000, the "Connection Refused" error will be resolved, displaying live graphs.



### **Terminal 3: The Chat UI (Guest Interface)**

The primary interface for resort guests to interact with the AI.

* **Command**:
```bash
./.venv/bin/python chat_ui.py

```


* **Endpoint**: `http://127.0.0.1:7861`
* **Configuration**: Ensure the `url` in `chat_ui.py` points to the Backend at `http://127.0.0.1:8000/chat`.

---

## **4. Core System Endpoints**

| Endpoint | Method | Description |
| --- | --- | --- |
| `/chat` | `POST` | Primary entry point for guest messages and AI processing. |
| `/metrics` | `GET` | Raw Prometheus telemetry feed (used by the dashboard). |
| `/invoices/{file_name}` | `GET` | Static file server for downloading generated PDF receipts. |

---

## **5. Knowledge Base & RAG Ingestion**

The MRC uses a RAG system to ensure the AI provides "grounded" answers. The following data is currently ingested:

**Resort Lodgings & Amenities** 

* 
**The Mummy Resort & Tomb-Service**: Offers Sarcophagus Suites and the Afterlife Bistro.


* 
**The Werewolf Lodge: Moon & Moor**: Features Soundproofed Fur-Care Suites and a Primal Buffet.


* 
**Vampire Manor: Eternal Night Inn**: Provides Coffin Suites and the famous Blood Bar.


* 
**Castle Frankenstein**: Luxury stay in Galvanic Suites with a Lightning Spa.



**Operational Policies** 

* 
**Check-in**: Available from 3:00 PM onwards.


* 
**Early Arrival**: Subject to "lair readiness".


* 
**Checkout**: Must be completed by 11:00 AM.


* 
**Nocturnal Guests**: "Moonlight arrival" can be pre-arranged.


* 
**Late Checkout**: May result in a "small broomstick fee".



---

## **6. Operational Monitoring (The Prometheus Layer)**

The system generates raw metrics that indicate both technical health and business performance.

### **Technical Health (Python Runtime)**

* **Garbage Collection**: Monitored via `python_gc_objects_collected_total` to ensure no memory leaks occur during high-traffic intervals.
* **Latency**: Tracked via `mrc_http_request_latency_seconds`. A healthy request (like fetching metrics) typically finishes in ~1.5ms.

### **Business Metrics**

* **`mrc_bookings_total`**: Increments every time a tool call successfully saves a booking to the SQLite DB.
* **`mrc_rag_hits_total`**: Increments every time the AI successfully retrieves data from the `.txt` knowledge files.
* **`mrc_tool_calls_total`**: Tracks the usage of the `book_room` functionality.

---

## **7. Troubleshooting & Common Failures**

### **The "Connection Refused" Loop**

* **Cause**: Dashboard is hardcoded to Port 8000 while Backend is on 8001.
* **Solution**: Always launch the backend with `--port 8000` or set the `PROMETHEUS_URL` environment variable to `http://127.0.0.1:8001/metrics`.

### **RAG "Silent" Failures**

* **Cause**: The AI claims it "doesn't have information" on check-in or specific resorts.
* **Solution**: Check the backend terminal for the `Ingesting knowledge` log. If the count is 0, verify the `data/knowledge` folder path is correct.

---

## **8. Security & Protocol**

* **Authentication**: All `/chat` requests are secured via Bearer tokens managed within `main.py`.
* **Session Management**: UUIDs are generated for every guest session to track conversation history and unique bookings.
* **Data Privacy**: Booking details (Email, Hotel, Dates) are stored in the local `monster_resort.db` and are not shared with external third parties beyond the LLM provider.

---

## **9. Summary of Achievement**

We have created a synchronized ecosystem where **Python 3.12**, **FastAPI**, **Prometheus**, and **Gradio** work in tandem. The system is capable of not only conversing with monsters but managing their entire stay lifecycle—from knowledge retrieval to database persistence and financial documentation.










Based on the system logs and deployment history, several technical "hiccups" were encountered and resolved to reach full operational capacity.

### **1. Port Synchronization (The "Connection Refused" Error)**

The primary hurdle was a communication mismatch between the monitoring dashboard and the backend server.

* **The Issue**: The `metrics_dashboard.py` was hardcoded to look for data on **Port 8000**, while the Backend was running on **Port 8001**.
* **The Symptom**: This resulted in a `NewConnectionError` and "Max retries exceeded" message on the dashboard UI.
* **The Resolution**: The entire stack was synchronized by moving the Backend to Port 8000 and updating the `chat_ui.py` configuration to match.

### **2. Retrieval-Augmented Generation (RAG) Latency**

Early tests showed significant delays in how quickly the AI could "read" the resort files.

* **The Issue**: Initial search queries for house rules and vacancies took as long as **4.22 seconds**.
* **The Resolution**: After re-indexing the `data/knowledge` folder and optimizing the `rag.py` search logic, latency was reduced to a high-performance range of **0.38s to 0.71s**.

### **3. Knowledge Ingestion Gaps**

There were instances where the AI claimed to have no information regarding specific resort policies.

* **The Issue**: The system initially reported `Ingesting 0 documents` because the text files were not correctly placed in the designated `/data/knowledge` directory.
* **The Resolution**: Moving `amenities.txt` and `checkin_checkout.txt` into the correct path allowed the system to successfully ingest details like the **3:00 PM check-in time** and the location of the **Blood Bar**.

### **4. Environment Variable Persistence**

Attempts to fix the port issue via terminal commands (e.g., `export PROMETHEUS_URL`) were initially unsuccessful.

* **The Issue**: The Gradio state in the metrics dashboard was not consistently picking up shell environment variables, leading to persistent "blind spots" where the dashboard couldn't see the live backend.
* **The Resolution**: This was bypassed by standardizing the launch command and ensuring the `main.py` application was explicitly told which port to use during the `uvicorn` startup.

### **5. Tool Registry Initialization**

The AI occasionally failed to trigger the booking tool when requested.

* **The Issue**: The `openai_tool_schemas` were not always ready at the moment of the first user request.
* **The Resolution**: The backend was adjusted to log `tool_registry_ready` before the application startup was considered complete, ensuring that the **book_room** tool was always available for guests like Dracula.