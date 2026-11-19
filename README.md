<div align="center">
<h1>
  PlayCraft: Designing Engaging Games<br>
  from Agent Play Experience
</h1>

https://github.com/user-attachments/assets/8e56e38b-f803-4bbf-be8c-26eba37305fe

<h4>Visit the project website to play games developed with PlayCraft.</h4>
<p align="center">
  <a href="https://xt4d.github.io/playcraft-web"><b>Website</b></a> ·
  <a href="https://xt4d.github.io/playcraft-web/paper/"><b>Paper</b></a>
</p>
</div>

## 📖 Overview

PlayCraft is an automated framework for designing engaging games that give players a path from beginner play to mastery.

PlayCraft alternates between playing and crafting:
- A player agent watches the game screen, uses the controls, and pursues the game objective over repeated episodes while retaining memory.
- A crafter agent then uses the experience from the player agent to revise the game, aiming to reward better decisions and execution.

## 🛠️ Get started

### 1. Setup

#### 1.1 Install Python dependencies and Chromium

Run the commands from the repository root in a Bash-compatible shell. Recommend Python 3.11 or later on macOS or Linux with a GPU available to Chromium.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

If `python -m playwright install chromium` fails, use `find_chrome.sh` to set `CHROME_PATH` to an installed Chrome or Chromium executable before running PlayCraft.

```bash
CHROME_PATH=$(bash find_chrome.sh) && export CHROME_PATH
```

The standalone finder checks common install locations on macOS, Linux, and Windows. Set `CHROME_PATH` directly if you use a custom installation.

#### 1.2 Install and sign in to Codex

Install the [Codex CLI](https://learn.chatgpt.com/docs/cli).

Sign in with file-based credential storage so the scripts can reuse your login in Codex sessions. [Codex authentication and credential storage](https://learn.chatgpt.com/docs/auth#credential-storage)

```bash
codex --version
codex login -c 'cli_auth_credentials_store="file"'
```

### 2. Create the initial game

Create the initial game with a prompt:

```bash
bash create_initial_game.sh output/game \
'a 3D first-person shooting game'
```

If you are starting from an existing game, make sure it has an `index.html` at its root and includes the scripts and assets it needs. Add an `instruction.md` at the root with the game objective, basic rules, and controls.

Create the iteration workspace from your game directory:

```bash
bash prepare_workspace.sh output/game
```

The workspace defaults to the game directory with `-workspace` appended. Pass a second argument to choose another location. The script copies the game into `iter0` and removes logs and temporary files from the copy. If Git is available, it makes an initial commit in a fresh repository.

### 3. Run the PlayCraft loop

Run `playcraft_loop.sh` with the workspace:

```bash
bash playcraft_loop.sh output/game-workspace 0 3 60_000 720 540
```

This example starts at `iter0` and runs through `iter3` at 720 × 540 pixels, with up to 60 seconds of active play per episode.

#### Run arguments

| Position | Argument | Description |
| --- | --- | --- |
| 1 | Workspace directory | Directory containing the iteration folders |
| 2 | Starting iteration | Existing iteration to play first, such as `0` for `iter0` |
| 3 | Final iteration | Last iteration to produce, such as `3` for `iter3` |
| 4 | Play time | Maximum active play time per episode in milliseconds |
| 5 | Render width | Width in pixels |
| 6 | Render height | Height in pixels |
| 7 | Play runs | Optional number of play runs per iteration. Defaults to `1`. |
| 8 | Run mode | Optional. Use `seq` (default) for sequential runs or `parallel` for concurrent runs. |

#### Iteration outputs

Paths are relative to the workspace. The loop plays the game at `iter[N]` and writes the updated game to `iter[N+1]`. Play run numbers start at `0`.

- `iter[N]-play/play-[run]/` contains raw screenshots and logs.
- `iter[N+1]/logs/play-[run]/play.md` contains the play reports with links to journals and lessons.
- `iter[N+1]/logs/design.md` and `iter[N+1]/logs/implementation.md` contain the design proposal, changes, and verification results.
- `iter[N+1]/index.html` is the entry point of the updated game.

## 🎮 Play a game

Run the player agent to play a browser-based game (requires `index.html` as its entry point):

```bash
python player/play.py output/game \
  --output output/game-play \
  --model gpt-6.1-sol \
  --episodes 1 --duration 10_000 \
  --width 480 --height 480
```

This example runs 1 episode with up to 10 seconds of active play at 480 × 480 pixels.
Screenshots, the episode journal, and the episode review are saved under `output/game-play/player/e001/`.

Generate `play.md` from the saved run:

```bash
python player/play_record.py output/game-play output/game-play-record
```

## Citation

```bibtex
@article{cheng2026playcraft,
  title  = {PlayCraft: Designing Engaging Games from Agent Play Experience},
  author = {Weihao Cheng},
  year   = {2026},
}
```

## License

PlayCraft is released under the [MIT License](LICENSE).
