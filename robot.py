"""
Azisly Hackathon -- Round 2 submission template.

One file, Python 3,
standard library only.

You edit ONE function: decide(). Everything below the DO NOT EDIT line handles talking
to the grader for you -- you never have to think about processes or JSON.

Read CONTRACT.md first. It is short and it is the whole ruleset.
"""

import json
import sys

def decide(sensors, memory):
    """Choose one action using only live sensors and persistent memory."""

    steps = [(0, -1), (1, 0), (0, 1), (-1, 0)]

    if "position" not in memory:
        memory["position"] = (0, 0)
        memory["heading"] = 0
        memory["edges"] = {}
        memory["crossings"] = {}

    if sensors.get("at_goal"):
        return "wait"

    left_rpm = sensors["rpm_left"]
    right_rpm = sensors["rpm_right"]

    if left_rpm > 80 and right_rpm > 80:
        old = memory["position"]
        heading = memory["heading"]
        dx, dy = steps[heading]
        new = (old[0] + dx, old[1] + dy)
        edge = tuple(sorted((old, new)))

        memory["position"] = new
        memory["crossings"][edge] = memory["crossings"].get(edge, 0) + 1
        memory["edges"][edge] = max(4, memory["edges"].get(edge, 0) + 4)

    elif left_rpm < -30 and right_rpm > 30:
        memory["heading"] = (memory["heading"] - 1) % 4

    elif left_rpm > 30 and right_rpm < -30:
        memory["heading"] = (memory["heading"] + 1) % 4

    x, y = memory["position"]
    heading = memory["heading"]

    if sensors["accel_fwd"] <= -1.5:
        dx, dy = steps[heading]
        neighbour = (x + dx, y + dy)
        edge = tuple(sorted(((x, y), neighbour)))
        memory["edges"][edge] = min(-4, memory["edges"].get(edge, 0) - 4)

    observations = [
        (heading, sensors["dist_front"]),
        ((heading - 1) % 4, sensors["dist_left"]),
        ((heading + 1) % 4, sensors["dist_right"]),
    ]

    for direction, distance in observations:
        dx, dy = steps[direction]
        neighbour = (x + dx, y + dy)
        edge = tuple(sorted(((x, y), neighbour)))

        if distance == 0:
            memory["edges"][edge] = memory["edges"].get(edge, 0) - 1
        else:
            memory["edges"][edge] = memory["edges"].get(edge, 0) + 1

    def move_towards(direction, inspect_only=False):
        difference = (direction - memory["heading"]) % 4

        if difference == 0:
            return "wait" if inspect_only else "forward"
        if difference == 1:
            return "turn_right"
        if difference == 3:
            return "turn_left"
        return "turn_right"

    def turn_cost(direction):
        difference = (direction - heading) % 4
        if difference == 0:
            return 0
        if difference == 2:
            return 2
        return 1

    # The long-distance readings are useful when choosing between
    # new directions. A clamped value still means "at least this open."
    visible_distance = {
        heading: sensors["dist_front"],
        (heading - 1) % 4: sensors["dist_left"],
        (heading + 1) % 4: sensors["dist_right"],
    }

    priority = [
        (heading + 1) % 4,
        heading,
        (heading - 1) % 4,
        (heading + 2) % 4,
    ]

    # Prefer untraveled open passages with the longest visible corridor.
    candidates = []

    for order, direction in enumerate(priority):
        dx, dy = steps[direction]
        neighbour = (x + dx, y + dy)
        edge = tuple(sorted(((x, y), neighbour)))
        evidence = memory["edges"].get(edge, 0)
        crossings = memory["crossings"].get(edge, 0)

        if evidence > 0 and crossings == 0:
            corridor = visible_distance.get(direction, 0)
            candidates.append(
                (corridor, -turn_cost(direction), -order, direction)
            )

    if candidates:
        best_direction = max(candidates)[3]
        return move_towards(best_direction)

    # Inspect unseen boundaries before backtracking.
    for direction in priority:
        dx, dy = steps[direction]
        neighbour = (x + dx, y + dy)
        edge = tuple(sorted(((x, y), neighbour)))

        if edge not in memory["edges"]:
            return move_towards(direction, inspect_only=True)

    # Recheck weak sensor evidence once.
    for direction in priority:
        dx, dy = steps[direction]
        neighbour = (x + dx, y + dy)
        edge = tuple(sorted(((x, y), neighbour)))
        evidence = memory["edges"].get(edge, 0)
        crossings = memory["crossings"].get(edge, 0)

        if crossings == 0 and -2 < evidence <= 0:
            return move_towards(direction, inspect_only=True)

    # Backtrack through a known-open passage. Earlier versions of this
    # required crossings == 1 exactly, which meant any edge crossed twice
    # (common at hub cells / loops) became permanently unusable in every
    # branch above -- the robot would fall through to "wait" forever and
    # never reach the goal. Instead, always retreat via whichever known-open
    # edge has been used the least, so there is always a valid escape as
    # long as any open passage from this cell exists.
    fallback_candidates = []
    for direction in priority:
        dx, dy = steps[direction]
        neighbour = (x + dx, y + dy)
        edge = tuple(sorted(((x, y), neighbour)))
        evidence = memory["edges"].get(edge, 0)
        crossings = memory["crossings"].get(edge, 0)

        if evidence > 0:
            fallback_candidates.append((crossings, direction))

    if fallback_candidates:
        fallback_candidates.sort(key=lambda c: c[0])
        return move_towards(fallback_candidates[0][1])

    return "wait"
# =============================================================================
# DO NOT EDIT BELOW THIS LINE
# This is the plumbing that talks to the grader. Changing it will break your
# submission and score you zero.
# =============================================================================

def _main():
    print(json.dumps({"ready": True}), flush=True)
    memory = {}
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        sensors = json.loads(line)
        action = decide(sensors, memory)
        print(json.dumps({"action": action}), flush=True)
        if sensors.get("at_goal"):
            break

if __name__ == "__main__":
    _main()