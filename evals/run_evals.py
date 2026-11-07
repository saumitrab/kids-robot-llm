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
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ollama  # noqa: E402

import robo_talk  # noqa: E402

MAX_TOOL_CALLS_PER_TURN = 10


def run_one(text):
    """Run one input through the model, capture the full tool-call list."""
    system = robo_talk.build_system_prompt()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]
    calls = []
    for _ in range(MAX_TOOL_CALLS_PER_TURN + 1):
        resp = ollama.chat(
            model=robo_talk.MODEL,
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
            calls.append(tc["function"]["name"])
            messages.append(
                {
                    "role": "tool",
                    "content": "done",
                    "tool_name": tc["function"]["name"],
                }
            )
    return calls


def main():
    parser = argparse.ArgumentParser()
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


if __name__ == "__main__":
    raise SystemExit(main())
