"""Action plans, keyboard and mouse validation, and browser input conversion."""

import math

from codex import object_schema


SUPPORTED_KEYS = (
    [f"Key{letter}" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    + [f"Digit{digit}" for digit in range(10)]
    + ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
       "Space", "Enter", "Escape", "Tab", "Backspace"]
    + [f"{modifier}{side}" for modifier in ("Shift", "Control", "Alt", "Meta")
       for side in ("Left", "Right")]
)
SUPPORTED_BUTTONS = ["left", "right", "middle"]


def action_plan_schema(width, height, max_actions):
    """Build the start/play response schema for the current viewport and plan size."""
    action = object_schema({
        "repeat": {"type": "integer", "minimum": 1},
        "keys": {"type": "array", "items": {"type": "string", "enum": SUPPORTED_KEYS}},
        "buttons": {"type": "array", "items": {"type": "string", "enum": SUPPORTED_BUTTONS}},
        "x": {"type": ["number", "null"], "minimum": 0, "exclusiveMaximum": width},
        "y": {"type": ["number", "null"], "minimum": 0, "exclusiveMaximum": height},
        "dx": {"type": ["number", "null"]},
        "dy": {"type": ["number", "null"]},
    })
    return object_schema({
        "phase": {"type": "string", "enum": ["playing", "ended"]},
        "actions": {"type": "array", "items": action, "maxItems": max_actions},
        "result": {"type": ["string", "null"]},
        "end_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "note": {"type": "string"},
    })


def controls(commands):
    """Validate held keys/buttons, absolute positions, and one-time relative movement."""
    if not isinstance(commands, list):
        raise ValueError("actions must be a list")
    actions = []
    for command in commands:
        if not isinstance(command, dict):
            raise ValueError("each action must be an object")
        keys, buttons = command.get("keys", []), command.get("buttons", [])
        if not isinstance(keys, list) or any(not isinstance(key, str) or key not in SUPPORTED_KEYS for key in keys):
            raise ValueError("use KeyboardEvent.code names for keys")
        if not isinstance(buttons, list) or any(button not in SUPPORTED_BUTTONS for button in buttons):
            raise ValueError("invalid mouse buttons")
        mouse = {"buttons": buttons}
        for axis in ("x", "y", "dx", "dy"):
            value = command.get(axis)
            if value is not None:
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value) or (axis in ("x", "y") and value < 0)):
                    raise ValueError("invalid pointer coordinate or movement")
                mouse[axis] = value
        if any(axis in mouse for axis in ("x", "y")) and any(axis in mouse for axis in ("dx", "dy")):
            raise ValueError("use either x/y or dx/dy in an action, not both")
        actions.append({"keys": keys, "mouse": mouse})
    return actions


def expand_actions(commands, count):
    """Expand model repeats into held states, checking the total before allocation."""
    if not isinstance(commands, list) or any(not isinstance(c, dict) for c in commands):
        raise ValueError("actions must be a list of objects")
    repeats = [command.get("repeat", 1) for command in commands]
    if any(type(repeat) is not int or repeat < 1 for repeat in repeats):
        raise ValueError("action repeat must be a positive integer")
    total = sum(repeats)
    if total != count:
        raise ValueError(f"requires {count} action states; received {total}")
    return [{key: value for key, value in command.items() if key != "repeat"}
            for command, repeat in zip(commands, repeats) for _ in range(repeat)]
