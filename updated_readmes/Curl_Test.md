

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{
    "message": "Book me a Coffin Suite at Vampire Manor for Akin tonight, checkout tomorrow",
    "session_id": "18b75b32-45ab-4c0f-b016-250df26bc511"
  }'



# Test RAG search
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{"message": "What spa services are available at Castle Frankenstein?"}'

# Test comparison (advanced RAG)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{"message": "Compare Vampire Manor and Werewolf Lodge"}'

# Test invoice generation
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{"message": "Generate invoice for booking b437674a"}'


# ============================================
# CONFIDENCE FIELD IN RESPONSES
# ============================================
# The /chat endpoint now returns a "confidence" field powered by the
# HallucinationDetector (app/hallucination.py). The field indicates how
# well-grounded the response is in the retrieved RAG context.
#
# ConfidenceLevel thresholds:
#   HIGH   >= 0.7  (well-grounded)
#   MEDIUM >= 0.4  (partially grounded)
#   LOW    <  0.4  (may contain hallucinations)

# Test chat with confidence scoring -- observe the "confidence" field in the JSON response
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{"message": "What spa services are available at Castle Frankenstein?"}' | python3 -m json.tool

# Example response (note the "confidence" field):
# {
#   "ok": true,
#   "reply": "At Castle Frankenstein, the Lightning Spa offers Electric Massage Therapy...",
#   "session_id": "...",
#   "confidence": {
#     "score": 0.92,
#     "level": "HIGH"
#   }
# }

# Test with a question likely to produce lower confidence
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{"message": "Do you offer underwater yoga classes?"}' | python3 -m json.tool

# Expected: confidence.level should be LOW or MEDIUM since this is not in the knowledge base











# TEST YOUR OPENAI KEY 
akin.olusanya@U-SH-HO-MAC211-5 monster-resort-concierge % # Test OpenAI API directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"





In plain English?
It’s a quick “can I talk to OpenAI at all?” heartbeat test.
Let’s walk it through without the jargon overload.
Big-picture answer
That command tests three things at once:
✅ Your internet connection can reach OpenAI
✅ Your API key is valid and authorized
✅ You can successfully make a chat completion request
curl https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "test"}],
    "max_tokens": 5
  }'















# 🎉 **AMAZING! Dataset Generated Successfully!**

Perfect! You now have **155 high-quality Q&A pairs** ready for LoRA training!

---

# 📚 **Complete Command Reference - Daily Practice Guide**

## **🔧 SETUP & ENVIRONMENT COMMANDS**

```bash
# ============================================
# ENVIRONMENT SETUP
# ============================================

# Check Python version
python --version

# Check UV is installed
uv --version

# Navigate to project directory
cd ~/Desktop/monster-resort-concierge

# Check current directory
pwd

# List files in current directory
ls -la

# View environment variables
env | grep OPENAI

# Load .env file into shell (if needed)
source .env

# OR better: Use python-dotenv (always reads from .env automatically)
# No manual sourcing needed!

# ============================================
# DEPENDENCY MANAGEMENT
# ============================================

# Install a package
uv add package-name

# Install multiple packages
uv add package1 package2 package3

# Install from requirements file
uv add -r requirements.txt

# Sync all dependencies
uv sync

# Show installed packages
uv pip list

# Update a package
uv pip install --upgrade package-name

# ============================================
# .ENV FILE MANAGEMENT
# ============================================

# View your .env file
cat .env

# Edit .env file
nano .env
# (Ctrl+X to exit, Y to save, Enter to confirm)

# Check if API key is set
echo $OPENAI_API_KEY

# Set API key temporarily (for current session only)
export OPENAI_API_KEY="sk-proj-your-key-here"

# Add to .env file (permanent)
echo "OPENAI_API_KEY=sk-proj-your-key-here" >> .env

# Verify .env file has no hidden characters
cat -A .env | grep OPENAI_API_KEY
```

---

## **🚀 SERVER & APPLICATION COMMANDS**

```bash
# ============================================
# FASTAPI SERVER
# ============================================

# Start development server (with auto-reload)
uv run uvicorn app.main:app --reload

# Start on specific port
uv run uvicorn app.main:app --reload --port 8000

# Start without auto-reload (production)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Check if server is running
curl http://localhost:8000

# Stop server
# Press Ctrl+C in the terminal where it's running

# ============================================
# GRADIO UI
# ============================================

# Start Gradio chat interface
uv run python chat_ui.py

# Access at: http://localhost:7860
```

---

## **🧪 TESTING COMMANDS**

