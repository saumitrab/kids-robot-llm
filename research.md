# Skills & Evals — Research, Design, and Plan

Research sweep 2026-11-07. Full sweep report (web sources, per-source notes):
`~/workspace/research_notes/skills-evals-architecture-sweep-20261107-1513/report.md`
First sweep (Anthropic only):
`~/workspace/research_notes/anthropic-skill-evals-guidance-20261107-1457/report.md`
Local papers already in this workspace: `~/workspace/AI-knowledge/items/`
(see §4 — they were supplied to the sweep, not re-fetched).

Status: **design not locked yet.** This file is the record to lock against.
Plugin evals (`claude plugin eval`) are NOT in scope yet — revisit when we
plug in. Mocking/simulation is a PLAN here, not built yet — build when
sensors arrive.

## 1. Central vs per-skill evals — the verdict

**No central-suite prescription exists anywhere found.** Searched Anthropic
(Demystifying Evals, Building Effective Agents, Equipping Agents with Agent
Skills, Claude Code plugin-evals + skill-creator docs, agentskills.io),
OpenAI (skill-evals post, Agents SDK), Google (ADK / Vertex AI), Meta
(Llama Stack), and the academic benchmarks (τ-bench, BFCL, ToolBench,
AgentBench, SWE-bench).

What exists instead:
- A consistent **per-skill convention**: `evals/evals.json` inside the skill
  directory (agentskills.io / skill-creator, 2–3 cases to start, run each
  with skill and without it); OpenAI: a per-skill prompt CSV (10–20
  prompts, should_trigger true/false); Claude Code: `evals/` inside the
  plugin, 3 runs per case, WITH / W/OUT / Δ — and its two eval formats are
  explicitly **not interchangeable**.
- A general-agent concept of a **central suite**: Anthropic defines a suite
  as "a collection of tasks designed to measure specific capabilities or
  behaviors"; Google ADK has a central `.evalset.json` per agent, grouped
  by capability. Neither says "put all skill evals in one central suite".

So the user's instinct was right to be surprised, and the sweep's answer
is: the prescription does not exist; the per-skill convention is the
closest thing to one, and it is not a central-suite rule.

**Design we will lock (hybrid):** per-skill eval files as the unit of
authorship + one central runner that discovers every skill's evals, runs a
central held-out suite, and reports one aggregate table. Per-skill-only
cannot see the failures the literature actually measures: routing
collapse, version divergence, and held-out non-generalisation are all
cross-skill failures.

## 2. Skill architecture — decisions to lock

### Progressive disclosure (Anthropic, agentskills.io spec)
- Level 1: name + description only, ~100 tokens per skill, pre-loaded.
- Level 2: full `SKILL.md` body, only when the skill triggers,
  <5,000 tokens / <500 lines.
- Level 3: `scripts/` / `references/` / `assets/` only when referenced;
  script code never enters context, only its output.
- **Correction to our current build:** PR #5 loads *every* skill body into
  the system prompt up front. That contradicts progressive disclosure and
  will not scale. Restructure to: each skill is a folder with `SKILL.md`
  (frontmatter: `name`, `description` with trigger keywords, `metadata`),
  loader reads only name + description, body loads on trigger.

### Description is the router
- Description carries the entire burden of triggering. Imperative
  ("Use this skill when…"), user intent not implementation, pushy,
  ≤1,024 chars. "The description field is for the model, not for humans."
- For this robot the prompt is the *only* routing signal, in English
  **and** Marathi — descriptions and trigger evals must carry trigger
  phrases in both languages, plus near-miss negatives
  ("dance" vs "sing", "spiral" vs "circle").

### Description optimisation loop (agentskills.io, adopt verbatim)
~20 trigger queries (8–10 should-trigger + 8–10 should-not, near-misses
most valuable), 3 runs each, trigger rate >0.5 to pass, 60/40
train/validation split, ≤5 iterations, select best by validation score,
verify on 5–10 fresh queries. Split across English/Marathi, explicit/
implicit phrasing.

### Granularity and count — the sharpest risk, now quantified
- SkillsBench (Li et al. 2026): focused skills with ≤3 modules beat
  exhaustive ones (+18.6pp vs +5.9pp for 4+, comprehensive −2.9pp).
  Curated skills +16.6pp overall; self-generated skills gave no benefit.
