#!/usr/bin/env python3
"""Run prompts sequentially in fresh Codex CLI sessions."""

import argparse
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("prompts", nargs="*")
    parser.add_argument("-p", "--prompt", action="append", default=[])
    parser.add_argument(
        "--prompts-file",
        type=Path,
        action="append",
        default=[],
        help="Text or Markdown file whose full contents are one prompt; repeatable",
    )
    parser.add_argument(
        "--insert",
        nargs="+",
        action="append",
        default=[],
        metavar="NAME_OR_VALUE",
        help=(
            "Replace {{NAME}} placeholders with VALUE; provide one or more "
            "NAME VALUE pairs"
        ),
    )
    parser.add_argument(
        "-C",
        "--project-dir",
        type=Path,
        required=True,
        help="Project directory in which Codex should work",
    )
    parser.add_argument("-m", "--model", default="gpt-6.1-sol")
    parser.add_argument(
        "-s",
        "--sandbox",
        choices=("read-only", "workspace-write", "danger-full-access"),
        default="workspace-write",
        help="Codex sandbox policy (workspace-write enables automatic approval review)",
    )
    parser.add_argument(
        "--thinking-level",
        choices=("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"),
        default="xhigh",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_prompts(args):
    prompts = [*args.prompt, *args.prompts]
    for path in args.prompts_file:
        prompt = path.read_text(encoding="utf-8")
        if not prompt.strip():
            raise ValueError(f"prompt file is empty: {path}")
        prompts.append(prompt)
    return prompts


def insert_values(prompts, groups):
    values = {}
    for group in groups:
        if len(group) % 2:
            raise ValueError("--insert requires NAME VALUE pairs")
        for name, value in zip(group[::2], group[1::2]):
            if not name or "{" in name or "}" in name:
                raise ValueError(f"invalid --insert name: {name!r}")
            if name in values:
                raise ValueError(f"duplicate --insert name: {name}")
            values[name] = value

    placeholder = re.compile(r"\{\{([^{}]+)\}\}")
    return [
        placeholder.sub(
            lambda match: values.get(match.group(1), match.group(0)), prompt
        )
        for prompt in prompts
    ]


def extract_commands(log_path, commands_path):
    lines = log_path.read_text(encoding="utf-8").splitlines()
    commands = []

    for index, line in enumerate(lines[:-1]):
        if line != "exec":
            continue

        command = lines[index + 1].strip()
        before_cwd, marker, cwd = command.rpartition(" in ")
        if marker and (cwd.startswith("/") or cwd.startswith(".")):
            command = before_cwd

        try:
            parts = shlex.split(command)
        except ValueError:
            parts = []
        if (
            len(parts) >= 3
            and parts[0].endswith(("/sh", "/bash", "/zsh"))
            and parts[1] in ("-c", "-lc")
        ):
            command = parts[2]
        commands.append(command)

    commands_path.write_text(
        "\n".join(commands) + ("\n" if commands else ""),
        encoding="utf-8",
    )
    return len(commands)


def main():
    args = parse_args()
    try:
        prompts = load_prompts(args)
        prompts = insert_values(prompts, args.insert)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not prompts:
        print("error: provide prompts or --prompts-file", file=sys.stderr)
        return 2

    project_dir = args.project_dir.expanduser().resolve()
    if not project_dir.is_dir():
        print(f"error: project directory does not exist: {project_dir}", file=sys.stderr)
        return 2

    source_home = Path(
        os.environ.get("CODEX_HOME", Path.home() / ".codex")
    ).expanduser()
    temp_root = Path("tmp").resolve()
    if not args.dry_run:
        try:
            temp_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(
                f"error: cannot create temporary root {temp_root}: {exc}",
                file=sys.stderr,
            )
            return 1
    failures = 0

    for prompt_index, prompt in enumerate(prompts, 1):
        run_id = f"{time.time_ns()}-{prompt_index}"
        run_prompt = f"Run ID: {run_id}\n\n{prompt}"
        suffix = "" if len(prompts) == 1 else f"-{prompt_index:03d}"
        log_path = project_dir / f"codex-run{suffix}.log"
        commands_path = project_dir / f"codex-run{suffix}.commands.log"
        command = [
            "codex",
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "-C",
            str(project_dir),
            "--color",
            "never",
        ]
        if args.sandbox == "workspace-write":
            command.append("--approve-for-me")
        else:
            command += ["-s", args.sandbox]
        command += [
            "-m",
            args.model,
            "-c",
            f'model_reasoning_effort="{args.thinking_level}"',
            "-c",
            "features.respect_system_proxy=true",
        ]
        command += ["-"]

        label = f"prompt {prompt_index}"
        print(
            f"\n==> {label} (run ID: {run_id})\n{shlex.join(command)}",
            flush=True,
        )
        if args.dry_run:
            print(f"log: {log_path}\ncommands: {commands_path}", flush=True)
            continue

        with tempfile.TemporaryDirectory(
            prefix="codex-run-",
            dir=temp_root,
        ) as temp_dir:
            clean_home = Path(temp_dir) / "codex-home"
            clean_home.mkdir()
            auth = source_home / "auth.json"
            if auth.is_file():
                shutil.copy2(auth, clean_home / "auth.json")

            env = os.environ.copy()
            env["CODEX_HOME"] = str(clean_home)
            try:
                with log_path.open("w", encoding="utf-8") as log_file:
                    result = subprocess.run(
                        command,
                        input=run_prompt,
                        text=True,
                        cwd=project_dir,
                        env=env,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        check=False,
                    )
            except OSError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1

        command_count = extract_commands(log_path, commands_path)
        print(
            f"log: {log_path}\n"
            f"commands: {commands_path} ({command_count} extracted)",
            flush=True,
        )
        failures += result.returncode != 0

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
