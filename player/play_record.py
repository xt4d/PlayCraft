#!/usr/bin/env python3
"""Export a play record from a saved player run."""

import argparse
import json
import math
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from checkpoints import Checkpoints, load_settings


def write_play_record(workspace, args, episodes, output_directory):
    """Write play.md and its linked files to the requested directory."""
    workspace = Path(workspace)
    destination = Path(output_directory)
    interval = args.model_interval
    observation, action = args.observation_interval, args.action_interval
    frame_window = (f"then {interval // observation} frames from the preceding action sequence" if interval % observation == 0
                    else "then periodic frames and the final frame from the preceding action sequence")
    setup = [
        f"- Episodes attempted: {len(episodes)} of {args.episodes}; active time limit: {args.duration} ms per episode.",
        f"- Frame dimensions: {args.width} × {args.height} pixels.",
        f"- Frame capture frequency: {1000 / observation:g} Hz (every {observation} ms of active game time).",
        f"- Input application frequency: {1000 / action:g} Hz (one held input state every {action} ms).",
        f"- Model call frequency: {1000 / interval:g} Hz (one model call every {interval} ms).",
        f"- Frames per model call: one initial frame, {frame_window}.",
        f"- Actions per model call: {math.ceil(interval / action)} action states, covering {interval} ms.",
    ]
    sections = ["# Play", "## Setup", "\n".join(setup), "## Episodes"]
    destination.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".play-record-", dir=destination) as temporary:
        staging = Path(temporary)
        references = staging / "ref"
        references.mkdir()
        for episode in episodes:
            number = episode["episode"]
            directory = workspace / f"e{number:03d}"
            review = directory / "review.md"
            error = episode["error"]
            content = review.read_text(encoding="utf-8") if review.is_file() else (
                f"Review unavailable. Episode error: {error}" if error else "Review unavailable.")
            sections.append(f"### E-{number}\n\n{content}".rstrip())

            journal = directory / "journal.jsonl"
            if journal.is_file():
                name = f"journal_{number:03d}.jsonl"
                shutil.copyfile(journal, references / name)
                sections.append(f"[Journal](ref/{name}) — Timestamped play notes from this episode.")
            elif not error:
                raise FileNotFoundError(f"Missing episode journal: {journal}")

            name = f"lessons_{number:03d}.jsonl"
            lessons = "".join(json.dumps(lesson, ensure_ascii=False) + "\n" for lesson in episode["lessons"])
            (references / name).write_text(lessons, encoding="utf-8")
            sections.append(f"[Lessons](ref/{name}) — Lessons updated through this episode.")

        report = staging / "play.md"
        report.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
        reference_destination = destination / "ref"
        reference_destination.mkdir(exist_ok=True)
        for reference in references.iterdir():
            reference.replace(reference_destination / reference.name)
        report.replace(destination / report.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path, help="run directory containing run.json and player/")
    parser.add_argument("output_directory", type=Path, help="destination for play.md and its linked files")
    args = parser.parse_args()
    run = Checkpoints(args.run_directory)
    try:
        with run.lock(resuming=True):
            settings = argparse.Namespace(**load_settings(run.output))
            episodes = json.loads((run.workspace / "memory.json").read_text(encoding="utf-8"))
            write_play_record(run.workspace, settings, episodes, args.output_directory)
    except (OSError, ValueError, KeyError, AttributeError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(f"Exported {len(episodes)} episodes to {args.output_directory / 'play.md'}")


if __name__ == "__main__":
    main()
