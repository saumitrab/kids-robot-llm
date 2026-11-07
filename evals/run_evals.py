<<<<<<< /tmp/merge_run_evals.py/ours
"""Run the tool-call sequence evals in evals/cases.json.

Usage (from the repo root, Ollama running, model pulled):
    python3 evals/run_evals.py [--cases evals/cases.json] [--out evals/results.json]

Scores each case by EXACT sequence match: the captured tool calls must
match the expected list call for call, in order, with the same repeats
and the same final stop. Reply text is ignored for scoring, except that
a reply claiming work the tool calls did not do is a fail (caught by
the sequence mismatch itself — the calls are what count).

Writes a results file with the model, prompt version, generation
budget, and per-case input / expected / actual / pass.
=======
"""The central benchmark runner.

This is the benchmark, not just a test script: per-skill evals are the
unit tests for each skill (skills/<name>/evals/evals.json), and this
runner discovers them, runs them, and aggregates them with the central
held-out suite (evals/cases.json) into one table.

Usage (from the repo root, Ollama running, model pulled):
    python3 evals/run_evals.py [--model gemma4:e4b] [--runs 3]
                               [--skill maze-escape] [--out evals/results.json]

- Configurable: --model picks the brain (gemma4:e4b default, gemma4:e2b
  for a smaller/faster run, qwen3:4b, …). The same evals must run
  unchanged against any model — that is what makes the number comparable.
  A Muse Spark / other-model backend is a future --backend flag; the
  runner is written so the model call is one function (chat_once).
- pass³ headline: each case runs 3 times; a case passes only if ALL 3
  succeed (a kids' toy must do the same trick reliably every time).
  pass@3 (≥1 of 3) is reported as a secondary capability signal.
- Dual grading, separate scores: (a) exact tool-call sequence match,
  (b) final robot state (position + heading, simulated from the
  sequence — a spiral that ends in the right place via the wrong turns
  is a different trick). Both must pass.
- Both arms: each case runs with the skill loaded and without it
  (metadata only, body not loaded). Δ in pass rate and tokens/time is
  reported; a skill with Δ≈0 is a deletion candidate.
- Held-out: evals/cases.json is the central held-out suite — no skill
  author may edit it to pass a skill. A held-out case that causes a
  fix is demoted to the train set and replaced.
- load_skill calls are handled by the runner (body injected, not
  counted as a robot command) — progressive disclosure, level 2.
>>>>>>> /tmp/merge_run_evals.py/theirs
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
<<<<<<< /tmp/merge_run_evals.py/ours
=======
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code" / "step0"))
>>>>>>> /tmp/merge_run_evals.py/theirs

import ollama  # noqa: E402

import robo_talk  # noqa: E402

MAX_TOOL_CALLS_PER_TURN = 10

<<<<<<< /tmp/merge_run_evals.py/ours

def run_one(text):
    """Run one input through the model, capture the full tool-call list."""
    system = robo_talk.build_system_prompt()
=======
# Final-state simulation: start at (0, 0) facing North.
# move_forward/back step 1 unit along heading; turns rotate 90°.
HEADINGS = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # N, E, S, W


def final_state(calls):
    x = y = 0
    heading = 0  # 0=N, 1=E, 2=S, 3=W
    for name in calls:
        if name == "fibonacci_spiral":
            calls = robo_talk.expand_fibonacci()
            sub = final_state(calls)
            x, y, heading = sub[0], sub[1], sub[2]
            continue
        if name == "move_forward":
            dx, dy = HEADINGS[heading]
            x, y = x + dx, y + dy
        elif name == "move_back":
            dx, dy = HEADINGS[heading]
            x, y = x - dx, y - dy
        elif name == "turn_left":
            heading = (heading - 1) % 4
        elif name == "turn_right":
            heading = (heading + 1) % 4
    return (x, y, heading)


def chat_once(model, messages):
    """One model call. This is the only place the backend lives, so a
    future --backend (e.g. Muse Spark) swaps this function only."""
    return ollama.chat(
        model=model,
        messages=messages,
        tools=robo_talk.TOOLS,
        think=False,
        keep_alive="30m",
        options={"temperature": 0, "num_ctx": 4096, "num_predict": 512},
    )


def run_one(model, text, with_skill=True):
    """Run one input, capture the tool-call list (robot commands only).

    with_skill=False: the skill bodies are withheld — the model sees
    metadata only and load_skill returns nothing. That is the baseline
    arm: what the vanilla LLM does without the skill.
    """
    system = robo_talk.build_system_prompt()
    if not with_skill:
        system = robo_talk.SYSTEM_PROMPT
>>>>>>> /tmp/merge_run_evals.py/theirs
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]
    calls = []
    for _ in range(MAX_TOOL_CALLS_PER_TURN + 1):
