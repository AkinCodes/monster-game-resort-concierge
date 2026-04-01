# Interactive Learning Page — Prompt Template

Use this prompt (fill in the bracketed sections) to generate interactive HTML learning pages for any codebase concept. Copy the whole thing and paste it as your prompt.

---

## THE PROMPT

```
I need you to create a single-file interactive HTML learning page that teaches how
[CONCEPT / FILE / SYSTEM] works in my codebase.

The page should NOT be a static document. It should be a living, interactive teaching
tool where I can click, explore, toggle, and watch things connect — so I can finally
see how the pieces fit together in ways that just reading code never shows me.

=== WHAT TO TEACH ===

Subject: [e.g., "how app/concierge/tools.py wires tools to the LLM"]
Source files: [e.g., "app/concierge/tools.py (186 lines)"]
Key concepts: [e.g., "frozen dataclass, decorator registry, dependency injection,
  OpenAI tool schemas, async execution with timing"]

=== PAGE STRUCTURE ===

Build the page as a TABBED interface. Each tab reveals a different lens on the same
code — so I can approach it from multiple angles:

Tab ideas (pick 3-6 that fit your concept):
- **Visual Blueprint** — An interactive node graph showing how objects/functions
  connect. Click a node to highlight its upstream dependencies and downstream
  consumers. Use SVG paths with animated dots flowing along connection lines.
  Color-code flows by type (data, config, knowledge, etc.).
- **Step-by-Step Theater** — Choose a scenario (e.g., "Book a Room", "Handle an
  Error") and watch the execution unfold step by step. Each step shows: which
  function runs, what data flows in/out, timing, and what could go wrong.
- **Method/Function Cards** — One card per function/class. Each card has:
  the code explanation, a Sesame Street analogy, parameter details, and return
  values. Laid out in a responsive grid.
- **Deep Dive Simulator** — An interactive playground where I can manipulate
  inputs and watch the system respond. Sliders, toggles, buttons that add/remove
  elements, with real-time visual feedback.
- **Experiment Cards** — Hands-on "break it to learn it" exercises. Each has
  numbered steps, code to modify, "What to Observe" callout boxes, and
  collapsible findings sections.
- **Instruction Manual** — The schemas, configs, or contracts the system uses,
  presented as expandable accordion sections with both the technical JSON/code
  AND a plain-English explanation.
- **Scoreboard / Metrics** — Visual bar charts or counters showing runtime
  behavior (call counts, timing, error rates).

=== DESIGN SYSTEM ===

Dark mode only. Use this exact aesthetic:

Colors:
- Background: very dark (#0a-#12 range), never pure black
- Text: warm light (#e2-#e8 range), never pure white
- Accent palette: 3-5 vivid colors for different categories/flows
  (e.g., gold #d4a843, crimson #c0392b, teal #2a9a7a, violet #7a3abf)
- Glows: use rgba() versions of accents for box-shadows and hover states
- Cards: slightly lighter than background (#1a-#22 range) with subtle borders

Typography:
- Titles: a decorative serif (Cinzel or similar from Google Fonts)
- UI labels: a friendly rounded sans-serif (Fredoka or similar)
- Code: JetBrains Mono (monospace)
- Body: Inter (clean sans-serif)
- All from Google Fonts CDN

Effects:
- Smooth transitions: cubic-bezier(.4,0,.2,1) for all state changes
- Subtle ambient animations: flickering glows, pulsing borders, floating dots
- Expandable sections: max-height transitions with chevron rotation
- Interactive highlights: clicked elements glow, connected elements highlight,
  unrelated elements dim (opacity 0.25)
- NO harsh transitions. Everything should feel fluid and alive.

Layout:
- Responsive grid that collapses gracefully on mobile
- Cards with slight border-radius (8-12px) and layered box-shadows
- Tab bar with clear active states (color + border change)
- Generous spacing — the page should breathe, never feel cramped

=== INTERACTIVE ELEMENTS TO INCLUDE ===

Must have at least 3 of these:

1. **Clickable node graph** — SVG-based. Nodes represent functions/objects.
   Clicking a node highlights its connections (upstream=one color,
   downstream=another). Unconnected nodes dim. Animated dots flow along paths.

2. **Scenario buttons** — "Book a Room", "Handle Error", "Search Amenities" etc.
   Clicking one plays a step-by-step animation showing the execution flow.
   Each step highlights with a pulse, shows the data, and auto-advances
   (or click to advance).

3. **Expandable accordion cards** — Click header to expand body. Smooth
   max-height transition. Chevron rotates. Can have nested accordions inside.

4. **Interactive simulator** — Buttons that add/remove visual elements
   (e.g., "Add Message" drops a colored grain into a container). Sliders
   that adjust parameters. Real-time counters that update.

5. **Toggle switches** — Switch between two modes (e.g., "LLM vs Regex",
   "Before vs After") and watch the visualization change.

6. **Inspect-on-click panels** — Click any visual element to see its details
   in a slide-in side panel. Panel shows: name, description, code snippet,
   connections.

7. **Copy buttons** — On code blocks. Click to copy, show a brief toast
   notification "Copied!"

8. **Filter buttons** — Filter cards/experiments by category. Active filter
   gets colored, inactive stays muted.

=== SESAME STREET ANALOGIES ===

CRITICAL: Every major concept gets a "Sesame Street Explains This" section.

Rules:
- Use ONE continuous analogy across ALL sections (not a different metaphor for
  each card). The analogy should tell a progressive story — each section is
  a new chapter in the same scenario.
- Pick a setting: [e.g., "Big Bird runs a restaurant", "Elmo's toy factory",
  "Grover's delivery service"]
- Map each technical concept to something in that setting
- Use character dialogue format:
  <span class="character">Big Bird:</span> "dialogue here"
- Include a "One-line version" summary at the end of each section
- The analogy sections should be collapsible (click to expand)
- Style them with a warm accent color (gold/orange) border

=== CODE PRESENTATION ===

When showing code:
- Dark code blocks (#0d-#14 background) with syntax highlighting
- Use span classes for coloring: .keyword (purple), .string (green/orange),
  .comment (dim gray), .function (gold), .highlight (bright accent for the
  key line being discussed)
- Include line references to actual files: "tools.py:32"
- If showing before/after, use clear labels and different accent colors

=== TEACHING METHODOLOGY ===

Each concept should be approachable from 3 levels:
1. **Visual** — See it animated/interactive on screen
2. **Analogy** — Understand it through the Sesame Street story
3. **Technical** — Read the actual code with annotations

Include these callout box types:
- **"What to observe"** — Yellow-tinted box with bullet points about what to
  watch for during an experiment
- **"Key insight"** — Highlighted takeaway box
- **"Common mistake"** — Red-tinted warning box
- **"One-line version"** — Ultra-distilled summary

=== TECHNICAL REQUIREMENTS ===

- Single HTML file, no build tools, no external JS frameworks
- CSS in a <style> block, JS in a <script> block at the bottom
- Google Fonts loaded via CDN link tags
- All interactive state managed with vanilla JS (classList.toggle, etc.)
- SVG for any diagrams/paths (inline, not external files)
- Responsive: works on 1440px desktop down to 375px mobile
- Tab panels use display:none/block switching
- Smooth scroll behavior for any anchor navigation
- No console errors, no external dependencies beyond fonts

=== HEADER ===

The page header should:
- Have a dramatic gradient background with subtle animated effects
- Display the title in large decorative serif font
- Include a subtitle explaining what file/system this covers
- Show metadata badges (e.g., "3 Functions", "186 Lines", "1 File")
- Feel like the entrance to something — atmospheric, not corporate

=== WHAT SUCCESS LOOKS LIKE ===

When I open this page, I should be able to:
1. See the big picture immediately (visual graph/diagram in the first tab)
2. Click any node/card and understand what it does within 10 seconds
3. Watch a scenario play out step-by-step and say "OH, that's how it flows"
4. Read the Sesame Street version and be able to explain the concept to
   a non-programmer
5. Find the actual code reference for anything I see on the page
6. Never feel lost — every interactive element has clear affordances
   (hover states, cursor:pointer, labels)

The goal is to make the invisible visible. The connections between functions,
the flow of data, the timing of execution — all the things that are hidden
when you just read code line by line.
```

