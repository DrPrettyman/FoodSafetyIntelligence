# EU Food Safety Regulatory Intelligence Engine

## Before starting any work, read ALL planning documents:

1. `planning/comprehensivePlan.md` — Full project plan: business problem, architecture, data sources, evaluation framework, timeline
2. `planning/general/portfolio-advice-article.md` — What hiring managers care about in data science portfolios
3. `planning/general/portfolio-principles-reference.md` — 7 research-backed principles for portfolio design (2024-2026)

Read these thoroughly before writing any code. They define what this project is, why it exists, and what "done" looks like.

## Working Rules

### 1. Keep a project log in `notes.md`

Maintain `notes.md` as a running record of the project. Read it at the start of every session. Update it as you work. Record:

- Data exploration findings (what the data looks like, edge cases, quirks)
- Design decisions and their rationale (why X approach over Y)
- Problems encountered and how they were solved
- Ideas considered but not pursued, and why
- Anything that would help someone (or future you) understand the project's evolution

Keep entries concise and factual. Use dated sections.

### 2. No throwaway code — everything goes in scripts

Do not execute ad-hoc code to explore data, test ideas, or prototype. Everything must be written in versioned, reproducible scripts or modules under `src/` or `scripts/`. Simple one-line bash commands (checking file sizes, listing directories, counting lines) are fine, but anything beyond a couple of lines belongs in a script.

Why: reproducibility is a core portfolio principle. If an analysis can't be re-run from the scripts alone, it doesn't exist.

### 3. Write tests as you go

Every new module under `src/` should have corresponding tests in `tests/`. Write them as you write the code, not after.

- Use pytest. Run with: `pytest` or `python -m pytest`
- Test data transformations, extraction logic, and edge cases
- Use small fixtures, not full datasets
- If a bug is found, write a failing test first, then fix it
