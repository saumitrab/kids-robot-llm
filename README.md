# RoboTalk — Step 0: talk to the robot (laptop only, no parts needed)

Step 0 proves the voice pipeline on your laptop before any hardware exists.
You talk, the laptop understands (English or Marathi), Gemma decides what
the robot *would* do, and the command is printed instead of sent.

## Setup (macOS; Linux is the same minus `say`)

```bash
# 1. Ollama — download from https://ollama.com, or:
brew install --cask ollama

# 2. Pull the model (~2.5 GB download, one time)
ollama pull gemma3:4b

# 3. Python packages (use a venv if you like)
cd ~/kids-robot-llm/code/step0   # wherever you put this folder
pip install -r requirements.txt

# 4. Run
python3 robo_talk.py
```

First run: macOS will ask for **microphone permission** for your terminal —
allow it, or no audio is captured. Whisper downloads its model on first use.

## How to play

- Press **Enter**, speak, press **Enter** again to stop. Type `quit` to stop.
- Try: "go forward" · "turn left" · "dance" · "sing a song" · "tell me a story"
- Marathi: "पुढे जा" (go forward) · "डावीकडे वळ" (turn left) · "नाच" (dance)
- **Text test (no mic needed):** `python3 robo_talk.py --text` — type instead of speaking, same Gemma brain, same `[ROBOT WOULD DO]` commands. Good for a quick check that voice/text converts to commands.
- You will see lines like:
  - `You said (mr): पुढे जा`
  - `[ROBOT WOULD DO] move_forward`
  - `Robot says: ...` (and the laptop speaks it, English only for now)

## What each piece does

| Piece | Job | Why this one |
|---|---|---|
| faster-whisper `small` | Speech → text, English + Marathi | Local, free, auto-detects language |
| Ollama + Gemma 4 E4B | Understands + picks the robot command via native tool calls | Knows Marathi (140+ languages); ~3GB download, 4–6GB RAM; tools + vision + thinking. Gemma 3 does NOT support Ollama tools — do not use gemma3:4b. |
| macOS `say` | Spoken reply (English) | Built in, zero setup |
| `FakeLink` | Prints the command | Step 0 has no robot; step 1 swaps in `SerialLink` |

## Marathi voice-out (step 0b, not in this file yet)

`say` cannot do Marathi — Marathi replies are printed, not spoken, for now.
The upgrade is **Sarvam Bulbul v3 TTS** (`mr-IN` voice), the same voice
validated for the Marathi teacher project. It needs a free Sarvam API key;
when that exists, `speak()` gains a Sarvam branch and Marathi replies come
out of the speaker.

## Troubleshooting

- **"Ollama model not ready"** — run `ollama pull gemma3:4b`, and make sure
  the Ollama app is running (menu-bar icon).
- **No audio / empty transcript** — check mic permission (System Settings →
  Privacy & Security → Microphone → your terminal app) and that the right
  input is selected in System Settings → Sound → Input.
- **Slow first reply** — first run loads two models; after that it is a
  second or two per turn.
- **Gemma picks the wrong command** — that is the skill to tune in step 0:
  the system prompt in `robo_talk.py` is the place to fix it, not the model.

## What's next

- **Step 1 (radio link):** set `ROBOT_SERIAL_PORT=/dev/tty.usbserial-XXXX`
  and the same commands go over USB serial to the ESP32 bridge, which
  replays them to the robot over 2.4 GHz. The ESP32 sketch lands with step 1.
- **Step 2 (Jev):** the fast decision layer, learned in the OpenJev Doom app.
- **Step 3 (Pi):** same program on the Pi; the nRF24 plugs straight into
  the Pi's GPIO, no ESP32 needed, plus a USB mic and speaker.

## Sequences and Fibonacci

One turn can run up to 10 tool calls, so counts and chains work: `turn left two times` calls turn_left twice, `go forward and left` calls move_forward then turn_left.

`draw a Fibonacci spiral` (or just `Fibonacci`) calls the `fibonacci_spiral` tool once. It runs 1 forward, left, 2 forward, left, 3 forward, left, 5 forward, left, 8 forward, then stops — 19 forwards and 4 turns, 23 moves total. The stop after 8 is the stopping condition, and the 10-call cap stops any runaway count.

Speed: the model runs with thinking off, 30-minute keep-alive (no 9.6GB reload every 5 minutes), 4096 context, temperature 0.

## Evals — central benchmark + per-skill evals

`evals/cases.json` is the **central benchmark**: 24 held-out cases — single
commands, repeats, multi-step sequences, maze escapes, Fibonacci, dance
routine, chat with no command — in English and Marathi. No skill author
may edit a held-out case to pass it. Each skill also has its own evals
in `skills/<name>/evals/evals.json` (output cases + 10 trigger queries:
should-trigger / should-not, near-misses, English + Marathi).

Run them (from the repo root, Ollama running, model pulled):

```bash
python3 evals/run_evals.py [--model gemma4:e4b] [--runs 3]
```

Scoring is dual grading: (a) exact tool-call sequence, (b) final robot
state (position + heading, simulated from the moves). A case passes
only if both match. Headline is **pass³** — all 3 trials pass — with
pass@3 as a secondary signal. Every trial is logged to
`evals/runs.jsonl` (timestamp, model, case, skills loaded with name +
version + content hash, tool calls, final state, pass/fail). Tune from
that log: read the failing trials, add the failing input as a case
first, then fix the skill/prompt, then re-run and compare. Never a
single run, never copy-paste from chat.

## Teaching the robot new things — skills (Anthropic format)

Each skill is a folder, `skills/<name>/SKILL.md`, with YAML frontmatter
(`name`, `description` with trigger keywords, `metadata.version`,
`metadata.category`). `robo_talk.py` loads **only name + description**
at startup (progressive disclosure, ~100 tokens per skill); the model
loads the full body on demand with the `load_skill` tool when a skill
applies. To teach something new, add a folder with a `SKILL.md` and an
`evals/evals.json` — no code change, and a skill with no eval does not
ship.

Current skills: `fibonacci-spiral` (the 1-2-3-5-8 spiral, stop after 8),
`maze-escape` (follow the child's listed moves in order, stop when they
say stop), `dance-routine` (dance, sing, dance).

## Run log

Every turn `robo_talk.py` runs appends one JSON line to
`runs/runs.jsonl`: timestamp, model, input, skills loaded (name +
version + content hash — provenance), tool calls in order, reply.
That log is the record the RSE-Bench finding requires: never tune a
skill from a memory or a chat paste — tune it from the log, after
checking the record itself is clean (input ↔ calls ↔ outcome all
agree).
