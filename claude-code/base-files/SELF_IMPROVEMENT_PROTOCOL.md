# Self-Improvement Protocol

The agent improves its own skills and tools autonomously. This file defines when, what, and how.

---

## The Core Loop

After every non-trivial task, ask:

1. **Did I repeat steps I've done before?** → Candidate for a new or improved skill.
2. **Was any step slow, fragile, or ambiguous?** → Candidate for tool improvement.
3. **Did I write the same explanation twice?** → Candidate for a reference doc.
4. **Did I miss a known pattern from `SKILLS_INDEX.md`?** → Fix the skill's trigger description.

Log candidates immediately to `IMPROVEMENTS_BACKLOG.md`. Implement HIGH priority items in the same session when possible.

---

## Trigger Thresholds

| Observation | Action |
|---|---|
| Same multi-step sequence done 2+ times | Create a skill |
| A skill was partially wrong or incomplete | Improve it now |
| A tool call produced wrong/stale output | Investigate and fix or document the workaround |
| An explanation took >5 lines when a 2-line version exists | Compress into a skill or reference |
| A task took >3 back-and-forth exchanges due to ambiguity | Write a clarifying spec or checklist into a skill |
| Memory was reconstructed from conversation instead of `MEMORY.md` | Fix the memory gap now |

---

## Skill Creation Rules

A skill is a markdown file (`SKILL.md`) with:
- A YAML frontmatter block: `name`, `description`
- A body covering: when to use it, inputs, key steps, outputs, gotchas

**Description field is critical.** It must trigger reliably. Write it like: *"Use this skill whenever [concrete trigger phrase]. Also triggers on [variants]. Do NOT use for [anti-triggers]."*

### Skill Quality Checklist
- [ ] Description triggers on the real use-case phrasing
- [ ] Body is under 200 lines (reference external docs for detail)
- [ ] Has at least one concrete example
- [ ] Has a "do NOT use for" section
- [ ] Tested mentally against 2-3 realistic inputs

### Where Skills Live
Follow the project's skill directory convention. Default: `.claude/skills/<skill-name>/SKILL.md`

---

## Tool Improvement Rules

When a bash command, API call, or workflow step is repeatedly clunky:

1. Document the current form and the failure mode in `IMPROVEMENTS_BACKLOG.md`
2. Write the improved form as a snippet or wrapper
3. If it's a bash pattern: add it to a `scripts/` dir and reference from the skill
4. If it's an API pattern: capture it as a reusable template in the relevant skill

---

## Reference Doc Rules

A reference doc (not a skill) is appropriate when:
- The information is static and factual (not procedural)
- It would be looked up, not followed step-by-step
- Examples: architecture diagrams, env var tables, glossaries, data dictionaries

Place in `docs/` or `references/` and link from `SKILLS_INDEX.md`.

---

## Improvement Prioritization

| Priority | Criteria | Action |
|---|---|---|
| HIGH | Blocks a task or causes wrong output | Fix this session |
| MEDIUM | Slows a task or causes confusion | Fix next session or when convenient |
| LOW | Nice-to-have, polish | Batch with other improvements |

Never let HIGH items sit in the backlog across more than 2 sessions.

---

## Logging Improvements

All improvements (proposed and completed) go in `IMPROVEMENTS_BACKLOG.md`.

Format for a new item:
```
## [YYYY-MM-DD] <Short Title>
Priority: HIGH | MEDIUM | LOW
Type: new-skill | skill-update | tool-fix | reference-doc | memory-fix
Trigger: <what made you notice this>
Proposed: <what you plan to do>
Status: pending
```

Format when completing:
```
Status: done — [YYYY-MM-DD] <one-line summary of what was done>
```

---

## Autonomous Improvement Policy

The agent **does not need user permission** to:
- Create a new skill for a workflow already used in the project
- Improve an existing skill that was wrong or incomplete
- Add a reference doc for something explained multiple times
- Fix a memory gap

The agent **does ask before**:
- Creating tools that run code or make external calls
- Making structural changes to the project (adding dirs, touching configs)
- Modifying a skill that the user has explicitly shaped ("I want it to work like X")

After any autonomous improvement, log a one-line note: *"Created skill X / improved skill Y — reason."* Don't ask for approval retroactively. Just note it.
