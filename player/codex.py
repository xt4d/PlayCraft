"""One persistent Codex app-server conversation, using native tools."""

import json
import os
import queue
import random
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

from native_sandbox import prepare_home


def object_schema(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


class Pipe:
    """JSONL transport; timeout values and receive deadlines are milliseconds."""

    def __init__(self, command, cwd, stderr, log=lambda message: None, env=None):
        self.stderr = open(stderr, "a", encoding="utf-8")
        try:
            self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self.stderr, text=True, bufsize=1, env=env,
                start_new_session=True)
        except Exception:
            self.stderr.close()
            raise
        self.log = log
        self.inbox = queue.Queue()
        self.events = deque()
        self.counter = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.process.stdout:
            self.inbox.put(line)
        self.inbox.put(None)

    def send(self, message):
        self.process.stdin.write(json.dumps(message, allow_nan=False) + "\n")
        self.process.stdin.flush()

    def receive(self, deadline_ms):
        remaining_ms = deadline_ms - time.monotonic() * 1000
        if remaining_ms <= 0:
            raise TimeoutError("process timed out")
        try:
            line = self.inbox.get(timeout=remaining_ms / 1000)
        except queue.Empty as error:
            raise TimeoutError("process timed out") from error
        if line is None:
            raise RuntimeError("process exited; see its stderr log")
        message = json.loads(line)
        self.log(message)
        if "method" in message and "id" in message:
            method = message["method"]
            if method in ("item/commandExecution/requestApproval", "item/fileChange/requestApproval"):
                reply = {"result": {"decision": "decline"}}
            elif method == "item/tool/requestUserInput":
                reply = {"result": {"answers": {}}}
            else:
                reply = {"error": {"code": -32601, "message": "Unsupported client request"}}
            self.send({"id": message["id"], **reply})
        return message

    def call(self, method, params, timeout=60000):
        self.counter += 1
        self.send({"id": self.counter, "method": method, "params": params})
        deadline_ms = time.monotonic() * 1000 + timeout
        while True:
            message = self.receive(deadline_ms)
            if message.get("id") == self.counter and "method" not in message:
                if "error" in message:
                    raise RuntimeError(str(message["error"]))
                return message["result"]
            if "method" in message and "id" not in message:
                self.events.append(message)

    def close(self):
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        # The native sandbox launcher can exit while its controller still owns stdout.
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait()
        self.process.stdout.close()
        self.stderr.close()


class CapacityError(RuntimeError):
    """The selected model is temporarily overloaded."""


