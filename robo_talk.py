#!/usr/bin/env python3
"""
RoboTalk — Step 0: laptop voice pipeline for the kids' robot.

What it does:
  1. You press Enter, talk, press Enter again (push-to-talk).
  2. Whisper (local) transcribes — English or Marathi, auto-detected.
  3. Gemma 4 (local, via Ollama) decides: a robot command (native
     tool call) and/or a short spoken reply, in the SAME language
     you used.
  4. Step 0 has no robot yet, so the command is PRINTED
     ("[ROBOT WOULD DO] move_forward") instead of sent.
     Step 1 swaps FakeLink for SerialLink — same commands, real radio.

Why Gemma 4, not Gemma 3:
  Gemma 3 does NOT support Ollama native tool calling — every
  gemma3 tag (4b/12b/27b) returns 400 "does not support tools".
  Gemma 4 (e4b) does support native tools, plus vision/thinking,
  140+ languages incl. Marathi, ~3GB download, 4-6GB RAM.

Setup (see README.md):
  - Install Ollama, then:  ollama pull gemma4:e4b
  - pip install -r requirements.txt
  - Run:  python3 robo_talk.py

Step 1 preview: set ROBOT_SERIAL_PORT=/dev/tty.usbserial-XXXX and the
program sends the same commands over USB serial to the ESP32 bridge
instead of printing them.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

try:
    import ollama
except ImportError:
    ollama = None

SAMPLE_RATE = 16000
MODEL = os.environ.get("ROBOT_MODEL", "gemma4:e4b")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")

SYSTEM_PROMPT = """You are the voice of a small toy robot talking with kids aged 3 and 6.
- Understand English and Marathi (and mixes of both). Always reply in the SAME language the child used.
- Keep replies to one short sentence, playful and kind. Never scary, never rude.
- You can make the robot do things by calling tools: move_forward, move_back, turn_left, turn_right, dance, sing, tell_story, fibonacci_spiral.
- SEQUENCES: if the child asks for more than one thing, return ALL steps as MULTIPLE tool calls in a SINGLE response — one call per step, in order, up to 10 calls. Do NOT do just the first step and reply. Do NOT give a spoken reply until all steps are done. Examples:
  - "turn left two times" -> turn_left, turn_left (both in one response)
  - "go forward five times then turn left" -> move_forward x5, then turn_left (all 6 in one response)
  - "turn left two times then go ahead two times then turn right and stop" -> turn_left, turn_left, move_forward, move_forward, turn_right (all 5 in one response, then reply)
  - "go forward and left" -> move_forward, turn_left
  - "dance and sing" -> dance, sing
  Counts are literal: "three times" means exactly 3 calls, "five times" means exactly 5.
