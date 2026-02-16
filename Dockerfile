FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p ./generated_pdfs ./.rag_store

# Non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

# Run with production server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]



# 📦 Dockerfile
# This file is a recipe for your app.
# It explains how to build a clean, portable box that contains Python, your code, and everything it needs to run.
# Anyone can use this recipe to run your app the same way, on any computer.




# so if I have several servers APIs (maybe 3), that needs starting, 
# why do I have to have instructions for how to build just one of those mini-servers. 
# what happens to the others 
# This is a really good question, and it means you’re thinking about this the right way.
# Let’s answer it cleanly, without analogies first — then I’ll add one small one at the end.

# The direct answer
# You only write a Dockerfile for a server you own and build yourself.
# The other servers already come built.






# so if I have several servers APIs (maybe 3), that needs starting, why do I have to have instructions 
# for how to build just one of those mini-servers. what happens to the others 

# This is a **really good question**, and it means you’re thinking about this the *right* way.

# Let’s answer it cleanly, without analogies first — then I’ll add one small one at the end.

# ---

# ## The direct answer

# You only write a **Dockerfile** for a server **you own and build yourself**.

# The *other* servers already come built.

# ---

# ## What happens to the others?

# In your setup:

# ### 1️⃣ Your API

# * This is **your code**
# * Docker has no idea how to run it
# * So **you must explain how to build it**
#   → that’s the **Dockerfile**

# ### 2️⃣ Prometheus

# ```yaml
# image: prom/prometheus:latest
# ```

# * Prometheus already has a **pre-built Docker image**
# * Someone else wrote its Dockerfile
# * You just download and run it

# ### 3️⃣ Grafana

# ```yaml
# image: grafana/grafana:latest
# ```

# * Same story
# * Prebuilt, ready to go

# ---

# ## Key idea (this is the “aha”)

# > **Every running container comes from an image.
# > Every image was created from a Dockerfile — just not always yours.**

# * Your API → **your Dockerfile**
# * Prometheus → **their Dockerfile**
# * Grafana → **their Dockerfile**

# You don’t see the others because they’re already packaged.

# ---

# ## Why this separation matters

# * Your app changes → you rebuild *your* image
# * Prometheus doesn’t change → you reuse its image
# * Clear responsibility boundaries
# * Faster startup
# * Less duplication

# ---

# ## Tiny analogy (clean this time)

# * You **cook your own dish** → you write the recipe
# * You **order takeout** → someone else already cooked it

# docker-compose just puts all the food on the table together.

# ---

# ## One sentence to lock it in

# > **You write a Dockerfile only for software that doesn’t already come as a ready-made image.**

# If you want next, I can explain **images vs containers** in the same straight style, because 
# that’s the final missing puzzle piece.



# Exactly — that’s a **perfect way to put it**! 🎯

# Let me restate it slightly tighter:

# * **Dockerfile** → “starts my music player” (the core app I built)
# * **docker-compose** → “starts all the supporting systems I 
# rely on” (databases, monitoring, dashboards, etc.) so the music player actually works reliably

# Without the Dockerfile → no music player.
# Without docker-compose → the player might start, but things it depends on (water, gas, electricity) 
# aren’t ready, so it could fail or behave unpredictably.

# You’ve basically nailed the **core distinction** between the two.

# If you want, I can now **explain Prometheus and Grafana in the same analogy**, 
# so the whole ecosystem clicks.




# so docker file is what starts the concert and keeps it a success - 
# with the stage, the sound, the lighting etc. the files (band) just need to play 
# Exactly — that’s spot on! 🎸🎤💡
# Dockerfile = the stage, lighting, sound system, electricity — everything needed for the show to run smoothly.
# Your files (main.py, rag.py, APIs, etc.) = the band — they only perform once the stage is ready.
# CMD in Dockerfile = the cue to start the concert — the lead singer steps on stage and the music begins.
# Without the Dockerfile, the band could be ready, but no stage, no lights, no sound → nothing works.
# This is exactly how it works for your app.
# If you want, I can now tie docker-compose into the same concert analogy, so you can see how multiple “bands and stages” work together. Do you want me to do that?








# Perfect question — let’s be **very precise**.
# From your Dockerfile, here’s **what is truly “yours” vs what comes from outside**:
# ---
# ## ✅ Built by you (your code / your responsibility)

# 1. **Your application code**

#    * `COPY . .` brings in **all the files in your project**: `main.py`, `rag.py`, APIs, helper modules, etc.
#    * These are **your logic, your features, your “concert”**.

# 2. **Your setup inside the container**

#    * Directories you create: `./generated_pdfs` and `./.rag_store`
#    * User setup: `appuser`
#    * Healthcheck command: `python -c "import httpx; httpx.get(...)"`
#    * Port exposure: `EXPOSE 8000`

# These are things you **configure** to make your app work and run safely.
# They’re part of your “stage and backstage” in the concert analogy.

# ---

# ## 📦 From external vendors (pre-built / third-party)

# 1. **Python base image**:

#    ```dockerfile
#    FROM python:3.11-slim
#    ```

#    * You didn’t build Python — someone else packaged it.
#    * This is like **buying a pre-wired stage with basic lights**.

# 2. **System packages / libraries**:

#    ```dockerfile
#    RUN apt-get install -y build-essential
#    RUN pip install -r requirements.txt
#    ```

#    * These are **tools and dependencies your code needs**, but they’re pre-built by others.
#    * Like renting a soundboard, microphone, or instruments.

# 3. **Uvicorn server**:

#    ```dockerfile
#    CMD ["uvicorn", "app.main:app", ...]
#    ```

#    * The server that runs your app is a **third-party program**, like hiring a stage manager who knows how to cue the lights and music.

# ---

# ### ✅ One-sentence summary

# > **What’s truly yours:** all the app code, custom folders, healthcheck logic, and container configuration.
# > **What’s from external vendors:** Python itself, libraries, tools, and the production server that actually “runs” your code.

# ---

# If you want, I can **highlight each line of your Dockerfile and mark which part is “yours” vs “external”** — it becomes immediately obvious.

# Do you want me to do that?