<<<<<<< /tmp/merge_run_evals.py/ours
        resp = ollama.chat(
            model=robo_talk.MODEL,
            messages=messages,
            tools=robo_talk.TOOLS,
            think=False,
            keep_alive="30m",
            options={"temperature": 0, "num_ctx": 4096, "num_predict": 512},
        )
=======
        resp = chat_once(model, messages)
>>>>>>> /tmp/merge_run_evals.py/theirs
        msg = resp["message"]
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            break
        messages.append(msg)
        for tc in tool_calls:
<<<<<<< /tmp/merge_run_evals.py/ours
            calls.append(tc["function"]["name"])
            messages.append(
                {
                    "role": "tool",
                    "content": "done",
                    "tool_name": tc["function"]["name"],
                }
            )
    return calls
=======
            fn = tc["function"]
            name = fn["name"]
            if name == "load_skill":
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args)
                body = robo_talk.load_skill_body(args.get("name", "")) if with_skill else ""
                messages.append(
                    {
                        "role": "system",
                        "content": f"Skill {args.get('name', '')}:\n{body}"
                        if body
                        else "No skill loaded.",
                    }
                )
                continue
            if name == "fibonacci_spiral":
                calls.extend(robo_talk.expand_fibonacci())
            else:
                calls.append(name)
            messages.append({"role": "tool", "content": f"{name} done"})
    return calls


def grade(expected, actual):
    """Dual grading: exact sequence AND final robot state."""
    seq_ok = actual == expected
    state_ok = final_state(actual) == final_state(expected)
    return {"sequence": seq_ok, "final_state": state_ok, "pass": seq_ok and state_ok}


def discover_cases(root):
    """Per-skill evals + central held-out suite, tagged by source."""
    cases = []
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for evals_file in sorted(skills_dir.glob("*/evals/evals.json")):
            data = json.loads(evals_file.read_text())
            for c in data.get("cases", []):
                cases.append(
                    {
                        "id": c["id"],
                        "input": c["prompt"],
                        "expected": c["expected"],
                        "skill": data.get("skill", evals_file.parent.parent.name),
                        "source": "per-skill",
                    }
                )
    central = root / "evals" / "cases.json"
    if central.is_file():
        data = json.loads(central.read_text())
        for c in data.get("cases", []):
            cases.append(
                {
                    "id": c["id"],
                    "input": c["input"],
                    "expected": c["expected"],
                    "skill": c.get("skill", "core"),
                    "source": "central-benchmark",
                }
            )
    return cases
>>>>>>> /tmp/merge_run_evals.py/theirs


def main():
    parser = argparse.ArgumentParser()
<<<<<<< /tmp/merge_run_evals.py/ours
    parser.add_argument("--cases", default="evals/cases.json")
    parser.add_argument("--out", default="evals/results.json")
    args = parser.parse_args()

    data = json.loads(Path(args.cases).read_text())
    meta = data["meta"]
    cases = data["cases"]

    results = []
    passed = 0
    for case in cases:
        started = time.time()
        actual = run_one(case["input"])
        elapsed = round(time.time() - started, 1)
        ok = actual == case["expected"]
        passed += ok
        results.append(
            {
                "id": case["id"],
                "input": case["input"],
                "expected": case["expected"],
                "actual": actual,
                "pass": ok,
                "seconds": elapsed,
            }
        )
        mark = "PASS" if ok else "FAIL"
        print(f"{mark}  {case['id']}")
        if not ok:
            print(f"      expected: {case['expected']}")
            print(f"      actual:   {actual}")

    summary = {
        "model": meta["model"],
        "prompt_version": meta["prompt_version"],
        "generation": meta["generation"],
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "results": results,
    }
    Path(args.out).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n{passed}/{len(cases)} passed — results in {args.out}")
    return 0 if passed == len(cases) else 1
