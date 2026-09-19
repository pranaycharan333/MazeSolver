"""
Watch your robot solve a maze.

    python play.py
    python play.py robot.py
    python play.py robot.py mazes/m04.txt

A small GUI: pick a maze, run your robot against it, then step or play back the
attempt tick by tick to see exactly where it went and why. Runs entirely on your own
machine -- nothing is sent anywhere.

It tells you whether you solved the maze and how many ticks you took. It does not
score you and does not tell you the shortest possible route -- that is the grader's
job, and guessing at it here would only mislead you.

Standard library only (uses tkinter, which ships with the normal python.org installer
on Windows and macOS; on Linux you may need to install it separately, e.g.
`sudo apt install python3-tk`). If tkinter isn't available, this file just won't run --
selftest.py and CONTRACT.md don't depend on it.
"""

from __future__ import annotations

import sys
import threading
import traceback
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    print("This tool needs tkinter, which isn't installed.")
    print("On Linux, try: sudo apt install python3-tk")
    print("You don't need this to submit -- it's just for watching your robot run.")
    raise SystemExit(1)

import sim_lite

HERE = Path(__file__).resolve().parent

# Basic, recognisable problems get a specific, actionable message. Anything not in
# this map is left as "an unspecified error occurred" -- see _friendly_message.
_HINTS = {
    "startup_crash": "Your program crashed as soon as it started.",
    "startup_timeout": "Your program never printed the ready signal in time.\n"
                        "Make sure {\"ready\": true} is printed before any slow setup.",
    "handshake_invalid": "The first thing your program printed wasn't the expected\n"
                          "{\"ready\": true} line. Check nothing else prints to stdout first.",
    "crash": "Your program stopped responding partway through the run.",
    "malformed_output": "Your program sent something that wasn't a valid action.\n"
                         "Check you're only ever printing one JSON action per line,\n"
                         "and that any debug prints go to sys.stderr, not stdout.",
    "illegal_action": "Your program returned an action that doesn't exist.\n"
                       "Valid actions: forward, turn_left, turn_right, wait.",
    "tick_timeout": "Your program took too long to respond to a tick.\n"
                     "Check decide() isn't stuck in a loop or waiting on something.",
    "wallclock_cap": "The run took too long overall and was stopped.",
}


def _friendly_message(reason: str | None, detail: str) -> str:
    """Basic, known problems get a specific hint. Anything else stays vague on
    purpose -- the point is to send students to their own stderr output and
    selftest.py rather than to hand them a diagnosis."""
    if reason in _HINTS:
        return f"{_HINTS[reason]}\n\n{detail}"
    if reason in ("tick_cap", "no_goal"):
        return (
            "Your robot didn't reach the goal.\n\n"
            "This isn't a crash -- your program ran the whole time, it just never "
            "found the goal within the tick budget. Common causes: looping between "
            "the same few cells, or a wall-follower stuck in an open room."
        )
    return (
        "An unspecified error occurred.\n\n"
        "This tool doesn't recognise what went wrong, which usually means it's "
        "something in your own logic rather than the plumbing. A few things to try:\n"
        "  1. Run: python selftest.py robot.py -- confirms the basics still work\n"
        "  2. Add print(..., file=sys.stderr) inside decide() to see what your\n"
        "     robot believes is happening at each tick\n"
        "  3. Check the terminal this window was launched from for a Python "
        "traceback"
    )


