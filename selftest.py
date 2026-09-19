"""
Azisly Hackathon -- Round 2 submission self-check.

    python selftest.py robot.py

This checks that your file *runs and talks to the grader correctly*. It replays a
short canned sensor sequence at your program and checks that every reply is a
well-formed action.

It says NOTHING about whether your maze-solving logic is any good -- it never
simulates a maze. What it catches is the plumbing mistakes that would otherwise turn
a perfectly good robot into a zero:

  * a crash or a syntax error at import time
  * a stray print() going to stdout and being read as your action
  * a forgotten flush, so the grader waits forever for a reply
  * returning something that is not one of the four legal actions

Run it before every submission. It takes about a second.
"""

import json
import subprocess
import sys
import threading
import queue
from pathlib import Path

ACTIONS = ("forward", "turn_left", "turn_right", "wait")
STARTUP_TIMEOUT = 10.0
TICK_TIMEOUT = 2.0

# A short stream with a few different shapes: open corridor, wall ahead, a
# collision, a turn, and finally the goal.
PACKETS = [
    {"tick": 0, "dist_front": 3, "dist_left": 0, "dist_right": 0,
     "rpm_left": 0, "rpm_right": 0, "accel_fwd": 0.0, "accel_lat": 0.0, "at_goal": False},
    {"tick": 1, "dist_front": 2, "dist_left": 0, "dist_right": 1,
     "rpm_left": 120, "rpm_right": 120, "accel_fwd": 1.0, "accel_lat": 0.0, "at_goal": False},
    {"tick": 2, "dist_front": 0, "dist_left": 2, "dist_right": 0,
     "rpm_left": 120, "rpm_right": 120, "accel_fwd": 0.0, "accel_lat": 0.0, "at_goal": False},
    {"tick": 3, "dist_front": 0, "dist_left": 2, "dist_right": 0,
     "rpm_left": 0, "rpm_right": 0, "accel_fwd": -2.0, "accel_lat": 0.0, "at_goal": False},
    {"tick": 4, "dist_front": 2, "dist_left": 0, "dist_right": 0,
     "rpm_left": -60, "rpm_right": 60, "accel_fwd": 0.0, "accel_lat": -1.0, "at_goal": False},
    {"tick": 5, "dist_front": 1, "dist_left": 0, "dist_right": 0,
     "rpm_left": 120, "rpm_right": 120, "accel_fwd": 1.0, "accel_lat": 0.0, "at_goal": True},
]


def _reader(stream, sink):
    for line in stream:
        sink.put(line)
    sink.put(None)


def fail(message, hint=""):
    print(f"\n  FAILED: {message}")
    if hint:
        print(f"  hint:   {hint}")
    return 1


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    target = Path(sys.argv[1])
    if not target.is_file():
        return fail(f"no such file: {target}")

    print(f"checking {target.name} ...")
    proc = subprocess.Popen(
        [sys.executable, "-u", str(target)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=_reader, args=(proc.stdout, lines), daemon=True).start()

    def read(timeout, what):
        try:
            line = lines.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError(what)
        if line is None:
            raise EOFError(what)
        return line

    try:
        # 1. handshake
        try:
            line = read(STARTUP_TIMEOUT, "startup")
        except TimeoutError:
            return fail(
                "your program never printed the ready line",
                "do not do slow work at import time; keep the DO NOT EDIT block intact",
            )
        except EOFError:
            err = proc.stderr.read()
            return fail("your program crashed on startup", err.strip()[-800:] or "no error output")

        try:
            handshake = json.loads(line)
        except json.JSONDecodeError:
            return fail(
                f"first line of output was not JSON: {line.strip()[:120]!r}",
                "something is print()ing to stdout before the handshake",
            )
        if handshake.get("ready") is not True:
            return fail(f'first line should be {{"ready": true}}, got {line.strip()[:120]!r}')
        print("  handshake       ok")

        # 2. the tick loop
        for packet in PACKETS:
            proc.stdin.write(json.dumps(packet) + "\n")
            proc.stdin.flush()
            try:
                line = read(TICK_TIMEOUT, f"tick {packet['tick']}")
            except TimeoutError:
                return fail(
                    f"no reply to tick {packet['tick']} within {TICK_TIMEOUT}s",
                    "either decide() is too slow, or your output is not being flushed",
                )
            except EOFError:
                err = proc.stderr.read()
                return fail(
                    f"your program exited during tick {packet['tick']}",
                    err.strip()[-800:] or "no error output",
                )

            try:
                reply = json.loads(line)
            except json.JSONDecodeError:
                return fail(
                    f"tick {packet['tick']}: reply was not JSON: {line.strip()[:120]!r}",
                    "a stray print() in decide() will land here -- use "
                    "print(..., file=sys.stderr) for debugging",
                )
            action = reply.get("action")
            if action not in ACTIONS:
                return fail(
                    f"tick {packet['tick']}: {action!r} is not a legal action",
                    f"must be one of {list(ACTIONS)}",
                )
        print(f"  {len(PACKETS)} ticks        ok")

    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        proc.kill()

    stderr = proc.stderr.read().strip()
    if stderr:
        print(f"\n  (your stderr output, which is fine and is returned to you with your results)")
        for line in stderr.splitlines()[-10:]:
            print(f"    {line}")

    print("\n  PASSED -- your submission is well-formed and will be graded on its logic.")
    print("  This does not mean it solves mazes. Only that it will get the chance to try.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
