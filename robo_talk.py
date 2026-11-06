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
- You can make the robot do things by calling tools: move_forward, move_back, turn_left, turn_right, dance, sing, tell_story.
- If the child asks the robot to move or do something, call the matching tool AND give a one-sentence reply.
- If the child just wants to chat, just reply — no tool call.
- Never claim you can do things you cannot (no fetching things, no going outside).
- If you are unsure what the child wants, ask one short question instead of guessing a movement.
"""

TOOLS = [
    {"type": "function", "function": {"name": "move_forward", "description": "Drive the robot forward a short distance.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "move_back", "description": "Drive the robot backward a short distance.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "turn_left", "description": "Turn the robot left.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "turn_right", "description": "Turn the robot right.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "dance", "description": "Make the robot do a little dance.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "sing", "description": "Make the robot sing a song.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "tell_story", "description": "Make the robot tell a short story.", "parameters": {"type": "object", "properties": {}}}},
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


class FakeLink:
    """Step 0: no robot. Print the command instead of sending it."""

    def send(self, command: str) -> None:
        print(f"  [ROBOT WOULD DO] {command}  (no radio linked yet — step 1 wires this up)")


class SerialLink:
    """Step 1: send short commands over USB serial to the ESP32 bridge."""

    def __init__(self, port: str, baud: int = 115200):
        import serial

        self.ser = serial.Serial(port, baud, timeout=1)

    def send(self, command: str) -> None:
        wire = COMMAND_WIRE.get(command, command)
        self.ser.write((wire + "\n").encode())
        print(f"  [SENT TO ROBOT] {wire}")


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
    """One user turn: Gemma (native tool calls) -> send + speak."""
    messages.append({"role": "user", "content": text})
    try:
        resp = ollama.chat(model=MODEL, messages=messages, tools=TOOLS)
    except Exception as exc:
        print(f"  Ollama error: {exc}")
        return messages
    msg = resp["message"]
    for call in msg.get("tool_calls") or []:
        name = call["function"]["name"]
        link.send(name)
        messages.append({"role": "tool", "content": f"{name} done"})
    reply = (msg.get("content") or "").strip()
    if not reply and msg.get("tool_calls"):
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

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

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