class App:
    CELL = 26
    PAD = 16

    COLORS = {
        "bg": "#1e1e26",
        "wall": "#3a3a46",
        "open": "#f4f4f8",
        "start": "#4ade80",
        "goal": "#f97362",
        "goal_ring": "#7a1f14",
        "robot": "#3b82f6",
        "collision": "#ef4444",
        "grid_line": "#d8d8e0",
    }

    def __init__(self, root: tk.Tk, robot_path: Path, maze_dir: Path, initial_maze: Path | None):
        self.root = root
        self.robot_path = robot_path
        self.maze_dir = maze_dir
        self.result: sim_lite.RunResult | None = None
        self.frame_index = 0
        self.playing = False
        self.play_job = None

        root.title(f"Maze Practice -- {robot_path.name}")
        root.configure(bg=self.COLORS["bg"])
        root.geometry("980x680")
        root.minsize(760, 560)

        self._build_layout()
        self._populate_mazes(initial_maze)

    # ------------------------------------------------------------------ layout

    def _build_layout(self):
        top = tk.Frame(self.root, bg=self.COLORS["bg"])
        top.pack(side="top", fill="x", padx=12, pady=10)

        tk.Label(top, text="Maze:", bg=self.COLORS["bg"], fg="white").pack(side="left")
        self.maze_var = tk.StringVar()
        self.maze_menu = ttk.Combobox(top, textvariable=self.maze_var, state="readonly", width=28)
        self.maze_menu.pack(side="left", padx=(6, 14))

        self.run_btn = ttk.Button(top, text="Run", command=self._on_run)
        self.run_btn.pack(side="left")

        self.status_var = tk.StringVar(value="Pick a maze and press Run.")
        tk.Label(
            top, textvariable=self.status_var, bg=self.COLORS["bg"], fg="#c9c9d4",
            anchor="w",
        ).pack(side="left", padx=14, fill="x", expand=True)

        body = tk.Frame(self.root, bg=self.COLORS["bg"])
        body.pack(side="top", fill="both", expand=True, padx=12, pady=(0, 10))

        self.canvas = tk.Canvas(body, bg=self.COLORS["bg"], highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        side = tk.Frame(body, bg="#26262f", width=280)
        side.pack(side="right", fill="y", padx=(10, 0))
        side.pack_propagate(False)
        self._build_sidepanel(side)

        bottom = tk.Frame(self.root, bg=self.COLORS["bg"])
        bottom.pack(side="bottom", fill="x", padx=12, pady=(0, 12))
        self._build_playback(bottom)

    def _build_sidepanel(self, parent):
        pad = dict(padx=12, pady=(10, 0))
        tk.Label(parent, text="This tick", bg="#26262f", fg="white",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", **pad)

        self.info_var = tk.StringVar(value="--")
        tk.Label(parent, textvariable=self.info_var, bg="#26262f", fg="#c9c9d4",
                 justify="left", anchor="w").pack(anchor="w", padx=12, pady=(4, 0))

        tk.Label(parent, text="Sensors", bg="#26262f", fg="white",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", **pad)
        self.sensor_var = tk.StringVar(value="--")
        tk.Label(parent, textvariable=self.sensor_var, bg="#26262f", fg="#c9c9d4",
                 justify="left", anchor="w", font=("Consolas", 9)).pack(
            anchor="w", padx=12, pady=(4, 0)
        )

        tk.Label(parent, text="Result", bg="#26262f", fg="white",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", **pad)
        self.result_var = tk.StringVar(value="Not run yet.")
        tk.Label(parent, textvariable=self.result_var, bg="#26262f", fg="#c9c9d4",
                 justify="left", anchor="w", wraplength=250).pack(
            anchor="w", padx=12, pady=(4, 0)
        )

        self.problem_text = tk.Text(
            parent, height=10, width=30, bg="#1a1a20", fg="#f0a0a0",
            wrap="word", relief="flat", padx=8, pady=8,
        )
        self.problem_text.pack(side="bottom", fill="x", padx=12, pady=12)
        self.problem_text.insert("1.0", "")
        self.problem_text.configure(state="disabled")

    def _build_playback(self, parent):
        self.step_back_btn = ttk.Button(parent, text="<< Step", command=self._step_back,
                                         state="disabled")
        self.step_back_btn.pack(side="left")

        self.play_btn = ttk.Button(parent, text="Play", command=self._toggle_play,
                                    state="disabled")
        self.play_btn.pack(side="left", padx=6)

        self.step_fwd_btn = ttk.Button(parent, text="Step >>", command=self._step_forward,
                                        state="disabled")
        self.step_fwd_btn.pack(side="left")

        tk.Label(parent, text="Speed:", bg=self.COLORS["bg"], fg="white").pack(
            side="left", padx=(18, 4)
        )
        self.speed_var = tk.DoubleVar(value=12.0)
        ttk.Scale(parent, from_=1, to=40, variable=self.speed_var, length=140).pack(
            side="left"
        )

        self.tick_var = tk.StringVar(value="tick -/-")
        tk.Label(parent, textvariable=self.tick_var, bg=self.COLORS["bg"], fg="#c9c9d4").pack(
            side="right"
        )

    # ------------------------------------------------------------------- setup

    def _populate_mazes(self, initial_maze: Path | None):
        files = sorted(self.maze_dir.glob("*.txt")) if self.maze_dir.is_dir() else []
        if not files:
            self.status_var.set(f"No mazes found in {self.maze_dir}")
            self.maze_menu["values"] = []
            return
        self.maze_menu["values"] = [f.name for f in files]
        self._maze_files = {f.name: f for f in files}
        default = initial_maze.name if initial_maze and initial_maze.name in self._maze_files else files[0].name
        self.maze_var.set(default)

    # -------------------------------------------------------------------- run

    def _on_run(self):
        name = self.maze_var.get()
        if not name:
            return
        maze_path = self._maze_files[name]
        self.run_btn.configure(state="disabled")
        self._set_playback_enabled(False)
        self._clear_problem()
        self.status_var.set(f"Running your robot against {name} ...")
        self.result = None
        self.frame_index = 0

        thread = threading.Thread(target=self._run_worker, args=(maze_path,), daemon=True)
        thread.start()

    def _run_worker(self, maze_path: Path):
        try:
            maze = sim_lite.load_maze(maze_path)
            result = sim_lite.run(self.robot_path, maze)
        except Exception:  # noqa: BLE001 -- deliberately broad, see module docstring
            tb = traceback.format_exc()
            self.root.after(0, lambda: self._on_run_error(tb))
            return
        self.root.after(0, lambda: self._on_run_done(maze, result))

    def _on_run_error(self, traceback_text: str):
        self.run_btn.configure(state="normal")
        self.status_var.set("Something went wrong running the visualizer.")
        self._show_problem(_friendly_message(None, ""))
        print(traceback_text, file=sys.stderr)  # still in the terminal for real debugging

    def _on_run_done(self, maze: sim_lite.Maze, result: sim_lite.RunResult):
        self.maze = maze
        self.result = result
        self.run_btn.configure(state="normal")

        self._draw_maze()
        if result.replay:
            self._set_playback_enabled(True)
            self.frame_index = 0
            self._render_frame()

        if result.solved:
            self.status_var.set(f"Solved {maze.name} in {result.ticks} ticks.")
            self.result_var.set(
                f"SOLVED\nticks used: {result.ticks}\ncollisions: {result.collisions}"
            )
            self._clear_problem()
        else:
            self.status_var.set(f"Did not solve {maze.name}.")
            self.result_var.set(
                f"NOT SOLVED\nreason: {result.reason}\n"
                f"ticks used: {result.ticks}\ncollisions: {result.collisions}"
            )
            self._show_problem(_friendly_message(result.reason, result.detail))

    # -------------------------------------------------------------- rendering

    def _cell_bbox(self, x: int, y: int):
        cell = self.CELL
        x0 = self.PAD + x * cell
        y0 = self.PAD + y * cell
        return x0, y0, x0 + cell, y0 + cell

    def _draw_maze(self):
        self.canvas.delete("all")
        maze = self.maze
        for y in range(maze.height):
            for x in range(maze.width):
                x0, y0, x1, y1 = self._cell_bbox(x, y)
                ch = maze.rows[y][x]
                if ch == sim_lite.WALL:
                    color = self.COLORS["wall"]
                else:
                    color = self.COLORS["open"]
                self.canvas.create_rectangle(
                    x0, y0, x1, y1, fill=color, outline=self.COLORS["grid_line"], width=1
                )

        sx, sy = maze.start
        gx, gy = maze.goal
        x0, y0, x1, y1 = self._cell_bbox(sx, sy)
        self.canvas.create_oval(x0 + 5, y0 + 5, x1 - 5, y1 - 5, fill=self.COLORS["start"], outline="")
        x0, y0, x1, y1 = self._cell_bbox(gx, gy)
        self.canvas.create_oval(x0 + 3, y0 + 3, x1 - 3, y1 - 3, fill=self.COLORS["goal"],
                                 outline=self.COLORS["goal_ring"], width=2)

        self.robot_shape = None

    _HEADING_ANGLE = {"N": 90, "E": 0, "S": -90, "W": 180}

    def _draw_robot(self, x: int, y: int, heading: str, collided: bool):
        if self.robot_shape:
            self.canvas.delete(self.robot_shape)
        x0, y0, x1, y1 = self._cell_bbox(x, y)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        r = self.CELL * 0.38
        import math

        angle = math.radians(self._HEADING_ANGLE[heading])
        tip = (cx + r * math.cos(angle), cy - r * math.sin(angle))
        left = (cx + r * math.cos(angle + 2.5), cy - r * math.sin(angle + 2.5))
        right = (cx + r * math.cos(angle - 2.5), cy - r * math.sin(angle - 2.5))
        color = self.COLORS["collision"] if collided else self.COLORS["robot"]
        self.robot_shape = self.canvas.create_polygon(
            *tip, *left, *right, fill=color, outline="black"
        )

    def _render_frame(self):
        if not self.result or not self.result.replay:
            return
        frame = self.result.replay[self.frame_index]
        self._draw_robot(frame.x, frame.y, frame.heading, frame.collided)
        self.tick_var.set(f"tick {self.frame_index + 1}/{len(self.result.replay)}")

        action = frame.action if frame.action else "(end of run)"
        self.info_var.set(f"position: ({frame.x}, {frame.y})\nheading: {frame.heading}\naction: {action}")

        s = frame.sensors
        self.sensor_var.set(
            f"dist  front={s['dist_front']}  left={s['dist_left']}  right={s['dist_right']}\n"
            f"rpm   L={s['rpm_left']:>4}  R={s['rpm_right']:>4}\n"
            f"accel fwd={s['accel_fwd']:+.1f}  lat={s['accel_lat']:+.1f}\n"
            f"at_goal={s['at_goal']}"
        )

    # -------------------------------------------------------------- playback

    def _set_playback_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.step_back_btn.configure(state=state)
        self.step_fwd_btn.configure(state=state)
        self.play_btn.configure(state=state)

    def _step_forward(self):
        if not self.result or not self.result.replay:
            return
        if self.frame_index < len(self.result.replay) - 1:
            self.frame_index += 1
            self._render_frame()
        else:
            self._pause()

    def _step_back(self):
        if not self.result or not self.result.replay:
            return
        if self.frame_index > 0:
            self.frame_index -= 1
            self._render_frame()

    def _toggle_play(self):
        if self.playing:
            self._pause()
        else:
            self._play()

    def _play(self):
        self.playing = True
        self.play_btn.configure(text="Pause")
        self._tick_playback()

    def _pause(self):
        self.playing = False
        self.play_btn.configure(text="Play")
        if self.play_job:
            self.root.after_cancel(self.play_job)
            self.play_job = None

    def _tick_playback(self):
        if not self.playing:
            return
        if not self.result or self.frame_index >= len(self.result.replay) - 1:
            self._pause()
            return
        self.frame_index += 1
        self._render_frame()
        delay_ms = int(1000 / max(1.0, self.speed_var.get()))
        self.play_job = self.root.after(delay_ms, self._tick_playback)

    # -------------------------------------------------------------- problem box

    def _clear_problem(self):
        self.problem_text.configure(state="normal")
        self.problem_text.delete("1.0", "end")
        self.problem_text.configure(state="disabled")

    def _show_problem(self, message: str):
        self.problem_text.configure(state="normal")
        self.problem_text.delete("1.0", "end")
        self.problem_text.insert("1.0", message)
        self.problem_text.configure(state="disabled")


def main():
    robot_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / "robot.py"
    if not robot_path.is_file():
        print(f"Can't find {robot_path}")
        print("Usage: python play.py [robot.py] [maze.txt]")
        raise SystemExit(1)

    initial_maze = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
    maze_dir = HERE / "mazes"

    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    App(root, robot_path, maze_dir, initial_maze)
    root.mainloop()


if __name__ == "__main__":
    main()
