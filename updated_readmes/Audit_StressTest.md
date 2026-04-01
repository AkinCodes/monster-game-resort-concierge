This documentation is designed to be a "Source of Truth" for the Quality Assurance and Reliability phase of the **Monster Resort Concierge** system. It covers the technical specifications, operational procedures, and strategic importance of the refactored `run_audit.py`  and `stress_test.py`.

---

# Confluence: Monster Resort Concierge Reliability & Quality Handbook

## 1. Executive Summary

To ensure a seamless guest experience for our supernatural clientele, the system must be both **accurate** and **resilient**. We utilize two primary testing frameworks:

1. 
**RAG Quality Audit (`run_audit.py`)**: Evaluates the "intelligence" and "honesty" of the AI.


2. **Advanced Stress Test (`stress_test.py`)**: Evaluates the "stamina" and "capacity" of the infrastructure.

---

## 2. Technical Component: RAG Quality Audit (`run_audit.py`)

### 2.1 Role in a High-Value Production Environment

In a production setting, the AI must not "hallucinate" (invent facts). The RAG (Retrieval-Augmented Generation) Audit ensures that the concierge only provides information found in the official knowledge base, such as `amenities.txt` or `checkin_checkout.txt`. It serves as a gatekeeper during CI/CD (Continuous Integration/Continuous Deployment) to prevent low-quality models from reaching the guests.

### 2.2 Core Metrics Explained

The audit focuses on two industry-standard RAGAS metrics:

* **Faithfulness**: Measures if the answer is derived solely from the retrieved context. A low score indicates the AI is making things up.


* 
**Relevancy**: Measures if the answer actually addresses the user's specific query.



### 2.3 How to Run the Audit

The script supports several execution modes via the command line:

| Command | Purpose |
| --- | --- |
| `python run_audit.py` | Standard audit using placeholder answers for a quick check.

 |
| `python run_audit.py --real-answers` | <br>**Recommended for Prod**: Prompts the auditor to enter actual LLM responses for a true accuracy check.

 |
| `python run_audit.py --k 5` | Tests the system's ability to handle larger amounts of retrieved context.

 |
| `python run_audit.py --difficulty hard` | Focuses specifically on complex queries like dietary restrictions or booking combinations.

 |

### 2.4 What to Observe

* 
**Pass Rate**: The script defines a "Pass" as a score  for both faithfulness and relevancy.


* 
**Category Breakdown**: Observe if specific categories (e.g., "Dining" or "Policy") consistently fail, which indicates a need for better documentation in those areas.



---

## 3. Technical Component: Advanced Stress Test (`stress_test.py`)

### 3.1 Role in a High-Value Production Environment

A concierge that takes 30 seconds to respond is as useless as one that is offline. The stress test simulates high-traffic scenarios (e.g., a full moon weekend at the resort) to determine the system's "breaking point".

### 3.2 Importance of the "Ramp-Up" Strategy

Unlike basic tests that hit the server with 100 requests at once, the refactored script uses **Progressive Load Testing**. By gradually increasing concurrency across several steps, we can identify exactly when latency begins to degrade before the system actually crashes.

### 3.3 How to Run the Stress Test

Upon execution, the script provides an interactive menu:

1. **Quick Test**: 20 requests, 5 concurrent. Use for rapid verification after code changes.
2. **Standard Test**: 100 requests, 10 concurrent with ramp-up. Use for weekly reliability reports.
3. **Extreme Test**: 500 requests, 50 concurrent. Use for quarterly capacity planning or before major holidays.

### 3.4 Key Observations & Metrics

* **P99 Latency**: This is the most critical metric. It represents the wait time for the slowest 1% of guests. If P99 is s, the system is failing the user experience.
* **Status Code 429 (Rate Limited)**: In a high-value environment, seeing 429 errors is a **positive sign**—it means your rate limiter is protecting the database from a total collapse.
* **Success Rate**: Total successful (200 OK) requests divided by total attempts. Target: .

---

## 4. Operational "Hiccups" & Troubleshooting

### 4.1 "Connection Refused" (Errno 61)

As seen in recent dashboard logs, this is the most common issue.

* **What it means**: The script is trying to talk to `localhost:8000`, but the server is not listening.
* **Fix**: Verify the backend is running and that no firewall is blocking the port.

### 4.2 "Read Timeout"

* **What it means**: The server accepted the request, but the AI took too long to generate an answer.
* **Observation**: Check if the `request_timeout` in `TestConfig` is set too low (default is 60s).

### 4.3 Low Faithfulness Scores

* 
**What it means**: The AI is "hallucinating" details about the resort (e.g., claiming there is a swimming pool when the docs only mention a Blood Bar).


* **Fix**: Improve the system prompt to explicitly state: "Only use the provided context to answer."

---

## 5. Maintenance & Observability Checklist

| Action Item | Frequency | Responsibility |
| --- | --- | --- |
| Update `GoldStandardTestSet` | When new amenities are added | Content Lead |
| Run "Extreme" Stress Test | Monthly | DevOps |
| Review `stress_test_results_[date].json` | After every major deployment | Tech Lead |
| Export RAG Audit JSON for Compliance | Quarterly | Audit Team |

