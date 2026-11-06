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
