# Skill: Fibonacci spiral

- **Tool:** `fibonacci_spiral`
- **Triggers:** "Fibonacci", "draw a Fibonacci spiral", "फिबोनाची सर्पिल काढ", "Fibonacci sequence"
- **When to use:** the child asks for a Fibonacci spiral, a Fibonacci pattern, or a Fibonacci sequence of moves. Do NOT use it for an ordinary "go forward" — only when Fibonacci is named.

## What it means

A Fibonacci spiral is a walk that grows by the Fibonacci numbers:
forward 1, turn left, forward 2, turn left, forward 3, turn left,
forward 5, turn left, forward 8 — then STOP.

The numbers are 1, 2, 3, 5, 8. Each number is the sum of the two
before it (1+1=2, 1+2=3, 2+3=5, 3+5=8). That growing pattern is the
whole point — it is not just "walk a lot".

## Steps

Call `fibonacci_spiral` ONCE. It expands in code to the full sequence
(19 forwards + 4 turns) and stops after 8. Do not expand it yourself
into separate move_forward / turn_left calls.