## 6. Multi-Model Fallback and Confidence Scoring in Tests

### 6.1 Multi-Model Fallback (`app/llm_providers.py`)

The stress test now exercises the **ModelRouter** fallback chain (OpenAI -> Anthropic -> Ollama). When running Option 3 (Extreme), if the primary LLM provider rate-limits or errors out, the system automatically falls back to the next provider. Watch for provider switching in logs during high-concurrency runs -- this is expected and healthy behavior, not a failure.

### 6.2 Confidence Scoring in Audit Results

The RAG Quality Audit should now account for the **confidence** field returned by the `/chat` endpoint. Every response is scored by the `HallucinationDetector` (`app/hallucination.py`) with a `ConfidenceLevel`:

- **HIGH** (score >= 0.7): Response is well-grounded in retrieved context
- **MEDIUM** (score >= 0.4): Response is partially grounded; review recommended
- **LOW** (score < 0.4): Response may contain hallucinations; flag for investigation

When reviewing audit results, cross-reference faithfulness scores with confidence levels. A high faithfulness but LOW confidence may indicate the detector is being overly conservative; a low faithfulness but HIGH confidence indicates the detector needs recalibration.

---

## 7. Conclusion

By utilizing these two refactored scripts, the Monster Resort Concierge moves from a "prototype" to a "production-ready" system. The **RAG Audit** protects the brand's integrity by ensuring information accuracy, while the **Stress Test** protects the system's availability by ensuring it can handle the midnight rush of checking-in ghouls and ghosts.









## **Confluence: Reliability Engineering & Performance Testing Suite**

---

### **1. Overview**

This document outlines the operational procedures for the **Monster Resort Concierge (MRC)** Reliability Suite. We have moved beyond basic connectivity tests into a **High-Value Production (HVP)** framework. By utilizing `run_audit.py` and `stress_test.py`, we ensure that the AI is not only fast but factually accurate and structurally resilient under the weight of hundreds of concurrent "monster" requests.

---

### **2. The Quality Audit Engine (`run_audit.py`)**

#### **A. Role & Importance**

In a production environment, the "cost" of a wrong answer is high. If the AI hallucinated that checkout was at 4:00 PM (instead of 11:00 AM), it would cause operational chaos.

* **Role**: It acts as the "Ground Truth" validator.
* **HVP Utility**: This script is used in **Regression Testing**. Before any new code is deployed, the audit must pass with a score of .

#### **B. How to Run**

Open your terminal and ensure the Backend is active.

| Mode | Command | When to use |
| --- | --- | --- |
| **Standard** | `python run_audit.py` | Daily health check of RAG retrieval. |
| **Filtered** | `python run_audit.py --difficulty hard` | Testing complex logic like "Broomstick fees." |
| **Categorized** | `python run_audit.py --category policy` | Verifying check-in/out rules specifically. |
| **Full Validation** | `python run_audit.py --real-answers` | Final sign-off before a production release. |

#### **C. Potential Hiccups & Observations**

* **Hiccup: `JSONDecodeError**`: Occurs if the AI returns an empty string.
* *Watch for*: Ensure your OpenAI/LLM API keys are active.


* **Hiccup: Low Faithfulness Score**: The AI is "inventing" amenities.
* *Watch for*: Check the `k` value; if `k` is too low, the AI doesn't get enough context to answer correctly.



---

### **3. The Advanced Stress Tester (`stress_test.py`)**

#### **A. Role & Importance**

Hardware and software behave differently when "hot." This script simulates a "Midnight Rush"—where 10 or 50 ghouls are all checking in simultaneously.

* **Role**: Capacity Planning and Bottleneck Discovery.
* **HVP Utility**: It defines the **SLA (Service Level Agreement)**. If we know the system breaks at 50 concurrent users, we set our production limits at 40.

#### **B. How to Run**

Launch this in a separate terminal while Terminal 1 (Backend) is running.

```bash
# Standard interactive execution
python stress_test.py

```

**Upon running, select your "Stress Level":**

1. **Select `1` (Quick)**: Verifies that the rate limiter is working.
2. **Select `2` (Standard)**: The baseline for production-ready code.
3. **Select `3` (Extreme)**: Only run this on high-spec staging servers to find the "Kill Point."

#### **C. What to Observe (The "Red Flags")**

* **P99 Latency > 15s**: The slowest guests are waiting too long. This usually means the Python `ThreadPoolExecutor` is saturated.
* **Status 504 (Gateway Timeout)**: The server is taking so long to process the RAG search that the connection is dropping.
* **Standard Deviation (StdDev) > 5.0**: This means the system is "jittery"—some guests get fast answers, others wait forever. You want a low StdDev for a premium resort experience.

---

### **4. Deployment Checklist for Production Readiness**

To certify a build as "Production Ready," the following steps must be completed in order:

1. **Initialize Backend**:
`uvicorn app.main:app --port 8000 --timeout-keep-alive 60`
2. **Verify Knowledge**:
Run `run_audit.py`. **Goal**: Pass rate .
3. **Pressure Test**:
Run `stress_test.py` (Option 2). **Goal**: Success rate .
4. **Analyze Metrics**:
Check the Gradio Dashboard for any memory spikes during the stress test.