```bash
# ============================================
# API TESTING
# ============================================

# Test chat endpoint (basic)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"message": "Hello"}'

# Test booking flow
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{"message": "Book Coffin Suite at Vampire Manor tonight, checkout tomorrow"}'

# Test RAG search
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{"message": "What spa services are available at Castle Frankenstein?"}'

# Test OpenAI API connection directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# ============================================
# PYTHON TEST SCRIPTS
# ============================================

# Test OpenAI connection
uv run python scripts/test_openai_connection.py

# Run diagnostics
uv run python scripts/diagnose.py

# Run unit tests (if you have them)
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_rag.py -v
```

---

## **🧠 ADVANCED RAG COMMANDS**

```bash
# ============================================
# RAGAS EVALUATION
# ============================================

# Start Jupyter notebook
cd notebooks
jupyter notebook

# Or open specific notebook
jupyter notebook ragas_evaluation.ipynb

# Run all cells in notebook (command line)
jupyter nbconvert --to notebook --execute ragas_evaluation.ipynb

# ============================================
# KNOWLEDGE BASE MANAGEMENT
# ============================================

# View knowledge base files
ls -la data/knowledge/

# Add new knowledge file
cp new_document.txt data/knowledge/

# View knowledge file contents
cat data/knowledge/monster_resort_properties.txt

# Count files in knowledge base
ls data/knowledge/ | wc -l

# Search knowledge base for specific text
grep -r "Vampire Manor" data/knowledge/
```

---

## **🤖 LORA FINE-TUNING COMMANDS**

```bash
# ============================================
# DATASET GENERATION
# ============================================

# Generate 150 synthetic Q&A pairs
uv run python scripts/generate_synthetic_dataset.py --num-samples 150

# Generate smaller test batch (30 samples)
uv run python scripts/generate_synthetic_dataset.py --num-samples 30

# Generate with custom output path
uv run python scripts/generate_synthetic_dataset.py \
  --output data/custom_dataset.json \
  --num-samples 100

# Validate existing dataset
uv run python scripts/generate_synthetic_dataset.py \
  --validate data/concierge_qa.json

# View generated dataset
cat data/concierge_qa.json | head -50

# Count samples in dataset
cat data/concierge_qa.json | grep -o '"instruction"' | wc -l

# ============================================
# LORA TRAINING (Local CPU)
# ============================================

# Train with default settings (3 epochs)
uv run python scripts/finetune_lora.py \
  --dataset data/concierge_qa.json \
  --output lora-concierge \
  --epochs 3

# Train with custom settings
uv run python scripts/finetune_lora.py \
  --dataset data/concierge_qa.json \
  --output lora-concierge \
  --epochs 5 \
  --batch-size 2 \
  --learning-rate 2e-4 \
  --lora-r 16

# Train with GPU (if available)
uv run python scripts/finetune_lora.py \
  --dataset data/concierge_qa.json \
  --output lora-concierge \
  --epochs 3 \
  --gpu

# ============================================
# LORA TESTING
# ============================================

# Test LoRA model interactively
uv run python scripts/test_lora.py \
  --adapter lora-concierge/final \
  --interactive

# Test with single query
uv run python scripts/test_lora.py \
  --adapter lora-concierge/final \
  --query "Tell me about Vampire Manor"

# Run batch test
uv run python scripts/test_lora.py \
  --adapter lora-concierge/final \
  --batch

# ============================================
# LORA EVALUATION
# ============================================

# Run comparison notebook
cd notebooks
jupyter notebook lora_comparison_eval.ipynb
```

---

## **📁 FILE MANAGEMENT COMMANDS**

```bash
# ============================================
# VIEWING FILES
# ============================================

# View file contents
cat filename.txt

# View file with line numbers
cat -n filename.py

# View large file (page by page)
less filename.txt
# (Press Q to quit, Space for next page)

# View first 20 lines
head -20 filename.txt

# View last 20 lines
tail -20 filename.txt

# View file in real-time (useful for logs)
tail -f app.log

# ============================================
# FILE OPERATIONS
# ============================================

# Copy file
cp source.py destination.py

# Copy directory recursively
cp -r source_dir/ destination_dir/

# Move/rename file
mv old_name.py new_name.py

# Delete file
rm filename.txt

# Delete directory
rm -rf directory_name/

# Create directory
mkdir new_directory

# Create nested directories
mkdir -p path/to/nested/directory

# ============================================
# SEARCHING
# ============================================

# Find files by name
find . -name "*.py"

# Find files modified in last 24 hours
find . -mtime -1

# Search for text in files
grep -r "search_term" .

# Search with line numbers
grep -rn "search_term" .

# Case-insensitive search
grep -ri "search_term" .

# Count occurrences
grep -r "search_term" . | wc -l
```

