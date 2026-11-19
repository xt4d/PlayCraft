"""Fresh Codex homes and native command permissions.

player_permissions() defines the policy; prepare_home() writes config.toml.
Codex selects the "player" profile when starting commands.
"""

import json
import os
import shutil
import sys
from pathlib import Path


def player_permissions(workspace):
    """Allow workspace read/write, minimal runtime reads, and no network."""
    return {
        "filesystem": {
            ":root": "deny",       # Deny file access by default.
            ":minimal": "read",    # Allow system/runtime files needed by tools.
            str(workspace.resolve()): "write",
        },
        "network": {"enabled": False},
    }


# Fresh-conversation settings; command permissions are defined above.
CLEAN_CONFIG = '''cli_auth_credentials_store = "file"
project_root_markers = []
project_doc_max_bytes = 0
default_permissions = "player"
web_search = "disabled"
allow_login_shell = false
[history]
persistence = "none"
[memories]
use_memories = false
generate_memories = false
[features]
memories = false
plugins = false
apps = false
hooks = false
shell_snapshot = false
skip_host_skill_discovery = true
skill_search = false
browser_use = false
browser_use_external = false
browser_use_full_cdp_access = false
in_app_browser = false
in_app_chat = false
computer_use = false
image_generation = false
multi_agent = false
workspace_dependencies = false
code_mode = false
code_mode_host = true
skill_mcp_dependency_install = false
shell_tool = true
respect_system_proxy = true
[shell_environment_policy]
experimental_use_profile = false
inherit = "none"
'''


def prepare_home(home, workspace, authenticate=False):
    """Write only this run's config; the model service may also receive login credentials."""
    workspace = workspace.resolve()
    temporary = workspace / ".tmp"
    if not temporary.resolve().is_relative_to(workspace):
        raise ValueError("temporary directory escapes the player workspace")
    temporary.mkdir(exist_ok=True)
    (home / "tmp").mkdir(exist_ok=True)
    if not shutil.which("codex"):
        raise RuntimeError("codex is not installed")

    # Environment for commands executed inside Codex's native sandbox.
    command_environment = {
        "PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONNOUSERSITE": "1",
        "TMPDIR": str(temporary),
    }
    config = CLEAN_CONFIG + "\n[shell_environment_policy.set]\n"
    for key, value in command_environment.items():
        config += f"{key} = {json.dumps(value)}\n"
    for section, entries in player_permissions(workspace).items():
        config += f"\n[permissions.player.{section}]\n"
        for key, value in entries.items():
            config += f"{json.dumps(key)} = {json.dumps(value)}\n"
    (home / "config.toml").write_text(config, encoding="utf-8")

    # Environment for the app-server or sandbox launcher itself.
    keep = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "LC_CTYPE")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env.update(CODEX_HOME=str(home), TMPDIR=str(home / "tmp"), PYTHONNOUSERSITE="1")
    if authenticate:
        auth = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "auth.json"
        if auth.is_file():
            shutil.copyfile(auth, home / "auth.json")
            (home / "auth.json").chmod(0o600)
        elif not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("Clean runs need file-based Codex login (auth.json) or OPENAI_API_KEY")
        for key in ("OPENAI_API_KEY", "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTP_PROXY", "HTTPS_PROXY",
                    "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy"):
            if key in os.environ:
                env[key] = os.environ[key]
    return env
