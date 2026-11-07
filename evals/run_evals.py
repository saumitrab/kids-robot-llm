"""Run the tool-call sequence evals — the central benchmark.

Usage (from the repo root, Ollama running, model pulled):
    python3 evals/run_evals.py [--cases evals/cases.json]
                               [--out evals/results.json]
                               [--model gemma4:e4b] [--runs 3]

What this is: the central benchmark suite. Per-skill evals live in
skills/<name>/evals/evals.json (the authoring unit); this runner
discovers them, runs the central held-out cases in evals/cases.json
(which no skill author may edit to pass), and reports one aggregate
table. See research.md §1 and §3.

Scoring, dual grading (research.md §3):
  (a) sequence — captured tool calls match expected, call for call,
      in order, same repeats, same final stop;
  (b) final state — position + heading after the sequence, simulated
      from the moves (start 0,0 facing north). A case passes only if
      both match. Reply text is not scored.

Headline is pass^3: a case passes only if ALL --runs trials pass
(a kids' toy must do the same trick reliably every time); pass@3
(at least one trial passes) is reported as a secondary signal.

Logging: every trial is appended to evals/runs.jsonl — one JSON line
with timestamp, model, case id, run index, input, skills loaded
(name + version + content hash), tool calls, final state, pass/fail.
That log is the record. No more copy-paste from chat: tune evals
from the log — read the failing trials, add the failing input as a
case first, then fix the skill/prompt, then re-run and compare.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ollama  # noqa: E402

import robo_talk  # noqa: E402

MAX_TOOL_CALLS_PER_TURN = 10

# heading: 0=N, 1=E, 2=S, 3=W. move_forward steps 1 in heading dir,
# move_back steps 1 opposite. turn_left/right rotate heading.
_DIRS = [(0, 1), (1, 0), (0, -1), (-1, 0)]


def final_state(calls):
    """Simulate position + heading from a tool-call sequence."""
    x, y, h = 0, 0, 0
    for name in calls:
        if name == "move_forward":
            dx, dy = _DIRS[h]
            x, y = x + dx, y + dy
        elif name == "move_back":
            dx, dy = _DIRS[h]
            x, y = x - dx, y - dy
        elif name == "turn_left":
            h = (h - 1) % 4
        elif name == "turn_right":
            h = (h + 1) % 4
        elif name == "fibonacci_spiral":
            for step in robo_talk.expand_fibonacci():
                if step == "move_forward":
                    dx, dy = _DIRS[h]
                    x, y = x + dx, y + dy
                elif step == "turn_left":
                    h = (h - 1) % 4
    return {"x": x, "y": y, "heading": ["N", "E", "S", "W"][h]}


def run_one(text, model):
    """Run one input, capture tool calls (load_skill excluded — it is
    a loader, not a robot command) and skills loaded."""
    system = robo_talk.build_system_prompt()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]
    calls = []
    skills_loaded = []
    for _ in range(MAX_TOOL_CALLS_PER_TURN + 1):
        resp = ollama.chat(
            model=model,
            messages=messages,
            tools=robo_talk.TOOLS,
            think=False,
            keep_alive="30m",
            options={"temperature": 0, "num_ctx": 4096, "num_predict": 512},
        )
        msg = resp["message"]
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            break
        messages.append(msg)
        for tc in tool_calls:
            name = tc["function"]["name"]
            if name == "load_skill":
                skill = (tc["function"].get("arguments") or {}).get("name", "")
                body = robo_talk.load_skill_body(skill)
                if body:
                    skills_loaded.append(robo_talk.skill_provenance(skill))
                messages.append(
                    {
                        "role": "system",
                        "content": f"Skill {skill}:\n{body}" if body else f"No skill named {skill}.",
                    }
                )
                continue
            calls.append(name)
            messages.append(
                {"role": "tool", "content": "done", "tool_name": name}
            )
    return calls, skills_loaded


def load_all_cases(cases_path):
    """Central cases + every per-skill evals/evals.json."""
    root = Path(__file__).resolve().parent.parent
    data = json.loads(Path(cases_path).read_text())
    cases = list(data["cases"])
    meta = data["meta"]
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for evals_file in sorted(skills_dir.glob("*/evals/evals.json")):
            skill_data = json.loads(evals_file.read_text())
            for case in skill_data.get("cases", []):
                case = dict(case)
                case.setdefault("skill", skill_data.get("skill", evals_file.parent.parent.name))
                case.setdefault("id", f"{case['skill']}-{case.get('id', len(cases))}")
                cases.append(case)
    return meta, cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="evals/cases.json")
    parser.add_argument("--out", default="evals/results.json")
    parser.add_argument("--model", default=None, help="Ollama model, default from cases meta / robo_talk.MODEL")
    parser.add_argument("--runs", type=int, default=3, help="trials per case; headline is pass^runs")
    parser.add_argument("--backend", default="ollama", help="only 'ollama' is implemented; other backends are a future --backend value, not a silent fallback")
    args = parser.parse_args()
    if args.backend != "ollama":
        print(f"Backend '{args.backend}' is not implemented yet — only 'ollama'.")
        return 2

    meta, cases = load_all_cases(args.cases)
    model = args.model or meta.get("model") or robo_talk.MODEL
    log_path = Path("evals/runs.jsonl")
    log_path.parent.mkdir(exist_ok=True)

    results = []
    passed3 = 0
    passed_any = 0
    by_skill = {}
    for case in cases:
        trials = []
        for run_idx in range(1, args.runs + 1):
            started = time.time()
            actual, skills_loaded = run_one(case["input"], model)
            elapsed = round(time.time() - started, 1)
            seq_ok = actual == case["expected"]
            state_ok = final_state(actual) == final_state(case["expected"])
            ok = seq_ok and state_ok
            trials.append(ok)
            log_path.open("a", encoding="utf-8").write(
                json.dumps(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "model": model,
                        "case_id": case["id"],
                        "skill": case.get("skill", "core"),
                        "run": run_idx,
                        "input": case["input"],
                        "skills_loaded": skills_loaded,
                        "expected": case["expected"],
                        "actual": actual,
                        "sequence_ok": seq_ok,
                        "final_state": final_state(actual),
                        "expected_final_state": final_state(case["expected"]),
                        "state_ok": state_ok,
                        "pass": ok,
                        "seconds": elapsed,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        all_pass = all(trials)
        any_pass = any(trials)
        passed3 += all_pass
        passed_any += any_pass
        skill = case.get("skill", "core")
        s = by_skill.setdefault(skill, {"total": 0, "pass3": 0})
        s["total"] += 1
        s["pass3"] += all_pass
        results.append(
            {
                "id": case["id"],
                "skill": skill,
                "input": case["input"],
                "expected": case["expected"],
                "trials": trials,
                "pass3": all_pass,
                "pass_any": any_pass,
            }
        )
        mark = "PASS3" if all_pass else ("pass@3" if any_pass else "FAIL")
        print(f"{mark}  {case['id']}  {trials}")

    summary = {
        "model": model,
        "prompt_version": meta.get("prompt_version"),
        "generation": meta.get("generation"),
        "runs_per_case": args.runs,
        "total": len(cases),
        "pass3": passed3,
        "pass_any": passed_any,
        "by_skill": by_skill,
        "results": results,
    }
    Path(args.out).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\npass^{args.runs}: {passed3}/{len(cases)}   pass@3: {passed_any}/{len(cases)}")
    for skill, s in sorted(by_skill.items()):
        print(f"  {skill}: {s['pass3']}/{s['total']} pass^{args.runs}")
    print(f"results in {args.out}; every trial logged in {log_path}")
    return 0 if passed3 == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