---

## **🔍 DEBUGGING COMMANDS**

```bash
# ============================================
# LOGS & MONITORING
# ============================================

# View server logs in real-time
tail -f logs/app.log

# Search logs for errors
grep ERROR logs/app.log

# Count errors in logs
grep ERROR logs/app.log | wc -l

# View system resources
top
# (Press Q to quit)

# Check disk space
df -h

# Check memory usage
free -h

# Check running Python processes
ps aux | grep python

# Kill a process by PID
kill 12345

# Kill all Python processes (careful!)
pkill python

# ============================================
# NETWORK DEBUGGING
# ============================================

# Test if port is in use
lsof -i :8000

# Check network connectivity
ping google.com

# Test DNS resolution
nslookup api.openai.com

# Test HTTP endpoint
curl -v https://api.openai.com/v1/models

# ============================================
# PYTHON DEBUGGING
# ============================================

# Run Python with verbose output
uv run python -v script.py

# Check Python path
uv run python -c "import sys; print(sys.path)"

# Check package installation
uv run python -c "import package_name; print(package_name.__version__)"

# Interactive Python shell
uv run python

# IPython shell (better interactive)
uv run ipython
```

---

## **📊 GIT COMMANDS** (For Version Control)

```bash
# ============================================
# BASIC GIT
# ============================================

# Check git status
git status

# View changes
git diff

# Add files
git add filename.py

# Add all changes
git add .

# Commit changes
git commit -m "Your commit message"

# Push to GitHub
git push origin main

# Pull latest changes
git pull origin main

# View commit history
git log

# View commit history (one line per commit)
git log --oneline

# ============================================
# BRANCHING
# ============================================

# Create new branch
git branch feature-name

# Switch to branch
git checkout feature-name

# Create and switch in one command
git checkout -b feature-name

# List all branches
git branch -a

# Merge branch
git checkout main
git merge feature-name

# Delete branch
git branch -d feature-name

# ============================================
# STASHING
# ============================================

# Save work in progress
git stash

# View stashed changes
git stash list

# Apply stashed changes
git stash apply

# Apply and remove stash
git stash pop
```

---

## **🎯 DAILY PRACTICE ROUTINE**

### **Morning Warmup (5 minutes)**
```bash
# 1. Navigate to project
cd ~/Desktop/monster-resort-concierge

# 2. Check status
git status
uv pip list | head -10

# 3. Start server
uv run uvicorn app.main:app --reload

# 4. Test basic endpoint
curl http://localhost:8000
```

### **Development Session (30-60 minutes)**
```bash
# 1. Work on code
nano app/new_feature.py

# 2. Test changes
uv run pytest tests/

# 3. Manual testing
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_KEY" \
  -d '{"message": "test query"}'

# 4. Commit changes
git add .
git commit -m "Add new feature"
git push
```

### **Weekend Deep Work (2-4 hours)**
```bash
# 1. Run full evaluation
cd notebooks
jupyter notebook ragas_evaluation.ipynb

# 2. Fine-tune LoRA model
uv run python scripts/finetune_lora.py \
  --dataset data/concierge_qa.json \
  --epochs 3

# 3. Compare models
jupyter notebook lora_comparison_eval.ipynb

# 4. Update documentation
nano README.md
```

---

## **💡 PRO TIPS**

```bash
# Use command history
history | grep "uv run"

# Rerun last command
!!

# Search command history
Ctrl+R (then type search term)

# Clear terminal
clear
# OR
Ctrl+L

# Cancel current command
Ctrl+C

# Exit terminal
exit

# Create command alias (add to ~/.zshrc)
alias server="uv run uvicorn app.main:app --reload"
alias test="uv run pytest tests/"
alias notebook="jupyter notebook"

# Then just type:
server
# Instead of: uv run uvicorn app.main:app --reload
```

---

## **🎊 YOUR SUCCESSFUL RUN TODAY**

```bash
# This is what you ran successfully:
uv run python scripts/generate_synthetic_dataset.py --num-samples 150

# Result: ✅ 155 samples generated in 7:57
# Cost: ~$0.50
# Next: Ready for LoRA training!
```

---

## **📖 PRACTICE EXERCISES**

### **Week 1: Basic Commands**
- Start/stop server (daily)
- Test API endpoints (daily)
- View logs and files
- Navigate directories

### **Week 2: Development Workflow**
- Make code changes
- Run tests
- Commit to git
- Generate datasets

