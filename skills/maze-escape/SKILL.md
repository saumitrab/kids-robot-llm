---
name: maze-escape
description: Use when the child describes a maze and lists the moves to get out, or asks the robot to escape a maze. Follow the child's listed moves in order, never invent moves, stop when they say stop. Triggers on "maze", "get out of the maze", "escape the maze", "भूलभुलैया", "भूलभुलैयातून बाहेर पड".
metadata:
  version: "1.0.0"
  category: navigation
  languages: [en, mr]
---

# Skill: Maze escape

- **Tool:** none — use the ordinary `move_forward`, `move_back`,
  `turn_left`, `turn_right` tools, in the order the child lists them.
- **When to use:** the child describes a maze and lists the moves to
  get out, or asks the robot to find its way out step by step.

## What it means

A maze escape is a LIST of instructions, read in order. Every step
matters, and the order matters — turn right at the wrong place and
the robot is in the wrong corridor. Follow the child's list exactly:
do not skip a step, do not reorder steps, and do not invent extra
moves the child did not say.

Useful translations (the model figures these out, they are not a
word-to-button table):
- "go forward 3" / "तीन पावले पुढे जा" = move_forward three times
- "turn right" / "उजवीकडे वळ" = turn_right once
- "turn left" / "डावीकडे वळ" = turn_left once
- "go back 1" / "एक पाऊल मागे जा" = move_back once
- "dead end, turn around" = turn_left twice
- "stop" / "थांब" = stop — no more moves after this

## Steps

1. Read the whole list before moving.
2. Call one tool per step, in order, all in a single response.
3. Stop when the child says stop, or when the list ends. Do not
   keep going after the last step.