- FIBONACCI: if the child says "Fibonacci", "draw Fibonacci", or "Fibonacci spiral", call fibonacci_spiral ONCE (it runs the whole 1-2-3-5-8 pattern by itself). Do not expand it yourself.
- If the child asks the robot to move or do something, call the matching tool(s) AND give a one-sentence reply.
- If the child just wants to chat, just reply — no tool call.
- If the child says "stop", call no tool and reply that you stopped.
- Never claim you can do things you cannot (no fetching things, no going outside).
- If you are unsure what the child wants, ask one short question instead of guessing a movement.
"""

# Safety caps: no turn runs more than this many tool calls, so a
# miscounted "go forward 100 times" cannot run away.
MAX_TOOL_CALLS_PER_TURN = 10
# Fibonacci spiral steps (stops after 8 — that IS the stopping condition).
FIBONACCI_STEPS = [1, 2, 3, 5, 8]

TOOLS = [
    {"type": "function", "function": {"name": "move_forward", "description": "Drive the robot forward a short distance.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "move_back", "description": "Drive the robot backward a short distance.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "turn_left", "description": "Turn the robot left.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "turn_right", "description": "Turn the robot right.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "dance", "description": "Make the robot do a little dance.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "sing", "description": "Make the robot sing a song.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "tell_story", "description": "Make the robot tell a short story.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "fibonacci_spiral", "description": "Draw a Fibonacci spiral and STOP: forward 1, turn left, forward 2, turn left, forward 3, turn left, forward 5, turn left, forward 8, then stop. Call this once for a Fibonacci request.", "parameters": {"type": "object", "properties": {}}}},
]

# What goes over the wire to the ESP32 bridge in step 1.
COMMAND_WIRE = {
    "move_forward": "FWD",
    "move_back": "BACK",
    "turn_left": "LEFT",
    "turn_right": "RIGHT",
    "dance": "DANCE",
    "sing": "SING",
    "tell_story": "STORY",
}


def load_skills():
    """Teach the robot new things without changing code.

    Each file in skills/*.md is one skill: a name, when to use it,
    and the exact steps (tool calls) it means. To teach the robot
    something new, add a file — no code change needed. The LLM picks
    the matching skill by name when the child asks for it.
    """
    here = Path(__file__).resolve().parent
    for cand in (here / "skills", here.parent / "skills", Path.cwd() / "skills"):
        if cand.is_dir():
            skills_dir = cand
            break
    else:
        return ""
    texts = []
    for path in sorted(skills_dir.glob("*.md")):
        texts.append(path.read_text().strip())
    return "\n\n".join(texts)


def build_system_prompt():
    """Base prompt + every skill file in skills/."""
    skills = load_skills()
    if not skills:
        return SYSTEM_PROMPT
    return (
        SYSTEM_PROMPT
        + "\n## Robot skills — things you have been taught\n"
        + "When the child asks for one of these skills by name, use it. "
        + "A skill's steps are the exact tool calls to make, in order.\n\n"
        + skills
    )
    """1, 2, 3, 5, 8 steps, left turn between each run, stop after 8."""
    seq = []
    for i, n in enumerate(FIBONACCI_STEPS):
        seq.extend(["move_forward"] * n)
        if i < len(FIBONACCI_STEPS) - 1:
            seq.append("turn_left")
    return seq


class FakeLink:
    """Step 0: no robot. Print the command instead of sending it."""

    def send(self, command: str) -> None:
        print(f"  [ROBOT WOULD DO] {command}  (no radio linked yet — step 1 wires this up)")

    def send_sequence(self, commands: list) -> None:
        for command in commands:
            self.send(command)


class SerialLink:
    """Step 1: send short commands over USB serial to the ESP32 bridge."""

    def __init__(self, port: str, baud: int = 115200):
        import serial

        self.ser = serial.Serial(port, baud, timeout=1)

    def send(self, command: str) -> None:
        wire = COMMAND_WIRE.get(command, command)
        self.ser.write((wire + "\n").encode())
        print(f"  [SENT TO ROBOT] {wire}")

    def send_sequence(self, commands: list) -> None:
        for command in commands:
            self.send(command)
            time.sleep(0.6)  # let each move finish before the next one


class PushToTalkRecorder:
    """Record from the mic between start() and stop()."""

    def __init__(self):
        self.chunks = []
        self.stream = None

    def _callback(self, indata, frames, time, status):
        self.chunks.append(indata.copy())

    def start(self):
        self.chunks = []
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=self._callback
        )
        self.stream.start()

    def stop(self):
        self.stream.stop()
        self.stream.close()
        if not self.chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self.chunks, axis=0).flatten()


def _is_mostly_ascii(text: str) -> bool:
    return sum(ord(c) < 128 for c in text) / max(len(text), 1) > 0.8


def speak(text: str) -> None:
    """Speak the reply. macOS `say` handles English; Marathi voice-out
    is the step-0b upgrade (Sarvam Bulbul TTS) — see README.md."""
    if not text:
        return
    print(f"  Robot says: {text}")
    if not _is_mostly_ascii(text):
        print("  (Marathi voice-out needs Sarvam TTS — reply printed above for now)")
        return
    try:
        subprocess.run(["say", text], check=False)
    except FileNotFoundError:
        pass  # not macOS — the printed reply is the fallback


def handle_turn(text: str, messages: list, link) -> list:
    """One user turn: Gemma (native tool calls) -> send + speak.

    Loops so one turn can run a SEQUENCE: the model may return
    several tool calls, or one per round. Capped at
    MAX_TOOL_CALLS_PER_TURN so a bad count cannot run away.
    Speed: think=False, keep_alive 30m (no 9.6GB reload every
    5 minutes), small context, short replies.
    """
    messages.append({"role": "user", "content": text})
    calls_done = 0
    reply = ""
    for _ in range(MAX_TOOL_CALLS_PER_TURN + 1):
        try:
            resp = ollama.chat(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                think=False,
                keep_alive="30m",
                options={"temperature": 0, "num_ctx": 4096, "num_predict": 512},
            )
        except Exception as exc:
            print(f"  Ollama error: {exc}")
            return messages
        msg = resp["message"]
        tool_calls = msg.get("tool_calls") or []
        # Only use spoken text from a round with NO tool calls.
        # A reply that comes with tool calls is premature — the
        # sequence is not done yet, so do not let it end the turn.
        if not tool_calls and msg.get("content"):
            reply = (msg.get("content") or "").strip()
        if not tool_calls:
            break
        # Keep the assistant turn (with its tool calls) in history,
        # so the next round can continue the sequence.
        messages.append(msg)
        for call in tool_calls:
            if calls_done >= MAX_TOOL_CALLS_PER_TURN:
                break
            name = call["function"]["name"]
            if name == "fibonacci_spiral":
                seq = expand_fibonacci()
                print(f"  [FIBONACCI] 1-2-3-5-8 spiral, {len(seq)} moves, stopping after 8")
                link.send_sequence(seq)
                calls_done += len(seq)
            elif name in COMMAND_WIRE:
                link.send(name)
                calls_done += 1
            else:
                print(f"  (unknown tool {name} — skipped)")
                continue
            messages.append({"role": "tool", "content": f"{name} done"})
        if calls_done >= MAX_TOOL_CALLS_PER_TURN:
            print(f"  (stopped after {MAX_TOOL_CALLS_PER_TURN} steps — safety cap)")
            break
    if not reply and calls_done:
        reply = "Okay!"
    if reply:
        messages.append({"role": "assistant", "content": reply})
        speak(reply)
    # Keep history short so the small model stays fast.
    return [messages[0]] + messages[-8:]


def main():
    text_mode = "--text" in sys.argv
    if sd is None or WhisperModel is None or ollama is None:
        print("Missing packages. Run:  pip install -r requirements.txt")
        sys.exit(1)

    link = FakeLink()
    serial_port = os.environ.get("ROBOT_SERIAL_PORT")
    if serial_port:
        try:
            link = SerialLink(serial_port)
            print(f"Radio link: {serial_port}")
        except Exception as exc:
            print(f"Could not open {serial_port} ({exc}) — running in print-only mode.")

    messages = [{"role": "system", "content": build_system_prompt()}]

    if text_mode:
        # Text test mode: type instead of speaking. Same Gemma brain,
        # same tool calls, no mic / Whisper needed. Run:
        #   python3 robo_talk.py --text
        print("Checking Ollama model... ")
        try:
            ollama.show(MODEL)
        except Exception as exc:
            print(f"Ollama model '{MODEL}' not ready: {exc}")
            print(f"Run:  ollama pull {MODEL}   (and make sure Ollama is running)")
            sys.exit(1)
        print("\nText mode! Type a command, e.g. 'go forward', 'dance', 'पुढे जा'. Type 'quit' to stop.\n")
        while True:
            try:
                text = input("  You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                break
            if not text:
                continue
            if text.lower() in ("quit", "exit", "stop"):
                print("Bye!")
                break
            messages = handle_turn(text, messages, link)
        return

    print("Loading Whisper (first run downloads the model)...")
    stt = WhisperModel(WHISPER_MODEL, device="auto", compute_type="int8")

    print(f"Checking Ollama model '{MODEL}'...")
    try:
        ollama.show(MODEL)
    except Exception as exc:
        print(f"Ollama model '{MODEL}' not ready: {exc}")
        print(f"Run:  ollama pull {MODEL}   (and make sure Ollama is running)")
        sys.exit(1)

    print("\nReady! Press Enter, speak, press Enter again to stop. Type 'quit' to stop.\n")
    while True:
        try:
            input("  [press Enter to talk] ")
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        rec = PushToTalkRecorder()
        rec.start()
        try:
            input("  Listening... press Enter to stop  ")
        except (EOFError, KeyboardInterrupt):
            rec.stop()
            print("\nBye!")
            break
        audio = rec.stop()
        if len(audio) < SAMPLE_RATE // 2:
            print("  (too short — try again)")
            continue

        segments, info = stt.transcribe(audio, language=None)
        text = " ".join(s.text for s in segments).strip()
        if not text:
            print("  (didn't catch that)")
            continue
        print(f"  You said ({info.language}): {text}")
        if text.lower() in ("quit", "exit", "stop"):
            print("Bye!")
            break

        messages = handle_turn(text, messages, link)


if __name__ == "__main__":
    main()
