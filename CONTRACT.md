# Round 2 — Robot Interface Contract (FROZEN)

**This document will not change.** Everything your robot can ever know, and everything it can
ever do, is on this page. Read it once carefully; it is the whole game.

---

## The situation

Your robot is a micromouse: a small two-wheeled robot dropped into an unknown maze. It has to
find the goal cell.

It does **not** have GPS. It is **not** told where it is, which way it is facing, or what the
maze looks like. It has three onboard sensors and two wheels. That is it.

Everything else — your position, your heading, a map of the maze — you have to work out
yourself from the sensor stream. That is the challenge.

---

## How your program runs

Your program is started once per maze and stays running for the whole attempt.

Every tick:

1. We send you one line of JSON on **stdin** — your sensor readings.
2. You send back one line of JSON on **stdout** — your action.

That loop is already written for you in `robot.py`, inside a block marked
`DO NOT EDIT`. You only fill in one function: `decide(sensors, memory)`.

You may print debugging output to **stderr** (`print(..., file=sys.stderr)`) — it is captured
and returned to you with your results. Never print anything to stdout except your action; a
stray `print()` will be read as a malformed action and end your run.

### Startup handshake

Before the first sensor packet, your program prints `{"ready": true}`. This is already in the
template. It tells us your file imported successfully. You have **10 seconds** to reach it —
so don't do heavy work at import time.

---

## What you receive each tick

One JSON object per line on stdin:

```json
{"tick": 12, "dist_front": 0, "dist_left": 3, "dist_right": 1,
 "rpm_left": 0, "rpm_right": 0,
 "accel_fwd": -2.0, "accel_lat": 0.0,
 "at_goal": false}
```

| Field | Type | Meaning |
|---|---|---|
| `tick` | int | Tick counter, starts at 0 |
| `dist_front` | int | Open cells ahead of you before a wall |
| `dist_left` | int | Open cells to your left before a wall |
| `dist_right` | int | Open cells to your right before a wall |
| `rpm_left` | int | Left wheel speed produced by your **previous** action |
| `rpm_right` | int | Right wheel speed produced by your **previous** action |
| `accel_fwd` | float | Forward acceleration, cells per tick squared |
| `accel_lat` | float | Lateral acceleration (positive = to your right) |
| `at_goal` | bool | `true` when you are standing on the goal (see note) |

**Note on `at_goal`:** your run ends the instant you step onto the goal, so in a real run
you will normally never receive a packet with this set to `true` — the grader stops before
asking you for another action. It is in the packet so your code can be written defensively,
and `selftest.py` does send it. Do not build your logic around waiting to see it.

### Reading the distance sensors

`dist_front: 0` means there is a wall in the cell directly in front of you — you cannot move
forward. `dist_front: 3` means three open cells ahead, then a wall.

Readings are **clamped to that maze's sensor range**. If the range is 2, you will never see a
value above 2, and a `2` means "at least 2 — could be more." Later mazes have a range of `1`,
so you can only feel the walls immediately touching you.

Distance readings are always relative to the direction you are currently facing. Turning
changes what `dist_front` means.

### Reading the wheels

| Your last action | `rpm_left` | `rpm_right` |
|---|---|---|
| `forward` (moved successfully) | `+120` | `+120` |
| `forward` (blocked by a wall) | `0` | `0` |
| `turn_left` | `-60` | `+60` |
| `turn_right` | `+60` | `-60` |
| `wait` | `0` | `0` |

This is your odometry. Both wheels at `+120` means you actually advanced one cell. Wheels
counter-rotating means you turned 90°. **This is how you track your own position and heading.**

On the hardest mazes the wheels have encoder jitter — a spinning wheel reports roughly ±5 off
its true value. A stalled wheel always reports exactly `0`. So compare with a tolerance, not
with `==`.

### Reading the accelerometer

| Situation | `accel_fwd` |
|---|---|
| Started moving from rest | `+1.0` |
| Continued moving | `0.0` |
| Stopped moving | `-1.0` |
| **Hit a wall** | `-2.0` |

`accel_lat` is `+1.0` on a `turn_right`, `-1.0` on a `turn_left`, `0.0` otherwise.

### There is no collision flag — you infer it

We do not tell you when you crash. You work it out: you commanded `forward`, and the wheels
came back `0, 0` with `accel_fwd` at `-2.0`. That is an impact. Your robot did not move, and
you lost points.

Detecting this correctly and updating your internal map accordingly is worth real marks.

---

## What you send back

One JSON object per line on stdout:

```json
{"action": "forward"}
```

`action` must be exactly one of:

| Action | Effect |
|---|---|
| `forward` | Move one cell in the direction you are facing. Blocked by a wall = collision, you stay put |
| `turn_left` | Rotate 90° left, in place |
| `turn_right` | Rotate 90° right, in place |
| `wait` | Do nothing |