---

### **5. Summary of Roles**

* **`run_audit.py`**: Protects the **Brand** (Information Accuracy).
* **`stress_test.py`**: Protects the **Infrastructure** (System Availability).

Together, these files ensure that the Monster Resort remains the #1 choice for ghouls who value both high-tech service and reliable sarcophagus suites.

**Would you like me to create a "Master Launch Script" that runs both of these automatically and generates a single PDF "Readiness Certificate"?**








# Confluence: Comprehensive Reliability & Quality Assurance Guide

This document serves as the official SOP (Standard Operating Procedure) for the **Monster Resort Concierge** reliability suite. It details the technical implementation, operational commands, and strategic importance of our refactored testing framework.

---

## 1. Quality Audit Framework (`run_audit.py`)

### Role and Importance

In a high-value production (HVP) environment, the "cost" of a wrong answer is significant. If the AI incorrectly informs a guest about check-out times or spa availability, it results in operational friction and loss of trust.

* **Role**: Acts as the "Ground Truth" validator to ensure the RAG (Retrieval-Augmented Generation) system is grounded in official resort documents.
* **HVP Utility**: Used for **Regression Testing**. Every major knowledge base update must be audited to ensure no "hallucinations" have been introduced.

### How to Run: Execution Commands

Navigate to the project root and ensure your virtual environment is active. Run the following commands based on your testing requirements:

| Test Scenario | Terminal Command | Purpose |
| --- | --- | --- |
| **Standard Audit** | `python run_audit.py` | Runs the default suite with placeholder answers to verify the retrieval pipeline is functional. |
| **Real LLM Validation** | `python run_audit.py --real-answers` | **Recommended for Prod**: Prompts the user to input actual AI responses for a true accuracy and faithfulness score. |
| **Targeted Stress** | `python run_audit.py --difficulty hard` | Filters the test set to focus only on complex queries like multi-service bookings or dietary restrictions. |
| **Increased Context** | `python run_audit.py --k 5` | Tests how the AI performs when given 5 document chunks instead of the default 2. |

### Observation Points

* **Faithfulness Score**: Measures if the answer is derived *only* from the provided context. A score below 0.7 indicates the AI is making up details not found in resort files.
* **Relevancy Score**: Measures how well the answer addresses the specific user query. Low scores here suggest the retrieval system is fetching the wrong documents.

---

## 2. Advanced Stress Test (`stress_test.py`)

### Role and Importance

The stress test evaluates the "stamina" of the infrastructure. In production, we must know the system's "breaking point" before real-world traffic reaches that threshold.

* **Role**: Capacity planning and bottleneck identification.
* **HVP Utility**: Establishes the **SLA (Service Level Agreement)**. If the system fails at 50 concurrent users, the production load balancer must be capped at 40.

### How to Run: Operational Modes

Open a terminal dedicated to testing. Ensure the backend server (`uvicorn`) is running in a separate window.

```bash
# Launch the interactive tester
python stress_test.py

```

**Upon launching, you will be prompted to select a mode:**

1. **Option 1 (Quick Test)**: 20 requests, 5 concurrent. Use this for a "smoke test" after updating server configurations.
2. **Option 2 (Standard Test)**: 100 requests, 10 concurrent with a 3-step ramp-up. This is the **baseline** for certifying a build for production.
3. **Option 3 (Extreme Test)**: 500 requests, 50 concurrent. Use this to test the limits of the rate limiter and database connection pooling.

### Observation Points (The "Red Flags")

* **P99 Latency**: Look at the P99 percentile. If the slowest 1% of requests take more than 15 seconds, the system is considered unresponsive for premium guests.
* **Status 429 (Rate Limited)**: In a high-value environment, 429s are a **success**. They prove the system is successfully protecting itself from a crash.
* **Standard Deviation (StdDev)**: A high StdDev indicates "jittery" performance where some users get instant answers while others wait indefinitely.

---

## 3. Potential Hiccups and Troubleshooting

| Symptom | Cause | Solution |
| --- | --- | --- |
| **"Connection Refused" (Errno 61)** | Backend server is not running on Port 8000. | Start the backend: `uvicorn app.main:app --port 8000`. |
| **"Request Timed Out" (504)** | The LLM took longer than the configured 60s to think. | Increase `request_timeout` in the `TestConfig` class or check API health. |
| **"No Context Retrieved"** | The search query didn't match anything in the vector database. | Re-index the resort files or adjust the embedding model settings. |
| **Low Pass Rate (<70%)** | The AI prompt is too loose, or the knowledge base is missing key data. | Refine the system prompt to enforce "grounding" and verify document content. |

---

## 4. Summary of Strategic Roles

* **`run_audit.py`**: Protects the **Brand Integrity** (Information Accuracy).
* **`stress_test.py`**: Protects the **Infrastructure** (System Availability).

Would you like me to generate a **Master Launch Script** that executes both tests sequentially and compiles a single "Production Readiness Report" PDF?