class Codex:
    """Persistent model conversation with a per-attempt timeout in milliseconds."""

    def __init__(self, workspace, instructions, model=None, http=False, timeout=180000,
                 *, home=None, fork_from=None):
        self.temporary_home = None if home else tempfile.TemporaryDirectory(
            prefix="agent-player-codex-", dir=workspace.resolve())
        self.home = Path(home) if home else Path(self.temporary_home.name)
        self.home.mkdir(exist_ok=True)
        self.rpc = self.events = None
        self.workspace = workspace.resolve()
        self.timeout = timeout
        try:
            self._start(workspace, instructions, model, http, fork_from)
        except BaseException:
            self.close()
            raise

    def _start(self, workspace, instructions, model, http, fork_from):
        home = self.home
        env = prepare_home(home, workspace, authenticate=True)
        stderr = workspace.parent / "codex-stderr.log"
        command = ["codex"]
        if http:
            settings = {"model_provider": '"agent_player_http"',
                "model_providers.agent_player_http": '{name="Agent player HTTP", '
                'base_url="https://chatgpt.com/backend-api/codex", wire_api="responses", '
                'requires_openai_auth=true, supports_websockets=false}'}
            for key, value in settings.items():
                command.extend(["-c", key + "=" + value])
        self.events = open(workspace.parent / "codex.jsonl", "a", encoding="utf-8")
        command += ["app-server", "--listen", "stdio://"]
        self.rpc = Pipe(command, workspace, stderr, self._log, env=env)
        self.rpc.call("initialize", {"clientInfo": {"name": "agent-player", "version": "0.3.0"},
                                    "capabilities": {"experimentalApi": True}})
        self.rpc.send({"method": "initialized", "params": {}})
        params = {"cwd": str(workspace), "approvalPolicy": "never", "permissions": "player",
                  "baseInstructions": instructions, "ephemeral": self.temporary_home is not None}
        if model:
            params["model"] = model
        method = "thread/start"
        if fork_from:
            method = "thread/fork"
            params.update(threadId=fork_from["thread_id"], lastTurnId=fork_from["turn_id"], excludeTurns=True)
        started = self.rpc.call(method, params)
        if started.get("instructionSources") or (started.get("activePermissionProfile") or {}).get("id") != "player":
            raise RuntimeError("Unexpected instruction sources or permission profile; refusing to play")
        self.thread_id = started["thread"]["id"]
        configured = self.rpc.call("config/read", {"cwd": str(workspace), "includeLayers": True})
        for layer in configured.get("layers") or []:
            name = layer.get("name", {})
            ours = name.get("type") == "sessionFlags" or (name.get("type") == "user" and
                   Path(name.get("file", "")).resolve() == (home / "config.toml").resolve())
            if layer.get("config") and not ours:
                raise RuntimeError("External configuration layer found; refusing a contaminated run")
        config = configured["config"]
        if config.get("mcp_servers") or config.get("developer_instructions"):
            raise RuntimeError("External MCP servers or developer instructions are not allowed in a clean run")

    def _log(self, message):
        self.events.write(json.dumps(message) + "\n")
        self.events.flush()

    def compact(self):
        """Compact this conversation and wait for its turn to finish successfully."""
        try:
            deadline_ms = time.monotonic() * 1000 + self.timeout
            self.rpc.call("thread/compact/start", {"threadId": self.thread_id}, self.timeout)
            turn_id, compacted = None, False
            while True:
                if time.monotonic() * 1000 >= deadline_ms:
                    raise TimeoutError("Codex compaction timed out")
                event = self.rpc.events.popleft() if self.rpc.events else self.rpc.receive(deadline_ms)
                p = event.get("params") or {}
                if p.get("threadId") != self.thread_id:
                    continue
                method = event.get("method")
                if method == "turn/started":
                    turn_id = p["turn"]["id"]
                elif method in ("item/started", "item/completed") and p["item"]["type"] == "contextCompaction":
                    turn_id = p["turnId"]
                    compacted = method == "item/completed"
                elif method == "error" and not p.get("willRetry", False):
                    raise RuntimeError("Codex compaction failed: " + str(p.get("error")))
                elif method == "turn/completed" and p["turn"]["id"] == turn_id:
                    turn = p["turn"]
                    if turn["status"] != "completed":
                        raise RuntimeError("Codex compaction failed: " + str(turn.get("error") or turn["status"]))
                    if not compacted:
                        raise RuntimeError("Codex turn finished without completing compaction")
                    return turn_id
        except BaseException:
            self.close()
            raise

    def ask(self, prompt, context, frames, schema, *, effort=None):
        if any(not Path(frame["path"]).resolve().is_relative_to(self.workspace) for frame in frames):
            raise ValueError("Model screenshots must be inside the player workspace")
        delay_ms, attempt = 5000, 0
        try:
            while True:
                try:
                    return self._ask(prompt, context, frames, schema, effort)
                except CapacityError as error:
                    attempt += 1
                    wait_ms = delay_ms + random.randint(0, 1000)
                    self._log({"event": "capacity_retry", "thread_id": self.thread_id,
                               "attempt": attempt, "delay_ms": wait_ms, "error": str(error)})
                    print(f"model at capacity; retry {attempt} in {wait_ms}ms", file=sys.stderr, flush=True)
                    time.sleep(wait_ms / 1000)
                    delay_ms = min(delay_ms * 2, 60000)
        except BaseException:
            self.close()
            raise

    def _ask(self, prompt, context, frames, schema, effort):
        params = {"threadId": self.thread_id, "outputSchema": schema, "input": [
            {"type": "text", "text": prompt},
            {"type": "text", "text": json.dumps(context, separators=(",", ":"))},
            *[{"type": "localImage", "path": f["path"]} for f in frames]]}
        if effort:
            params["effort"] = effort
        deadline_ms = time.monotonic() * 1000 + self.timeout
        turn_id = self.rpc.call("turn/start", params, self.timeout)["turn"]["id"]
        messages = {}
        while True:
            if time.monotonic() * 1000 >= deadline_ms:
                raise TimeoutError("Codex turn timed out")
            event = self.rpc.events.popleft() if self.rpc.events else self.rpc.receive(deadline_ms)
            p = event.get("params") or {}
            if p.get("threadId") != self.thread_id:
                continue
            if event.get("method") == "item/completed" and p.get("turnId") == turn_id:
                item = p["item"]
                if item["type"] == "agentMessage":
                    messages[item["id"]] = item
            if event.get("method") == "turn/completed" and p["turn"]["id"] == turn_id:
                turn = p["turn"]
                if turn["status"] != "completed":
                    error = turn.get("error")
                    if turn["status"] == "failed" and isinstance(error, dict) and error.get("codexErrorInfo") == "serverOverloaded":
                        raise CapacityError(str(error))
                    raise RuntimeError(str(error or turn["status"]))
                for item in turn.get("items", []):
                    if item["type"] == "agentMessage":
                        messages[item["id"]] = item
                final = [m for m in messages.values() if m.get("phase") in (None, "final_answer")]
                return json.loads(final[-1]["text"]), turn_id

    def close(self):
        try:
            if self.rpc:
                self.rpc.close()
                self.rpc = None
        finally:
            if self.events:
                self.events.close()
                self.events = None
            if self.temporary_home:
                self.temporary_home.cleanup()
                self.temporary_home = None
