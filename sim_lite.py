"""
Local practice simulator -- used by play.py, not by your robot.

This is a self-contained copy of the same maze physics described in CONTRACT.md: same
field names, same wall sensing, same wheel/accelerometer formulas. It exists so you can
watch your robot run on your own machine without needing anything outside this folder.

It is deliberately not the real grader. It has no security sandboxing (it's your own
code, on your own computer -- there's nothing to protect it from) and its timeouts are
a bit more relaxed than the real thing, since your machine also has to draw the GUI.
The maze physics themselves are exactly what CONTRACT.md documents.

You do not need to read this file to solve the maze. It is here so play.py has
something to import.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HEADINGS = ("N", "E", "S", "W")
DELTA = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
WALL, OPEN, START, GOAL = "#", ".", "S", "G"
ACTIONS = ("forward", "turn_left", "turn_right", "wait")

CRUISE_RPM = 120
TURN_RPM = 60
IMPACT_ACCEL = -2.0
JITTER = 5

# More relaxed than the real grader's caps -- this runs alongside a GUI on whatever
# laptop a student brought, not on a dedicated grading box.
STARTUP_TIMEOUT = 10.0
TICK_TIMEOUT = 2.0
MAZE_WALLCLOCK = 120.0


class MazeError(ValueError):
    pass


class RunProblem(Exception):
    """A basic, recognisable failure -- shown to the student with a specific message.

    Anything that is NOT one of these is left to bubble up as a generic error in the
    GUI, on purpose: see play.py's `_friendly_message`.
    """

    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(message)


def turn(heading: str, direction: str) -> str:
    i = HEADINGS.index(heading)
    return HEADINGS[(i + 1) % 4] if direction == "right" else HEADINGS[(i - 1) % 4]


def relative(heading: str, side: str) -> str:
    if side == "front":
        return heading
    if side == "left":
        return turn(heading, "left")
    if side == "right":
        return turn(heading, "right")
    return turn(turn(heading, "right"), "right")


@dataclass
class Maze:
    name: str
    rows: list[str]
    start: tuple[int, int]
    goal: tuple[int, int]
    start_heading: str
    seed: int
    sensor_range: int
    noise: float
    encoder_jitter: bool

    @property
    def width(self) -> int:
        return len(self.rows[0])

    @property
    def height(self) -> int:
        return len(self.rows)

    def is_open(self, x: int, y: int) -> bool:
        if not (0 <= y < self.height and 0 <= x < self.width):
            return False
        return self.rows[y][x] != WALL

    def distance(self, x: int, y: int, heading: str) -> int:
        dx, dy = DELTA[heading]
        d = 0
        cx, cy = x, y
        while d < self.sensor_range:
            cx, cy = cx + dx, cy + dy
            if not self.is_open(cx, cy):
                break
            d += 1
        return d


_DEFAULTS = {
    "name": "unnamed", "seed": 0, "sensor_range": 4,
    "noise": 0.0, "encoder_jitter": False, "heading": "N",
}


def parse_maze(text: str, name_hint: str = "") -> Maze:
    meta = dict(_DEFAULTS)
    rows = []
    for line in text.splitlines():
        line = line.rstrip("\r\n")
        if not line.strip():
            continue
        if line.startswith("!"):
            key, _, value = line[1:].partition(":")
            key, value = key.strip(), value.strip()
            if key not in meta:
                continue
            default = _DEFAULTS[key]
            if isinstance(default, bool):
                meta[key] = value.lower() == "true"
            elif isinstance(default, int):
                meta[key] = int(value)
            elif isinstance(default, float):
                meta[key] = float(value)
            else:
                meta[key] = value
        else:
            rows.append(line)

    if not rows:
        raise MazeError("maze file has no grid rows")
    width = max(len(r) for r in rows)
    rows = [r.ljust(width, WALL) for r in rows]

    start = goal = None
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == START:
                start = (x, y)
            elif ch == GOAL:
                goal = (x, y)
    if start is None or goal is None:
        raise MazeError("maze needs both a start (S) and a goal (G)")

    if meta["name"] == "unnamed" and name_hint:
        meta["name"] = name_hint

    return Maze(
        name=meta["name"], rows=rows, start=start, goal=goal,
        start_heading=meta["heading"], seed=int(meta["seed"]),
        sensor_range=int(meta["sensor_range"]), noise=float(meta["noise"]),
        encoder_jitter=bool(meta["encoder_jitter"]),
    )


def load_maze(path: str | Path) -> Maze:
    p = Path(path)
    return parse_maze(p.read_text(encoding="utf-8"), name_hint=p.stem)


def _tick_budget(maze: Maze) -> int:
    """A generous ceiling so a looping robot stops rather than running forever.

    Deliberately NOT derived from the shortest possible solution: this tool does not
    compute one. How efficient your route is, and what that is worth, is decided by
    the grader -- not here.
    """
    open_cells = sum(row.count(OPEN) + row.count(START) + row.count(GOAL) for row in maze.rows)
    return 30 * open_cells + 500


@dataclass
class Tick:
    tick: int
    x: int
    y: int
    heading: str
    sensors: dict
    action: str | None
    collided: bool


@dataclass
class RunResult:
    """What happened. Note there is no score and no "optimal" here, on purpose --
    this tool tells you whether you solved it and how many ticks you took, and
    leaves judging that to the grader."""

    solved: bool
    ticks: int
    collisions: int
    reason: str | None
    detail: str
    replay: list[Tick] = field(default_factory=list)


def _rng(maze: Maze, tick: int, sensor_id: str) -> random.Random:
    return random.Random(f"{maze.seed}:{tick}:{sensor_id}")


def _build_packet(maze: Maze, x: int, y: int, heading: str, tick: int, motion) -> dict:
    packet = {"tick": tick}
    for side in ("front", "left", "right"):
        reading = maze.distance(x, y, relative(heading, side))
        if maze.noise > 0.0:
            rng = _rng(maze, tick, f"dist_{side}")
            if rng.random() < maze.noise:
                reading = max(0, min(maze.sensor_range, reading + rng.choice((-1, 1))))
        packet[f"dist_{side}"] = reading

    left, right = motion["rpm"]
    if maze.encoder_jitter:
        for label, value in (("rpm_left", left), ("rpm_right", right)):
            if value != 0:
                value += _rng(maze, tick, label).randint(-JITTER, JITTER)
            packet[label] = value
    else:
        packet["rpm_left"], packet["rpm_right"] = left, right

    packet["accel_fwd"], packet["accel_lat"] = motion["accel"]
    packet["at_goal"] = (x, y) == maze.goal
    return packet


class _Reader:
    """Reads subprocess stdout on a background thread so we can enforce a timeout."""

    def __init__(self, stream):
        import queue
        import threading

        self._q = queue.Queue()
        self._queue_mod = queue

        def pump():
            for line in stream:
                self._q.put(line)
            self._q.put(None)

        threading.Thread(target=pump, daemon=True).start()

    def readline(self, timeout: float) -> str | None:
        try:
            return self._q.get(timeout=timeout)
        except self._queue_mod.Empty:
            return _TIMEOUT_MARKER


_TIMEOUT_MARKER = object()


def run(robot_path: str | Path, maze: Maze, on_tick=None) -> RunResult:
    """Run robot_path against maze, calling on_tick(Tick) as each tick resolves.

    Basic, recognisable problems are raised as RunProblem with a `kind` matching
    the CONTRACT.md vocabulary. Anything else is a genuine bug and is left to
    propagate -- the caller (play.py) turns that into a generic message on purpose.
    """
    tick_cap = _tick_budget(maze)

    proc = subprocess.Popen(
        [sys.executable, "-u", str(robot_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    reader = _Reader(proc.stdout)

    def stderr_tail() -> str:
        try:
            proc.stderr.flush()
        except Exception:
            pass
        try:
            out = proc.stderr.read()
        except Exception:
            out = ""
        lines = [l for l in out.strip().splitlines() if l.strip()]
        return lines[-1] if lines else ""

    replay: list[Tick] = []
    x, y = maze.start
    heading = maze.start_heading
    collisions = 0
    solved = False
    reason = None
    detail = ""
    tick = 0
    motion = {"rpm": (0, 0), "accel": (0.0, 0.0)}
    started = time.monotonic()

    try:
        line = reader.readline(STARTUP_TIMEOUT)
        if line is _TIMEOUT_MARKER:
            raise RunProblem("startup_timeout", "your program never signalled it was ready")
        if not line:
            raise RunProblem(
                "startup_crash",
                f"your program crashed on startup: {stderr_tail() or 'no error message'}",
            )
        try:
            handshake = json.loads(line)
        except json.JSONDecodeError:
            raise RunProblem(
                "handshake_invalid",
                f"first line of output wasn't JSON: {line.strip()[:120]!r}",
            )
        if handshake.get("ready") is not True:
            raise RunProblem(
                "handshake_invalid",
                f'expected {{"ready": true}}, got {line.strip()[:120]!r}',
            )

        while True:
            packet = _build_packet(maze, x, y, heading, tick, motion)
            at_goal = (x, y) == maze.goal

            if at_goal:
                solved = True
                replay.append(Tick(tick, x, y, heading, packet, None, False))
                if on_tick:
                    on_tick(replay[-1])
                break
            if tick >= tick_cap:
                reason, detail = "tick_cap", "did not reach the goal within the tick budget"
                replay.append(Tick(tick, x, y, heading, packet, None, False))
                if on_tick:
                    on_tick(replay[-1])
                break
            if time.monotonic() - started > MAZE_WALLCLOCK:
                reason, detail = "wallclock_cap", "the run took too long overall"
                break

            proc.stdin.write(json.dumps(packet) + "\n")
            try:
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                raise RunProblem(
                    "crash", f"your program stopped responding: {stderr_tail() or 'no error message'}"
                )

            reply_line = reader.readline(TICK_TIMEOUT)
            if reply_line is _TIMEOUT_MARKER:
                raise RunProblem(
                    "tick_timeout", f"your program took too long to respond on tick {tick}"
                )
            if not reply_line:
                raise RunProblem(
                    "crash", f"your program crashed: {stderr_tail() or 'no error message'}"
                )
            try:
                reply = json.loads(reply_line)
                action = reply["action"]
            except (json.JSONDecodeError, KeyError, TypeError):
                raise RunProblem(
                    "malformed_output",
                    f"tick {tick}: not a valid action packet: {reply_line.strip()[:120]!r}",
                )
            if action not in ACTIONS:
                raise RunProblem(
                    "illegal_action",
                    f"tick {tick}: {action!r} is not forward/turn_left/turn_right/wait",
                )

            # Record the state the packet actually described -- i.e. before this
            # action is applied -- then update x/y/heading for the next tick.
            pre_x, pre_y, pre_heading = x, y, heading
            collided = False

            if action == "forward":
                dx, dy = DELTA[heading]
                nx, ny = x + dx, y + dy
                if maze.is_open(nx, ny):
                    x, y = nx, ny
                    motion = {"rpm": (CRUISE_RPM, CRUISE_RPM), "accel": (1.0, 0.0)}
                else:
                    collisions += 1
                    collided = True
                    motion = {"rpm": (0, 0), "accel": (IMPACT_ACCEL, 0.0)}
            elif action in ("turn_left", "turn_right"):
                direction = "left" if action == "turn_left" else "right"
                heading = turn(heading, direction)
                rot = -1 if direction == "left" else 1
                rpm = (-TURN_RPM, TURN_RPM) if rot == -1 else (TURN_RPM, -TURN_RPM)
                motion = {"rpm": rpm, "accel": (0.0, float(rot))}
            else:  # wait
                motion = {"rpm": (0, 0), "accel": (0.0, 0.0)}

            record = Tick(tick, pre_x, pre_y, pre_heading, packet, action, collided)
            replay.append(record)
            if on_tick:
                on_tick(record)
            tick += 1

    except RunProblem as problem:
        reason, detail = problem.kind, str(problem)
    finally:
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                pass

    if not solved and reason is None:
        reason, detail = "no_goal", "the run ended without reaching the goal"

    return RunResult(
        solved=solved, ticks=tick, collisions=collisions,
        reason=reason, detail=detail, replay=replay,
    )
