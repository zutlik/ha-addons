# Memory Protocol

Rules for maintaining `MEMORY.md` efficiently across sessions.

---

## What Belongs in Memory

**Store:**
- Decisions and their one-line rationale
- Active task state (what's in progress, what's blocked)
- Project facts that would take >30 seconds to reconstruct (env details, credentials paths, key configs)
- Patterns observed (repeated actions, recurring problems)
- Open loops (unresolved questions, pending tasks)

**Do not store:**
- Information the user can find instantly elsewhere (docs, code comments)
- Step-by-step history of completed work (use git log for that)
- Anything that changes every session without meaning (timestamps, trivial status)
- Verbose explanations — store conclusions, not reasoning trails

---

## Writing Style

Memory entries must be:
- **Terse**: one line per fact when possible
- **Structured**: use the table and list formats in `MEMORY.md`
- **Dated**: prefix decisions with `[YYYY-MM-DD]`
- **Actionable**: "API key is in 1Password > project-x" beats "we talked about API key management"

---

## When to Update

Update `MEMORY.md`:
- After any decision is made
- After any task is completed (mark it done or remove it)
- After observing a new recurring pattern
- Before ending a session that produced meaningful state

Do **not** update `MEMORY.md` mid-task unless a critical fact emerges that must not be lost.

---

## Compaction Rules

Compact `MEMORY.md` when:
- The file exceeds ~150 lines, OR
- More than 30 days have passed since last compaction, OR
- The "Decisions Log" section has more than 20 entries

**Compaction process:**
1. Archive the full current `MEMORY.md` to `memory-archive/YYYY-MM.md`
2. Re-write `MEMORY.md` keeping only:
   - Current active context (verbatim if recent)
   - Project state table (verbatim)
   - Last 5 decisions (summarize older ones into 1 line each)
   - Open loops (all of them — don't drop these)
   - Patterns observed (compress into a bullet list)
3. Add a compaction entry at the bottom
4. Note in `IMPROVEMENTS_BACKLOG.md` if any patterns from the archive should become skills

---

## Memory vs. Skills

If a "Recurring Pattern" has appeared 2+ times, it belongs in a skill, not just in memory.

When promoting a pattern to a skill:
1. Create the skill per `SELF_IMPROVEMENT_PROTOCOL.md`
2. Remove the pattern from `MEMORY.md` (it's now captured better elsewhere)
3. Add a one-line reference: `"Pattern X → skill: skill-name"`

---

## Memory Failure Modes (and fixes)

| Failure | Symptom | Fix |
|---|---|---|
| Stale active context | Agent asks about something just done last session | Update "Active Context" at session end |
| Missing decisions | Same decision made twice | Add to Decisions Log immediately after deciding |
| Open loop rot | Backlog of never-resolved loops | Review at session start; close or escalate |
| Bloated file | >150 lines, slow to scan | Compact now |
| Over-detailed entries | Entries read like prose paragraphs | Rewrite as one-liners or tables |