---

## HOW TO USE THIS PROMPT

1. **Fill in the bracketed sections** at the top (`[CONCEPT]`, `[SOURCE FILES]`, `[KEY CONCEPTS]`)
2. **Choose your tabs** — pick 3-6 from the list that fit your concept
3. **Pick your analogy setting** — one metaphor world that maps to your whole system
4. **Paste the whole prompt** into Claude (or any LLM)
5. **Follow up** with: "Here is the source code:" and paste the actual file(s)

### Example fills:

**For a database module:**
```
Subject: "how app/records_room/database.py manages bookings"
Source files: "app/records_room/database.py (145 lines)"
Key concepts: "SQLite connection, CRUD operations, session management,
  booking validation, error recovery"
Analogy: "Big Bird's filing cabinet at the Monster Resort front desk"
```

**For an auth middleware:**
```
Subject: "how app/security/auth.py validates API requests"
Source files: "app/security/auth.py (89 lines)"
Key concepts: "API key validation, rate limiting, request logging,
  error responses, middleware chain"
Analogy: "Big Bird's bouncer at the Monster Resort entrance"
```

**For a RAG pipeline:**
```
Subject: "how app/records_room/rag.py retrieves and ranks knowledge"
Source files: "app/records_room/rag.py (210 lines)"
Key concepts: "vector embeddings, BM25 keyword search, hybrid scoring,
  cross-encoder reranking, context assembly"
Analogy: "Big Bird's library system at the Monster Resort"
```

---

## TIPS FOR BEST RESULTS

- **Always provide the actual source code** after the prompt — the LLM needs to
  read the real implementation to make accurate visualizations
- **One file per page works best** — if a concept spans multiple files, focus on
  the main orchestrator and reference the others
- **The analogy is the glue** — spend a moment picking one that naturally maps
  to your concept. Restaurant for data flow, library for search, factory for
  object creation, etc.
- **Start with the Blueprint tab** — seeing the node graph first gives context
  for everything else
- **If the page is too long**, split into 2 pages with cross-links rather than
  cramming everything into one
- **Test interactivity** — open the file in a browser and click everything.
  If something doesn't respond, ask for a fix specifically