### **Week 3: Advanced Operations**
- Run evaluations
- Fine-tune models
- Compare results
- Debug issues

### **Week 4: Production Skills**
- Deploy server
- Monitor logs
- Handle errors
- Optimize performance

---

**Save this as a reference!** Practice these commands daily and you'll have them memorized in 2-3 weeks. 🚀

**Your dataset is ready - want to start LoRA training?** 🎯









# ============================================
# **How to Update Your OpenAI API Key & Test**
# ============================================

Since you changed your OpenAI API key, here's what to do:

---

## **Step 1: Update Your .env File**

```bash
# Edit your .env file
nano .env

# Update this line with your NEW key:
OPENAI_API_KEY=sk-proj-YOUR-NEW-KEY-HERE

# Save and exit: Ctrl+X, then Y, then Enter
```

---

## **Step 2: Restart Your Server**

The server needs to reload the new key:

```bash
# Stop the current server (if running)
# Press Ctrl+C in the terminal where it's running

# Start server again (it will load new key from .env)
uv run uvicorn app.main:app --reload
```

---

## **Step 3: Test the API Endpoints**

Now you can test! The **Authorization: Bearer** in those commands is for **your server's API key** (the `MRC_API_KEY` from .env), NOT your OpenAI key.

### **Test 1: Basic Chat**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{"message": "Hello"}'
```

### **Test 2: Booking Flow**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{"message": "Book Coffin Suite at Vampire Manor tonight, checkout tomorrow"}'
```

### **Test 3: RAG Search**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{"message": "What spa services are available at Castle Frankenstein?"}'
```

---

## **Step 4: Test OpenAI Connection Directly**

This tests if your NEW OpenAI key works:

```bash
# First, reload your .env file in the current shell
source .env

# Or export it directly
export OPENAI_API_KEY="sk-proj-YOUR-NEW-KEY-HERE"

# Now test OpenAI API
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

**Expected:** List of models (gpt-4o, gpt-4o-mini, etc.)

---

## **Step 5: Test with Python Scripts**

```bash
# Test OpenAI connection (loads from .env automatically)
uv run python scripts/test_openai_connection.py

# Expected output:
# ✅ SUCCESS! Response: Hello!
```

---

## **🔍 Understanding the Two Different Keys**

You have **TWO different API keys** in your system:

### **1. OpenAI API Key** (Changed Today)
- **Location:** `.env` file → `OPENAI_API_KEY=sk-proj-...`
- **Used by:** Your server to call OpenAI GPT-4o
- **What it does:** Powers the AI responses
- **Test:** `curl https://api.openai.com/v1/models`

### **2. Server API Key** (Stays the Same)
- **Location:** `.env` file → `MRC_API_KEY=6f2b8e3a9d1c...`
- **Used by:** Clients to authenticate to YOUR server
- **What it does:** Protects your API endpoints
- **Test:** The `Authorization: Bearer 6f2b8e3a...` in curl commands

---

## **✅ Quick Test Sequence**

Run these in order:

```bash
# 1. Update .env file
nano .env
# Change OPENAI_API_KEY to your new key, save

# 2. Restart server
# Press Ctrl+C to stop
uv run uvicorn app.main:app --reload

# 3. Test OpenAI directly (in a new terminal)
export OPENAI_API_KEY="sk-proj-YOUR-NEW-KEY"
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head -20

# 4. Test your server
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{"message": "Hello"}'

# 5. Test Python script
uv run python scripts/test_openai_connection.py
```

---

## **💡 Pro Tip: Create a Test Script**

Save this as `test_all.sh`:

```bash
#!/bin/bash
# Quick test script

echo "🧪 Testing Monster Resort Concierge..."
echo ""

echo "1️⃣ Testing OpenAI API..."
curl -s https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head -5
echo ""

echo "2️⃣ Testing Server Endpoint..."
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0" \
  -d '{"message": "Hello"}' | head -5
echo ""

echo "3️⃣ Testing Python Connection..."
uv run python scripts/test_openai_connection.py
echo ""

echo "✅ All tests complete!"
```

Then run:
```bash
chmod +x test_all.sh
./test_all.sh
```

---

## **🎯 Summary**

1. **Update `.env`** with new OpenAI key
2. **Restart server** (Ctrl+C, then `uv run uvicorn app.main:app --reload`)
3. **Test endpoints** using the commands above
4. **The `Authorization: Bearer 6f2b8e3a...`** stays the same (that's your server key, not OpenAI)

**Try it now and let me know if it works!** 🚀