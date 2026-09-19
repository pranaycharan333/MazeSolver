# Round 2 — Maze Solver

You are writing the brain of a small two-wheeled robot dropped into a maze it has
never seen. Get it to the goal.

## What's in here

| File | What it is |
|---|---|
| `robot.py` | **Your submission.** The only file you edit. |
| `CONTRACT.md` | Everything your robot can sense and do. Read this first — it is short, and it is the whole ruleset. |
| `selftest.py` | Run before submitting. Catches broken plumbing. |
| `play.py` | Watch your robot solve a maze, step by step, in a small window. |
| `sim_lite.py` | Powers `play.py`. You don't need to read or edit it. |
| `mazes/` | The 3 practice mazes, as plain text. |

## Start here

1. Read `CONTRACT.md`. All of it. It takes five minutes and it is the entire game.
2. Open `robot.py`. You edit one function: `decide()`. Everything below the
   `DO NOT EDIT` line handles talking to the grader — leave it alone.
3. What's already in `decide()` is a right-hand wall follower. It works, and it will
   solve the easy mazes. It will not win: it has no memory, so it never learns the
   maze, walks the same long way round every time, and can loop forever in an open
   room. Improving on it is the exercise.
4. Write your logic, then **watch it run** — see the next section.
5. Before you submit: `python selftest.py robot.py`

---

## Testing your solution

### Step 1 — write your code

Put your logic inside the `decide()` function in **`robot.py`**. That is the only
file you edit, and the only file you submit.

### Step 2 — open a terminal in this folder

You need to be *inside* the `student_kit` folder for these commands to work:

```
cd path/to/student_kit
```

### Step 3 — run the visualizer

```
python play.py
```

If `python` isn't recognised, try:

| Your system | Command |
|---|---|
| Windows | `python play.py` (`python3` does **not** work on Windows — it opens the Microsoft Store) |
| macOS / Linux | `python3 play.py` |

A window opens.

### Step 4 — pick a maze, then hit Run

1. Choose a maze from the **dropdown** at the top (`p01.txt`, `p02.txt`, `p03.txt`).
2. Click **Run**. Your robot runs against that maze — this takes a second or two.
3. The maze appears: grey walls, a green dot where you start, a red ring at the goal,
   and a blue triangle showing your robot and which way it's facing.

### Step 5 — watch the replay

Use the buttons along the bottom:

| Button | What it does |
|---|---|
| **Play** | Animates the whole attempt from the start. Click again to pause. |
| **Step >>** | Advances one tick at a time — best for working out *why* it did something. |
| **<< Step** | Goes back a tick. |
| **Speed** slider | How fast Play runs. |

The panel on the right updates every tick with your robot's position, heading, the
action it chose, and the exact sensor values it saw. **This is the useful part** — when
your robot does something stupid, step to that tick and look at what it was actually
sensing when it decided.

### Step 6 — read the result

Bottom right tells you `SOLVED` (with ticks used and collisions) or `NOT SOLVED` with a
reason. If something broke, a message explains what — and if it can't tell what went
wrong, it says so rather than guessing, and points you back at `selftest.py` and your
own debug output.

To print your own debug output, use `stderr` — never plain `print()`:

```python
import sys
print("my robot thinks x =", x, file=sys.stderr)
```

### Step 7 — check it before submitting

```
python selftest.py robot.py
```

This catches the plumbing mistakes that would score you zero regardless of how good
your logic is — a stray `print()`, a crash on startup, a forgotten flush. Run it every
time before you upload.

> **Note:** `play.py` needs `tkinter`, which comes with the normal Windows and macOS
> Python installers. On Linux: `sudo apt install python3-tk`. You don't need it to
> submit — it's only for watching your robot run.

---

## Testing on more than three mazes

The three mazes in this folder are the **only** ones you get locally. They are teaching
examples, not a test set — solving all three means your robot works, not that it will
place well.

**For real testing, upload your file to the competition website.** It runs your robot
against the full hidden **mock** set — many more mazes, much harder, including ones with
short-range sensors, noisy readings and open chambers — and sends back your score with a
per-maze breakdown showing exactly which ones you failed and why.

That is the only way to find out how you are actually doing before the final round. Use
the mock rounds early and often; a robot tuned only against `p01`–`p03` will not survive
the final set.

Note that `play.py` deliberately does **not** score you or tell you the shortest possible
route — only the grader knows those. Locally, judge yourself by comparing your own runs
against each other; for a real score, upload.

## Submitting

Rename `robot.py` to your team id — `team17.py` — and upload it to the website.

One file. Python 3, standard library only. No `pip install`, no extra files, no
internet at runtime.

## Reading the maze files

`mazes/` contains the practice layouts so you can see what you are up against. Your
robot never receives these — it only ever gets sensor readings.

```
!name: p02            <- lines starting with ! are settings, not part of the grid
!sensor_range: 3      <- how far the distance sensors see on this maze
!noise: 0.0           <- chance of a distance reading being wrong by 1
!encoder_jitter: false
!heading: N           <- which way you start facing
###############
#S....#.......#       #  wall
#.###.#.#####.#       .  open
#...#...#...#.#       S  your start
###.#####.#.#.#       G  the goal
#.............#
#####...#####G#
###############
```

`x` counts across, `y` counts **down** from the top. `N` is up the page.

The three practice mazes each teach one thing:

| Maze | What it's for |
|---|---|
| `p01` | A plain maze with good sensors. If your robot can't solve this, nothing else matters yet. |
| `p02` | Loops — more than one route to the goal, so wall-following works but wastes ticks. |
| `p03` | **Encoder jitter.** Wheel RPM wobbles by roughly ±5. If you track position by testing `rpm == 120`, this maze is where you find out. Use a tolerance. |

These three are teaching examples, not a preview. The **mock** set you upload to during
the competition is far larger and harder, and the **final** set is harder still. A robot
that only works on these three will not travel — see `CONTRACT.md` for how the three
sets relate.

## Scoring, in one line

Reaching the goal is worth far more than reaching it quickly, and every wall you hit
costs 5 points plus a wasted tick. Get it solving first. Optimise second.

Full details in `CONTRACT.md`.
