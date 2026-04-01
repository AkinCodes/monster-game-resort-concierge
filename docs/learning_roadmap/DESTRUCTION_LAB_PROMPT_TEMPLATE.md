# Destruction Lab — Reusable Prompt Template

Copy the prompt below and paste it into a new Claude conversation when you're inside any project directory. Replace the `[PLACEHOLDERS]` with your project's details.

---

## THE PROMPT

```
I want you to create a "Destruction Lab" — an interactive HTML learning guide for my project. The concept: for every important file in the codebase, document what happens if you DELETE it. This teaches how the system fits together through controlled destruction.

**My project:** [BRIEF DESCRIPTION — e.g., "A FastAPI backend that serves as an AI-powered hotel concierge with RAG, tool calling, and auth"]

**Tech stack:** [e.g., Python/FastAPI, Node/Express, Go/Gin, React/Next.js, etc.]

**Entry point:** [e.g., "app/main.py", "src/index.ts", "cmd/server/main.go"]

**Test command:** [e.g., "pytest tests/", "npm test", "go test ./..."]

**Run command:** [e.g., "uvicorn app.main:app", "npm run dev", "go run cmd/server/main.go"]

---

First, analyze my entire codebase. Map out:
1. Every file and what it does (read them all)
2. The full import/dependency graph (who imports who)
3. The request flow from entry point to response
4. Which tests cover which files

Then generate a single self-contained HTML file called `destruction_lab.html` with this structure:

---

### Overall page structure:

- **Confluence/wiki-style design** — clean, professional, readable. Use Inter + JetBrains Mono fonts.
- **Breadcrumb nav** at top (Project > Engineering > Destruction Lab)
- **Page header** with title "Destruction Lab: What Breaks If I Delete This?"
- **"How to use this guide" panel** at the top explaining the loop:
  1. Read the "What Breaks" section for a file
  2. Actually delete or comment out the file
  3. Run the test command and observe failures
  4. Try to start the server and observe errors
  5. Restore the file
  6. Repeat for next file
- **Table of contents** linking to each phase
- **System Overview section** with:
  - ASCII-art request flow diagram showing the full path from input to output
  - Dependency tree showing what imports what
- **Expand All / Collapse All** buttons

### File grouping — organize files into PHASES by destruction severity:

- **Phase 1 — The Skeleton** (CRITICAL — deleting these kills the entire app)
  Files that are imported by everything: config, database, entry point, core models

- **Phase 2 — The Brain** (HIGH — app runs but core functionality is dead)
  Business logic, service layer, API clients, the "smart" parts

- **Phase 3 — The Guardrails** (MEDIUM — app works but is unsafe/unmonitored)
  Auth, validation, rate limiting, logging, monitoring, error handling

- **Phase 4 — The Features** (MEDIUM — specific features break)
  Individual feature modules, utilities, helpers

- **Phase 5 — The ML/Data Layer** (if applicable — intelligence degrades)
  ML models, embeddings, search, recommendation engines

- **Phase 6 — The Deployment** (LOW — app works locally but can't deploy)
  Dockerfiles, CI/CD, infra config, scripts

Each phase gets a colored severity banner (red/yellow/blue/green).

### For EACH file, create a collapsible card containing:

1. **File path** as monospace header (e.g., `app/config.py`)
2. **Severity badge** (Fatal / High / Medium / Low)
3. **Purpose** — 1-2 sentences: what this file does and why it exists
4. **"WHAT BREAKS IF YOU DELETE THIS"** (red box) — bullet list of SPECIFIC failures:
   - Name the exact file and line number that throws ImportError
   - Name the exact function that fails
   - Describe the user-visible symptom (e.g., "server won't start", "all API calls return 500", "auth is bypassed")
   - Describe cascading failures (A breaks, which means B also breaks, which means C also breaks)
5. **"WHO DEPENDS ON THIS FILE"** (blue box) — list every file that imports this one, with the specific import statement
6. **"TESTS THAT BREAK"** (green box) — list specific test names (test_file.py::test_name) and what they assert
7. **"INTERVIEW QUESTIONS THIS PREPARES YOU FOR"** (purple box) — 2-4 interview questions this file's concepts connect to, with brief answer sketches showing you understand the pattern
8. **"Key code to understand"** — the most important 5-15 lines of code from this file, syntax-highlighted, with comments explaining what each part does

### End sections:

- **Interview Cheat Sheet** — a summary table: Concept | File | One-line explanation
- **Destruction Exercises** — 5-8 graduated exercises:
  1. Easy: delete a leaf file, observe, restore
  2. Medium: delete a mid-level file, trace the cascade
  3. Hard: delete a core file, count how many things break
  4. Expert: delete TWO files at once, observe compound failures
  5. Boss: try to rebuild a deleted file from scratch using only the error messages as guidance

---

### Design requirements:

- Single self-contained HTML file (all CSS inline, no external dependencies except Google Fonts CDN)
- Color-coded panels: red (breaks), blue (dependencies), green (tests), purple (interview), yellow (warnings)
- Collapsible file cards with smooth toggle
- Dark-themed syntax-highlighted code blocks (Catppuccin-style)
- Severity meter bars (visual indicator)
- Professional — looks like internal engineering documentation
- JavaScript at the bottom for expand/collapse functionality

---

### Quality standards — be SPECIFIC, not generic:

- BAD: "Other modules will fail"
- GOOD: "ImportError in main.py line 18: `from .config import get_settings` — server won't start"
- BAD: "Tests break"
- GOOD: "test_unit_core.py::test_settings_load fails — asserts Settings() has app_name, database_url"
- BAD: "This file handles auth"
- GOOD: "JWT token validation. Decodes RS256 tokens, checks expiry, extracts user_id. Falls back to API key auth if no Bearer token."

Read every file. Trace every import. Name specific lines. This is a precision tool, not a summary.
```