- More Skills, Worse Agents? (Song et al. 2026): 52 skills −8pp,
  102 −14pp, 202 −21pp; no-skill runs 12% → 38.5%. **Shadowing**
  (a similar wrong skill masks the right one) is up to 68% of the
  degradation; context overhead is ~⅓ and indistinguishable from zero.
- Lost in Implicit Routing (Liu et al. 2026): recall 73.6% → 27.4%
  at 1,000 distractors; explicit preselection restores 73.9%.
- SkillRouter (Zheng et al. 2026): hiding the body costs 37–44pp
  routing accuracy; 91.7% of routing signal is in the body.
- Phase transition at ~50–100 skills; hierarchical routing recovers
  +37–40pp (Li 2026).
- **Decisions:** one skill = one trick, ≤3 modules, distinct trigger
  verbs, no near-duplicates; keep the library small; if it ever
  approaches ~20–30 skills, add an explicit preselection / hierarchical
  router in code before the LLM — do not rely on flat implicit routing.
  Add a `category` frontmatter field now as the hook for that router.

### Versioning and provenance
- The spec has **no version field** — only free-form `metadata`.
  Convention: `metadata.version` (SemVer) + `CHANGELOG.md` per skill.
- SkillLifeBench: stored / selected / loaded versions can diverge
  (joint success 65.2% vs 77.5% task success). Fix: log skill name +
  version + content hash in every eval transcript; previous version is
  the baseline when iterating.

### Composition
- No native dependency management, no formal compose operator.
  **Decision:** skills never depend on each other in prose. Composition
  lives in code (harness / routine calls skill A then B); composed
  routines are evaluated as their own central cases.

### Prose vs code
- Prose for judgement (when to use it, what "good" looks like, gotchas).
- Code for anything that must be byte-identical every run — Fibonacci
  step sequence, turn angles, maze loop. The LLM selects the trick and
  its parameters; deterministic code computes the sequence.
  (SkillCompiler: up to +32.33% by compiling deterministic steps.)

## 3. Eval-driven development

Anthropic, *Demystifying evals for AI agents* (2026-01-09),
https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents —
Steps 0–8, the source of the "20–50 simple tasks drawn from real
failures" starting point:
- Start early, from real failures; unambiguous tasks + a reference
  solution (0% pass usually means a broken task, not a incapable agent).
- Balanced should / should-not sets; isolated clean-environment trials.
- **Grade outcome, not path** — Anthropic warns exact tool-sequence
  checks are "too rigid… overly brittle". **But** Vo et al. (local,
  §4) found 92.6% of final-output passes hid a process deviation, and
  Google ADK defaults to exact trajectory matching, and Claude Code
  advises "one grader on the result, and one on the steps".
  **Resolution for this robot:** grade both, separately — (a) final
  robot state, (b) canonical tool-call sequence, (c) safety/invariant
  assertions. For a spiral or dance the sequence *is* the outcome, but
  define equivalence per skill in the skill (turn-left ×4 is not the
  same trick as turn-right ×4 in a spiral).
- **pass³ as headline** (all 3 trials succeed), pass@3 secondary, never
  a single run. τ-bench: GPT-4o 61% pass@1 retail, pass⁸ <25%.
- **Both arms, every skill eval:** with vs without skill (or vs previous
  version), report Δ in pass rate *and* tokens/time. A skill with Δ≈0
  is a deletion candidate.
- **Held-out discipline:** 60/40 split per skill; a central held-out
  set no skill author may edit to pass; a held-out case that causes a
  fix is demoted to train and replaced. Piao et al.: only 5/21
  training-improved skills kept all improvement held-out.
- **Audit the grader:** run the reference solution through it (must
  pass) and a deliberately wrong sequence (must fail). Oracle Failures:
  a grader defect moved measured success 94.3% → 65.5%.
- **How many cases to start:** 20–50 central cases (Anthropic);
  2–3 output cases + 20 trigger queries per skill (agentskills.io);
  10–20 prompts per skill (OpenAI).
- **Eval before skill:** write the eval (cases + reference solution)
  before the skill; a skill with no eval does not ship.

## 4. Papers

