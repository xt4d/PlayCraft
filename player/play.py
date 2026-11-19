#!/usr/bin/env python3
"""Run the agent player with configurable observation and action timing."""

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from actions import action_plan_schema, controls, expand_actions
from checkpoints import Checkpoints, load_settings, write_json
from codex import Codex, Pipe, object_schema

HERE = Path(__file__).resolve().parent
DEFAULT_EFFORTS = {"start": "medium", "play": "medium", "review": "xhigh"}


REVIEW_SCHEMA = object_schema({
    "final_result": {"type": ["string", "null"]},
    "review": {"type": "string"},
    "lessons": {"type": "array", "items": {"type": "string"}},
})


def model_memory(history):
    """Supply brief outcomes and the latest completed review's full lesson set."""
    episodes = [{key: episode[key] for key in ("episode", "elapsed_ms", "result", "stop")}
                for episode in history]
    latest = next((episode for episode in reversed(history) if episode["stop"] != "error"), None)
    return {"episodes": episodes, "lessons": list(latest["lessons"]) if latest else []}


def episode_journal(directory):
    """Supply the existing chronological notes directly to the review call."""
    path = directory / "journal.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class AgentPlayer:
    name = "agent"
    prompt_directory = HERE / "prompts"

    def __init__(self, args):
        self.args = args
        target = str(args.game)
        self.url = target if target.startswith(("http://", "https://")) else None
        self.game = None if self.url else Path(target).resolve()
        if getattr(args, "resume", None):
            self.output = args.resume.resolve()
        elif args.output:
            self.output = args.output.resolve()
        else:
            self.output = (self.game or Path.cwd()) / "logs/agent-player" / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        self.workspace = self.output / "player"
        self.checkpoints = Checkpoints(self.output)
        self.memory = []
        self.first_episode = 1
        self.turns = 0
        self.action_schema = action_plan_schema(
            args.width, args.height, math.ceil(args.model_interval / args.action_interval)
        )

    def log(self, event, **fields):
        self.events.write(json.dumps({"event": event, **fields}, allow_nan=False) + "\n")
        self.events.flush()

    def capture(self):
        image = self.bridge.call("render", {})
        frame = {"path": image["frame"], "elapsed_ms": self.elapsed_ms,
                 "pointer_locked": image["pointer_locked"]}
        self.frames.append(frame)
        self.log("frame", episode=self.episode, **frame)

    def _context(self, stage, reason):
        frames = self.frames[self.observation_start:]
        return {"stage": stage, "reason": reason, "episode": self.episode,
                "model_interval_ms": self.args.model_interval,
                "observation_interval_ms": self.args.observation_interval,
                "action_interval_ms": self.args.action_interval,
                "elapsed_ms": self.elapsed_ms,
                "pointer_locked": frames[-1]["pointer_locked"],
                "width": self.args.width, "height": self.args.height,
                "prior_episodes": len(self.memory),
                "prior_play_ms": sum(r["elapsed_ms"] for r in self.memory),
                "episode_directory": self.episode_directory.name, "frames": frames}

    def _request(self, context, schema, prompt=None, attempt=1):
        if prompt is None:
            prompt = (self.prompt_directory / f"{context['stage']}.md").read_text(encoding="utf-8")
        effort = getattr(self.args, f"{context['stage']}_effort")
        self.log("model_request", attempt=attempt, effort=effort, **context)
        self.turns += 1
        response, turn_id = self.model.ask(prompt, context, context["frames"], schema, effort=effort)
        if not isinstance(response, dict) or set(response) != set(schema["properties"]):
            raise ValueError(f"{context['stage']} response must contain exactly: {', '.join(schema['properties'])}")
        return response, turn_id

    def _record_decision(self, context, decision, turn_id, journal_fields):
        self.log("model_decision", episode=self.episode, elapsed_ms=self.elapsed_ms, stage=context["stage"],
                 turn_id=turn_id, images=[f["path"] for f in context["frames"]], decision=decision)
        with (self.episode_directory / "journal.jsonl").open("a", encoding="utf-8") as journal:
            journal.write(json.dumps({"elapsed_ms": self.elapsed_ms, "stage": context["stage"],
                                      **journal_fields}) + "\n")

    def ask_actions(self, stage, reason=""):
        """Choose and validate the next start/play action plan."""
        if stage not in ("start", "play"):
            raise ValueError("ask_actions requires start or play")
        plan_ms = min(self.args.model_interval, self.args.duration - self.elapsed_ms)
        action_count = math.ceil(plan_ms / self.args.action_interval)
        context = {**self._context(stage, reason),
                   "action_count": action_count, "action_duration_ms": plan_ms}
        if stage == "start":
            context["memory"] = model_memory(self.memory)
        prompt = (self.prompt_directory / f"{stage}.md").read_text(encoding="utf-8")
        for attempt in range(2):
            decision, turn_id = self._request(context, self.action_schema, prompt, attempt + 1)
            if decision["phase"] not in ("playing", "ended"):
                raise ValueError("invalid model phase")
            if decision["result"] is not None and not isinstance(decision["result"], str):
                raise ValueError("result must be a description string or null")
            if not isinstance(decision["note"], str):
                raise ValueError("note must be a string")
            if decision["phase"] == "ended" and (decision["end_confidence"] < 0.9 or not decision["note"].strip()):
                raise ValueError("ending requires confident visible evidence in the model's note")
            count = 0 if decision["phase"] == "ended" else action_count
            try:
                actions = expand_actions(decision["actions"], count)
            except ValueError as failure:
                error = "agent player " + str(failure)
                self.log("model_rejected", episode=self.episode, elapsed_ms=self.elapsed_ms, stage=stage,
                         turn_id=turn_id, error=error, decision=decision)
                if attempt == 1:
                    raise ValueError(error + " after one retry")
                prompt += (f"\n\nCorrection: {error}. Your previous actions were not executed. "
                           f"The game is still paused at {context['elapsed_ms']} ms; use the same screenshots. "
                           f"Return a complete corrected response with exactly {action_count} action states "
                           "after expanding repeat counts, or actions=[] with phase=ended and confident visible end evidence.")
                continue
            break
        self.game_result, self.result_frame = decision["result"], context["frames"][-1]["path"]
        self._record_decision(context, decision, turn_id, {"result": decision["result"], "note": decision["note"]})
        return {**decision, "actions": actions}

    def ask_review(self, stop):
        """Assess the final outcome, review the episode, and consolidate lessons."""
        context = {**self._context("review", stop), "memory": model_memory(self.memory),
                   "journal": episode_journal(self.episode_directory)}
        response, turn_id = self._request(context, REVIEW_SCHEMA)
        if response["final_result"] is not None and not isinstance(response["final_result"], str):
            raise ValueError("final_result must be a description string or null")
        if not isinstance(response["review"], str):
            raise ValueError("review must be a string")
        if not isinstance(response["lessons"], list) or any(not isinstance(lesson, str) for lesson in response["lessons"]):
            raise ValueError("lessons must be a list of strings")
        self.review_turn_id = turn_id
        self.game_result, self.result_frame = response["final_result"], context["frames"][-1]["path"]
        self._record_decision(context, response, turn_id, {"final_result": response["final_result"], "review": response["review"]})
        return response

    def step(self, command, milliseconds):
        actions = controls([command])
        self.bridge.call("step", {"actions": actions, "action_interval_ms": milliseconds}, timeout=30000)
        self.log("action", episode=self.episode, elapsed_ms=self.elapsed_ms,
                 duration_ms=milliseconds, actions=actions, source="model",
                 result=self.game_result, result_frame=self.result_frame)
        self.elapsed_ms += milliseconds

    def play(self):
        cutoff_ms = self.args.duration
        next_observation = self.args.observation_interval
        while self.elapsed_ms < cutoff_ms:
            first = self.elapsed_ms == 0
            decision = self.ask_actions("start" if first else "play",
                                        "first frame" if first else "action plan completed")
            if decision["phase"] == "ended":
                return "ended"
            self.observation_start = len(self.frames)
            plan_start = self.elapsed_ms
            plan_end = min(plan_start + self.args.model_interval, cutoff_ms)
            for index, command in enumerate(decision["actions"]):
                action_end = min(plan_start + (index + 1) * self.args.action_interval, plan_end)
                while self.elapsed_ms < action_end:
                    # Capture between action changes without releasing the held state.
                    until = min(action_end, next_observation)
                    self.step(command, until - self.elapsed_ms)
                    # Move once per action; captures only split the held keys/buttons.
                    command = {**command, "x": None, "y": None, "dx": None, "dy": None}
                    if self.elapsed_ms == next_observation:
                        self.capture()
                        next_observation += self.args.observation_interval
            if self.frames[-1]["elapsed_ms"] != self.elapsed_ms:
                self.capture()  # every decision needs the current screen
        return "limit"

    def play_episode(self, episode):
        self.episode, self.elapsed_ms = episode, 0
        self.frames = []
        self.observation_start = 0
        self.game_result, self.result_frame = None, None
        calls_before = self.turns
        started = time.monotonic()
        self.episode_directory = self.workspace / f"e{episode:03d}"
        self.frame_directory = self.episode_directory / "frames"
        self.frame_directory.mkdir(parents=True)
        self.bridge = Pipe([sys.executable, "-B", str(HERE / "browser_bridge.py")], self.workspace,
                           self.output / "bridge-stderr.log")
        stop, review, lessons, error = "limit", "", [], None
        try:
            self.bridge.call("open", {"url": self.url, "root": str(self.game) if self.game else None,
                "directory": str(self.frame_directory),
                "width": self.args.width, "height": self.args.height})
            self.capture()
            stop = self.play()

            response = self.ask_review(stop)
            review, lessons = response["review"], response["lessons"]
            (self.episode_directory / "review.md").write_text(review + "\n", encoding="utf-8")
        except Exception as failure:
            stop, error = "error", str(failure)
        finally:
            try:
                self.bridge.call("close", {}, timeout=10000)
            except Exception as failure:
                stop, error = "error", error or str(failure)
            self.bridge.close()
        result = {"episode": episode, "elapsed_ms": self.elapsed_ms, "result": self.game_result,
                  "result_frame": self.result_frame, "stop": stop, "error": error, "review": review,
                  "lessons": lessons,
                  "player": self.name,
                  "model_turns": self.turns - calls_before, "frames": len(self.frames),
                  "wall_ms": round((time.monotonic() - started) * 1000)}
        self.log("episode", **result)
        return result

    def run(self):
        if self.game and not (self.game / "index.html").is_file():
            raise ValueError("local game needs index.html; use a URL for a dev server")
        with self.checkpoints.lock(bool(getattr(self.args, "resume", None))):
            status = self._run()
            if status == 0:
                (self.output / "done").touch()
            return status

    def compact_before_episode(self, episode):
        started = time.monotonic()
        self.log("compaction_start", before_episode=episode)
        try:
            turn_id = self.model.compact()
        except BaseException as error:
            self.log("compaction_failed", before_episode=episode, error=str(error),
                     duration_ms=round((time.monotonic() - started) * 1000))
            raise
        self.log("compaction_completed", before_episode=episode, turn_id=turn_id,
                 duration_ms=round((time.monotonic() - started) * 1000))

    def _run(self):
        resuming = bool(getattr(self.args, "resume", None))
        checkpoint = None
        if resuming:
            settings = load_settings(self.output)
            if settings["game"] != (self.url or str(self.game)):
                raise ValueError("resume must use the original game")
            checkpoint = self.checkpoints.load(getattr(self.args, "from_episode", None))
            self.first_episode = checkpoint["episode"] + 1
            self.memory = checkpoint["memory"]
            if self.first_episode > self.args.episodes:
                print("All requested episodes are already checkpointed; increase --episodes to continue.")
                return 0
        if resuming:
            (self.output / "done").unlink(missing_ok=True)
            self.checkpoints.restore(checkpoint)
        instruction_file = self.args.instructions
        if instruction_file is None and self.game:
            candidate = self.game / "instruction.md"
            if candidate.is_file():
                instruction_file = candidate
        if resuming and self.args.instructions is None:
            instruction = (self.workspace / "instruction.md").read_text(encoding="utf-8")
        else:
            instruction = (instruction_file.read_text(encoding="utf-8") if instruction_file else
                           "No external instructions supplied. Infer goals and controls from the visible game.")
        self.workspace.mkdir(parents=True, exist_ok=resuming)
        (self.workspace / "instruction.md").write_text(instruction)
        self.events = (self.output / "events.jsonl").open("a", encoding="utf-8")
        self.model = None
        self.checkpoints.settings(self.args, self.url or str(self.game))
        self.log("run", game=self.url or str(self.game), episodes=self.args.episodes, duration_ms=self.args.duration,
                 player=self.name, model=self.args.model,
                 compact_between_episodes=self.args.compact_between_episodes,
                 start_effort=self.args.start_effort, play_effort=self.args.play_effort,
                 review_effort=self.args.review_effort,
                 model_interval_ms=self.args.model_interval,
                 observation_interval_ms=self.args.observation_interval, action_interval_ms=self.args.action_interval,
                 width=self.args.width, height=self.args.height,
                 instructions=str(instruction_file) if instruction_file else None)
        try:
            shared = (self.prompt_directory / "common.md").read_text(encoding="utf-8")
            self.model = Codex(self.workspace, shared + "\n\nGame instructions:\n" + instruction,
                               model=self.args.model, http=self.args.chatgpt_http, timeout=self.args.model_timeout,
                               home=self.workspace / ".codex-home",
                               fork_from=checkpoint if checkpoint and checkpoint["turn_id"] else None)
            if not resuming:
                self.checkpoints.save(0, self.model, None, [])
            else:
                self.log("resume", episode=self.first_episode, checkpoint_episode=checkpoint["episode"],
                         source_thread_id=checkpoint["thread_id"], thread_id=self.model.thread_id,
                         turn_id=checkpoint["turn_id"])
            for episode in range(self.first_episode, self.args.episodes + 1):
                if self.args.compact_between_episodes and episode > 1:
                    self.compact_before_episode(episode)
                result = self.play_episode(episode)
                self.memory.append(result)
                write_json(self.workspace / "memory.json", self.memory)
                if not result["error"]:
                    self.checkpoints.save(episode, self.model, self.review_turn_id, self.memory)
                print(f"episode {episode}: {result['stop']}, {result['elapsed_ms']}ms, result={json.dumps(result['result'], ensure_ascii=False)}", flush=True)
                if result["error"]:
                    break
            return 1 if self.memory[-1]["error"] else 0
        finally:
            if self.model:
                self.model.close()
            self.events.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", nargs="?", help="HTTP(S) URL or local folder containing index.html")
    parser.add_argument("--resume", type=Path, help="existing run directory to resume")
    parser.add_argument("--from-episode", type=int, help="restart this episode from its preceding checkpoint")
    parser.add_argument("--instructions", type=Path, help="instruction file (default: GAME/instruction.md when present)")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--width", type=int, default=960, help="screenshot width in pixels (default: 960)")
    parser.add_argument("--height", type=int, default=960, help="screenshot height in pixels (default: 960)")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--compact-between-episodes", action=argparse.BooleanOptionalAction, default=False,
                        help="compact the conversation before E2 onward, including resume (default: disabled)")
    parser.add_argument("--duration", type=int, default=60000, help="active milliseconds per episode (default: 60000)")
    parser.add_argument("--model")
    efforts = ["low", "medium", "high", "xhigh", "max", "ultra"]
    for stage, default in DEFAULT_EFFORTS.items():
        parser.add_argument(f"--{stage}-effort", choices=efforts, default=default,
                            help=f"thinking effort for {stage} (default: {default})")
    parser.add_argument("--model-interval", type=int, default=500,
                        help="milliseconds per model action plan (default: 500)")
    parser.add_argument("--observation-interval", type=int, default=100,
                        help="milliseconds between screenshots (default: 100)")
    parser.add_argument("--action-interval", type=int, default=20,
                        help="milliseconds per held action state (default: 20)")
    parser.add_argument("--model-timeout", type=int, default=180000,
                        help="milliseconds allowed per model attempt (default: 180000)")
    parser.add_argument("--chatgpt-http", action="store_true", help="ChatGPT authentication with HTTP transport")
    preliminary, _ = parser.parse_known_args()
    if preliminary.resume:
        try:
            parser.set_defaults(**load_settings(preliminary.resume))
        except (OSError, ValueError, KeyError) as error:
            parser.error(str(error))
    args = parser.parse_args()
    if not args.game:
        parser.error("game is required unless --resume is supplied")
    if args.from_episode is not None and (not args.resume or not 1 <= args.from_episode <= args.episodes):
        parser.error("--from-episode requires --resume and must be between 1 and --episodes")
    if args.resume and args.output:
        parser.error("--resume reuses its run directory; omit --output")
    if args.width < 1 or args.height < 1:
        parser.error("--width and --height must be positive integers")
    if min(args.episodes, args.duration, args.model_interval, args.observation_interval,
           args.action_interval, args.model_timeout) < 1:
        parser.error("episodes and all time settings must be positive integers; times are in milliseconds")
    try:
        return AgentPlayer(args).run()
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f"agent-player: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