**One action = one tick.** Turning costs a tick just like moving does, so a route with fewer
turns scores better than a route with the same number of moves and more turns.

Anything else — a different action name, invalid JSON, an extra line of output — ends your run
on that maze with a score of zero.

---

## How the maze behaves

- The maze is a grid of cells. Walls sit between cells or around the border.
- The maze never changes during your run. Walls do not move.
- Movement is fully deterministic. `forward` into an open cell always works.
- **Only the sensors get noisy**, and only on the hardest mazes: reduced range, occasional ±1
  error on distance readings, encoder jitter. Every team gets the exact same noise on the same
  maze at the same tick — it is generated from a fixed seed, not randomly per team.
- Your run ends as soon as `at_goal` is `true` on a tick you receive.

---

## The three sets of mazes

| Set | Where | Scored? | What it's for |
|---|---|---|---|
| **Practice** | The 3 mazes in `mazes/`, on your own machine | No | Learning and debugging. Run them as often as you like with `play.py`. |
| **Mock** | Hidden. Upload during the competition | Yes | Batch-graded, results sent back. Your rehearsal for the real thing. |
| **Final** | Hidden. Run once at the end | Yes | This is the one that counts. |

The practice mazes are **not** a preview of the graded sets — they are three teaching
examples: one plain maze, one with loops, one with encoder jitter. The mock set is much
larger and harder, and the final set is harder again.

Solving all three practice mazes means your robot works. It does not mean it will place
well. Use the mock rounds to find that out while there is still time to fix it.

---

## Limits

Exceed any of these and that maze scores zero:

| Limit | Mock | Final |
|---|---|---|
| Time to print `{"ready": true}` | 10 s | 10 s |
| Time to answer one tick | 0.75 s | 0.5 s |
| Ticks per maze | 7 × optimal + 350 | 6 × optimal + 300 |
| Wall clock per maze | 45 s | 30 s |
| Wall clock for your whole submission | 15 min | 10 min |

"Optimal" is the fewest ticks in which that maze can be solved, counting turns. You will not be
told what it is.

The tick cap is generous — you do not need to be fast, you need to not loop forever. A robot
that wanders sensibly will finish well inside it.

---

## Scoring

Per maze:

```
not solved                -> 0
solved                    -> max(10, 100 - 2 * (your_ticks - optimal_ticks) - 5 * collisions)
```

Your total is the sum across all mazes. Ties break on mazes solved (more is better),
then total ticks, then total collisions.

Three consequences worth internalising:

1. **Solving always beats not solving.** A clumsy solve still scores at least 10. An elegant
   robot that times out scores 0. Get to the goal first, optimise second.
2. **Crashing into walls is expensive** — 5 points each, and the collision tick is wasted too,
   so it really costs 7. If your sensors say there is a wall, believe them.
3. **Exploration you never reuse is what kills your score.** Both wall-following and blind
   flood-fill will find the goal. The teams that place well are the ones whose robot remembers
   what it learned and takes a better route once it knows the maze.

---

## Rules

- **One file.** Python 3.11+, standard library only. No `pip install`, no extra files.
- Your file runs in an isolated process with no network access.
- Do not attempt to read anything outside your own file, locate the hidden mazes, or interfere
  with the grader. This is checked, and it disqualifies your team.
- Do not edit anything in the `DO NOT EDIT` block.
- Your robot must decide from the sensor stream. Hardcoding a move sequence for a specific
  maze is not a maze solver, and the hidden mazes make it worthless anyway.

---

## Watching your robot run

```
python play.py
```

Opens a window where you can run your robot against any of the 3 practice mazes and
step through the attempt tick by tick — position, heading, sensor readings, and the
action taken each time. If the run fails, it will tell you what went wrong when it
recognizes the problem (a crash, a timeout, an invalid action); if it doesn't
recognize the problem, it will say so honestly rather than guess, and point you at
`selftest.py` and your own `stderr` output instead.

It tells you **whether you solved the maze and how many ticks you took** — nothing
more. It deliberately does not score you and does not tell you the shortest possible
route. Only the grader knows those, and a local guess at them would just mislead you.
Judge your efficiency by comparing your own runs against each other, and by what the
mock rounds tell you.

This is for your own practice only — it never talks to us and has nothing to do
with your score.

## Before you submit

Run:

```
python selftest.py robot.py
```

This checks your file starts up and answers well-formed actions. It does **not** check whether
your logic is any good — it catches the plumbing mistakes (a stray `print`, a crash on import,
a forgotten `flush`) that would otherwise turn a working robot into a zero.

Passing selftest is not a score. It just means your submission will be graded on its logic.