### Already in local store (~/workspace/AI-knowledge/items/)
- Do Self-Evolving Skills Generalize to Held-Out Tasks? — Piao et al.,
  arXiv:2609.39148, 2026-09-30. Only 5/21 kept all gain held-out.
- Continuous Process-Level Evaluation for Evolving Enterprise AI Agent
  Skills — Vo et al., arXiv:2610.01833, 2026-10-01. 92.6% of final
  passes hid a process deviation.
- EvoSkill v2 — Huang et al., arXiv:2610.25931, 2026-10-19. Stateful
  evolver; accept every epoch, don't cherry-pick on noisy scores.
- SkillCompiler — Yang et al., arXiv:2610.39508, 2026-10-29. Compile
  deterministic steps; up to +32.33%.
- SkillLifeBench — Zhang et al., arXiv:2610.35215, 2026-10-26.
  Stored/selected/loaded divergence; provenance fix.
- RSE-Bench — Yu et al., arXiv:2610.19910, 2026-10-14. Noise during
  learning retains only 25.5–42.1% of clean gain.
- When Agent Evaluation Becomes Unreliable (Oracle Failures) — Chen,
  arXiv:2610.16067, 2026-10-12. Grader defect: 94.3% → 65.5%.
- Poisoned Skills — Manjusha & Emani, arXiv:2610.37738, 2026-10-27.
  Jailbreak in a SKILL.md: attack success 0.5% → 45%. Skills are a
  trust boundary — audit any third-party skill.
- Agent Skills → AAIF brief, 2026-10-23
  (`~/workspace/agent-skills-aaif-brief-2026-10-23.md`): Anthropic
  donated Agent Skills to the Agentic AI Foundation (Linux Foundation);
  versioned releases planned; 969 malicious skills (JFrog 2026).

### New from this sweep (not in local store)
- τ-bench — Yao et al., arXiv:2406.12045, 2024. Introduced pass^k;
  grades final environment state in a simulated tool world.
- SkillsBench — Li et al., arXiv:2602.12670, 2026. First benchmark
  measuring whether skills help at all, with/without.
- SkillRouter — Zheng et al., arXiv:2603.22455, 2026. Progressive
  disclosure costs 37–44pp routing accuracy.
- More Skills, Worse Agents? — Song et al., arXiv:2605.24050, 2026.
  Shadowing, not context, degrades large skill libraries.
- Lost in Implicit Routing — Liu et al., arXiv:2610.18522, 2026.
  Implicit routing collapses at scale; explicit preselection restores it.
- ToolLLM / ToolBench — Qin et al., arXiv:2307.16789, 2023.
  Foundational large-scale tool-use eval (16,464 APIs).
- Also consulted: AgentBench (arXiv:2308.03688), SWE-bench
  (arXiv:2310.06770), BFCL (arXiv:2409.00608), Li 2026 hierarchical
  routing (arXiv:2601.04748).

## 5. Mocking / simulation — plan only, build when sensors arrive

Standard ladder (NI / MathWorks): MIL → SIL → PIL → HIL → physical.
MIL/SIL are the plan; HIL when a real controller board exists; physical
test is the last mile. Do NOT build Isaac Sim / Gazebo for this toy.

Staged plan:
1. **Now (no hardware):** define a `RobotBackend` interface
   (`move()`, `turn()`, `read_sensor()`, …). Only implementation is a
   deterministic **mock** — scripted sensor values, perfect actuation,
   fixed seed. Evals run against the mock. This is SIL in miniature.
   (Our `FakeLink` is already this pattern for commands.)
2. **When a world model is needed:** add a **grid sim** behind the same
   interface — obstacles, ray-cast distance sensor, wheel-slip /
   turn-error and latency parameters, fault injection (stuck sensor,
   dropped reading). ~200 lines at toy fidelity. Randomise per run
   (domain randomisation, Tobin et al., arXiv:1703.06907) — sensor
   noise, slip, latency, obstacle placement — and eval across the
   randomised distribution, not one fixed map.
3. **When the first real sensor arrives:** record real sensor traces;
   add **recorded replay** as a backend (fixtures checked in, replayed
   in CI); calibrate the sim's noise model against real traces.
   (Chronicle cut-point replay, arXiv:2609.20625; VCR-style cassettes.)
   Record every real-robot run from day one (prompt → tool calls →
   sensor readings → final state) as a fixture.