---

## QUICK-START EXAMPLES

### For a Node.js/Express API:
```
My project: Express REST API for a task management app with PostgreSQL and Redis caching
Tech stack: Node.js/Express/TypeScript, Prisma ORM, Redis, Jest
Entry point: src/index.ts
Test command: npm test
Run command: npm run dev
```

### For a React/Next.js Frontend:
```
My project: Next.js e-commerce storefront with cart, checkout, and Stripe integration
Tech stack: Next.js 14 (App Router), TypeScript, Tailwind, Zustand, Stripe SDK
Entry point: app/layout.tsx
Test command: npm test
Run command: npm run dev
```

### For a Go microservice:
```
My project: Go gRPC microservice for user authentication with JWT and Redis sessions
Tech stack: Go, gRPC, PostgreSQL, Redis, Wire DI
Entry point: cmd/server/main.go
Test command: go test ./...
Run command: go run cmd/server/main.go
```

### For a Django app:
```
My project: Django REST Framework API for a social media platform with feeds, notifications, and real-time chat
Tech stack: Python/Django/DRF, PostgreSQL, Celery, Redis, WebSockets
Entry point: manage.py / config/urls.py
Test command: python manage.py test
Run command: python manage.py runserver
```

### For a Flutter mobile app:
```
My project: Flutter mobile app for food delivery with real-time tracking and payment
Tech stack: Flutter/Dart, Riverpod, Firebase, Google Maps SDK
Entry point: lib/main.dart
Test command: flutter test
Run command: flutter run
```

---

## TIPS FOR BEST RESULTS

1. **Run this in Claude Code (CLI)** so Claude can actually read all your files — it produces much more specific results when it can see the actual code vs. you pasting snippets.

2. **Start with `destruction_lab.html`** as one big file. If it's too large (2000+ lines), ask Claude to split into tiers:
   - `destruction_lab_tier1.html` — Phase 1 & 2 (skeleton + brain)
   - `destruction_lab_tier2.html` — Phase 3 & 4 (guardrails + features)
   - `destruction_lab_tier3.html` — Phase 5 & 6 (ML + deployment)

3. **After generating**, actually DO the exercises. The HTML is just the map — the learning happens when you delete files and watch things burn.

4. **Regenerate periodically** as your project evolves. New files, new dependencies, new destruction paths.

5. **Use the interview questions** as flashcards. If you can answer every question in the lab, you can talk about this project confidently in any interview.