=======
    parser.add_argument("--model", default="gemma4:e4b")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--skill", default=None, help="run only one skill's cases")
    parser.add_argument("--cases", default=None)
    parser.add_argument("--out", default="evals/results.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    if args.cases:
        data = json.loads(Path(args.cases).read_text())
        cases = [
            {
                "id": c["id"],
                "input": c.get("input") or c.get("prompt"),
                "expected": c["expected"],
                "skill": c.get("skill", "core"),
                "source": "file",
            }
            for c in data.get("cases", [])
        ]
    else:
        cases = discover_cases(root)
    if args.skill:
        cases = [c for c in cases if c["skill"] == args.skill]

    results = []
    for case in cases:
        trials = []
        for _ in range(args.runs):
            started = time.time()
            actual = run_one(args.model, case["input"], with_skill=True)
            trials.append(
                {"actual": actual, "grade": grade(case["expected"], actual),
                 "seconds": round(time.time() - started, 1)}
            )
        # Baseline arm: same case, skill bodies withheld.
        baseline_actual = run_one(args.model, case["input"], with_skill=False)
        baseline = grade(case["expected"], baseline_actual)
        passes = sum(t["grade"]["pass"] for t in trials)
        # Log every trial to evals/runs.jsonl — the record the
        # RSE-Bench finding requires: tune from the log, not from chat.
        runs_log = root / "evals" / "runs.jsonl"
        with open(runs_log, "a", encoding="utf-8") as f:
            for t in trials:
                f.write(json.dumps({
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "model": args.model, "case": case["id"],
                    "skill": case["skill"], "input": case["input"],
                    "expected": case["expected"], "actual": t["actual"],
                    "grade": t["grade"], "seconds": t["seconds"],
                }, ensure_ascii=False) + "\n")
        results.append(
            {
                "id": case["id"],
                "skill": case["skill"],
                "source": case["source"],
                "input": case["input"],
                "expected": case["expected"],
                "trials": trials,
                "pass_all_runs": passes == args.runs,  # pass³
                "pass_any_run": passes > 0,  # pass@k
                "passes": passes,
                "baseline_without_skill": {"actual": baseline_actual, "grade": baseline},
                "delta_pass": (passes == args.runs) - baseline["pass"],
            }
        )
        mark = "PASS³" if passes == args.runs else f"FAIL {passes}/{args.runs}"
        print(f"{mark}  {case['id']}  (baseline: {'pass' if baseline['pass'] else 'fail'})")
        if passes != args.runs:
            print(f"      expected: {case['expected']}")
            for t in trials:
                print(f"      actual:   {t['actual']}  {t['grade']}")

    passed = sum(r["pass_all_runs"] for r in results)
    by_skill = {}
    for r in results:
        by_skill.setdefault(r["skill"], [0, 0])
        by_skill[r["skill"]][1] += 1
        by_skill[r["skill"]][0] += r["pass_all_runs"]

    summary = {
        "model": args.model,
        "runs_per_case": args.runs,
        "prompt_version": "pr6-anthropic-format",
        "generation": {"think": False, "keep_alive": "30m", "temperature": 0,
                       "num_ctx": 4096, "num_predict": 512},
        "total": len(results),
        "pass_all_runs": passed,
        "pass_any_run": sum(r["pass_any_run"] for r in results),
        "by_skill": {k: {"pass": v[0], "total": v[1]} for k, v in sorted(by_skill.items())},
        "results": results,
    }
    Path(args.out).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n{passed}/{len(results)} pass³ — per-skill: {summary['by_skill']}")
    print(f"results in {args.out}")
    return 0 if passed == len(results) else 1
>>>>>>> /tmp/merge_run_evals.py/theirs


if __name__ == "__main__":
    raise SystemExit(main())
