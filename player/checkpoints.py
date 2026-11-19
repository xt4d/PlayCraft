"""Episode-boundary conversation and workspace snapshots."""

import fcntl
import json
import os
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_settings(output):
    path = output.resolve() / "run.json"
    if not path.is_file():
        raise ValueError("resume requires a run with saved settings and episode checkpoints")
    settings = json.loads(path.read_text(encoding="utf-8"))
    if settings.get("chrome_path"):
        os.environ.setdefault("CHROME_PATH", settings["chrome_path"])
    return settings["args"]


def is_episode(path):
    return path.name.startswith("e") and path.name[1:].isdigit()


class Checkpoints:
    def __init__(self, output):
        self.output = output
        self.workspace = output / "player"
        self.directory = output / "checkpoints"

    @contextmanager
    def lock(self, resuming):
        if resuming and not self.output.is_dir():
            raise ValueError("resume directory does not exist")
        try:
            self.output.mkdir(parents=True, exist_ok=resuming)
        except FileExistsError:
            raise ValueError("output exists; choose a new run directory") from None
        with (self.output / ".lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("this run is already running; stop it before resuming") from None
            yield

    def settings(self, args, game):
        options = {key: str(value) if isinstance(value, Path) else value
                   for key, value in vars(args).items()
                   if key not in ("output", "resume", "from_episode", "instructions")}
        options["game"] = game
        write_json(self.output / "run.json", {"args": options,
                                              "chrome_path": os.environ.get("CHROME_PATH")})

    def save(self, episode, model, turn_id, memory):
        self.directory.mkdir(exist_ok=True)
        destination = self.directory / f"e{episode:03d}"
        temporary = self.directory / f".e{episode:03d}.tmp"
        if temporary.exists():
            shutil.rmtree(temporary)
        files = temporary / "files"
        files.mkdir(parents=True)
        for path in self.workspace.iterdir():
            if is_episode(path) or path.name in (".codex-home", ".tmp", "__pycache__", "memory.json"):
                continue
            self.copy(path, files / path.name)
        write_json(temporary / "checkpoint.json", {"episode": episode, "thread_id": model.thread_id,
                   "turn_id": turn_id, "memory": memory})
        temporary.replace(destination)

    def load(self, episode=None):
        if not (self.workspace / ".codex-home").is_dir():
            raise ValueError("the run's persistent Codex home is missing")
        saved = sorted(path for path in self.directory.glob("e*") if is_episode(path))
        if not saved:
            raise ValueError("no completed episode checkpoint exists")
        last = max(int(path.name[1:]) for path in saved)
        episode = last + 1 if episode is None else episode
        boundary = self.directory / f"e{episode - 1:03d}"
        if episode < 1 or not (boundary / "checkpoint.json").is_file():
            raise ValueError(f"no checkpoint exists before episode {episode}")
        checkpoint = json.loads((boundary / "checkpoint.json").read_text(encoding="utf-8"))
        return checkpoint

    def restore(self, checkpoint):
        episode = checkpoint["episode"] + 1
        boundary = self.directory / f"e{episode - 1:03d}"
        archive = self.output / "attempts" / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        archive.mkdir(parents=True)
        # Retain the private Codex store and completed frames at their original paths.
        for path in self.workspace.iterdir():
            if path.name == ".codex-home" or (is_episode(path) and int(path.name[1:]) < episode):
                continue
            target = archive / "player" / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            path.rename(target)
        for path in self.directory.glob("e*"):
            if is_episode(path) and int(path.name[1:]) >= episode:
                target = archive / "checkpoints" / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                path.rename(target)
        for path in (boundary / "files").iterdir():
            self.copy(path, self.workspace / path.name)
        write_json(self.workspace / "memory.json", checkpoint["memory"])

    @staticmethod
    def copy(source, destination):
        if source.is_dir():
            shutil.copytree(source, destination, symlinks=True)
        else:
            shutil.copy2(source, destination, follow_symlinks=False)