4. **When a real controller board arrives:** HIL — real board +
   simulated plant/sensors, real I/O timing; then physical test, with
   the sim evals re-run as the regression gate.
5. **Throughout:** mock tools / stub APIs, no real side effects in sim,
   fixed seed, resource caps (turns/time/tokens), full trace of every
   prompt / tool call / decision. Separate layers: orchestration is
   deterministic and replay-testable in CI with zero inference cost;
   model reasoning quality is an offline eval, not a CI gate.

Key pattern (ros2_control / Gazebo): the mock, the sim, and the real
driver are three implementations of the *same interface*, publishing
the same shapes — the agent never talks to hardware directly. That
seam is the only thing to lock in now.

## 6. Decisions to lock (checklist)

1. Hybrid eval layout: per-skill `evals/evals.json` + central runner /
   held-out suite / aggregate table.
2. Eval before skill; no eval = no ship.
3. Dual grading, separate scores: final state + canonical sequence +
   safety/invariants.
4. pass³ headline, pass@3 secondary, never a single run.
5. Both arms (with/without, or vs previous version); report Δ in pass
   rate and tokens/time; Δ≈0 = deletion candidate.
6. Trigger eval per skill (20 queries, 3 runs, >0.5, 60/40, ≤5 iters),
   split English/Marathi.
7. Description discipline: imperative, intent not implementation,
   ≤1,024 chars, trigger phrases in both languages.
8. Granularity + count: one skill = one trick, ≤3 modules, distinct
   trigger verbs; ~20–30 skills = add a code preselection/hierarchical
   router; add `category` frontmatter now as the hook.
9. Progressive-disclosure budgets enforced by lint: description
   ≤1,024 chars; SKILL.md <500 lines / <5,000 tokens; references one
   level deep; `scripts/` for deterministic steps.
10. Prose vs code: prose for judgement/gotchas; code for byte-identical
    steps. LLM selects trick + parameters; code computes the sequence.
11. No skill-to-skill dependencies; composition lives in code.
12. Version + provenance from day one: `metadata.version` + CHANGELOG;
    log name + version + hash per run; previous version is the baseline.
13. Held-out discipline: 60/40 per skill; central held-out set never
    edited to pass; a case that causes a fix is demoted to train.
14. Audit the grader: reference solution must pass, deliberately wrong
    sequence must fail.
15. Hardware seam now, sim later: `RobotBackend` interface + mock;
    staged plan §5. Skills are a trust boundary (audit third-party
    skills; Poisoned Skills).
16. Do NOT build on OpenAI hosted Evals — winding down, unavailable
    from 2026-11-30; migration is to Agents SDK / Promptfoo.

## Sources

- Anthropic, Equipping agents for the real world with Agent Skills,
  2025-10-16 — https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Agent Skills specification — https://agentskills.io/specification
- agentskills.io, Evaluating skill output quality —
  https://agentskills.io/skill-creation/evaluating-skills
- agentskills.io, Optimizing skill descriptions —
  https://agentskills.io/skill-creation/optimizing-descriptions
- agentskills.io, Best practices for skill creators —
  https://agentskills.io/skill-creation/best-practices
- Anthropic, Demystifying evals for AI agents, 2026-01-09 —
  https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Anthropic, Building effective agents, 2024 —
  https://www.anthropic.com/engineering/building-effective-agents
- Anthropic, Writing effective tools for agents, Sep 2025 —
  https://www.anthropic.com/engineering/writing-tools-for-agents
- Claude Code, Test plugins with evals —
  https://code.claude.com/docs/en/plugin-evals
- Claude Code, Extend Claude with skills —
  https://code.claude.com/docs/en/skills
- OpenAI, Testing Agent Skills Systematically with Evals —
  https://developers.openai.com/blog/eval-skills
- Google ADK evals — https://codelabs.developers.google.com/adk-eval/instructions
- Tobin et al., Domain Randomization, arXiv:1703.06907
- Chronicle, Cut-Point Replay, arXiv:2609.20625
- Scholak, Skills, Composition, and the Coordination Problem, 2025 —
  https://tscholak.github.io/posts/composable-skills.html
