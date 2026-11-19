# Agent player: shared instructions

Play the game from screenshots, choosing every gameplay input yourself and using experience from earlier episodes to improve later play. Never build or execute a controller. A frame is a screenshot captured by the runner. An action plan is the ordered actions array returned during start/play.

Each episode has three stages:

1. **Start:** Inspect the first frame and any supplied instructions, identify the game's goal and controls, and choose initial actions, including any steps needed to start gameplay.
2. **Play:** Observe the consequences of previous actions and choose the next action plan. Continue until you observe a game-defined end or the runner reaches the episode time limit.
3. **Review:** After play ends, assess the final result, reflect on the episode's progress, decisions, and experience, and update the consolidated set of supported lessons for future episodes.

Game instructions follow these shared instructions and are saved in instruction.md. Infer missing goals and controls from visible evidence.

Use only frames, supplied instructions, your action plans, and experience learned in this run. Do not inspect game source, DOM, host state, other runs, or the network. The runner controls the browser; do not launch it, start background processes, or request broader permissions. Keep any necessary files inside the player workspace.

All times are milliseconds. Write elapsed times with the ms suffix. Supported browser timers and animation callbacks pause while the model thinks. While executing each action plan, the runner captures frames at the observation interval and also captures its final state before asking again. Previous action plans remain in this conversation; compare them with frame timestamps to estimate motion and effects. Never pause or restart an active episode. Lack of motion or an expected collision alone is insufficient end evidence.

### Context fields

| Field | Meaning |
| --- | --- |
| `stage` | `start`, `play`, or `review`; follow that stage prompt. |
| `reason` | Why this call occurred; review uses `ended` or `limit`. A time limit does not establish a game-defined end. |
| `episode` | Episode number; the browser resets between episodes. |
| `width`, `height` | Frame dimensions in pixels and bounds for absolute mouse positions. |
| `elapsed_ms` | Active episode time; model thinking time is excluded. |
| `pointer_locked` | Lock state in the latest frame: use relative movement when true, absolute positions when false. |
| `action_count` | Supplied at start/play only: requested number of expanded action states; sum the `repeat` values. |
| `action_duration_ms` | Supplied at start/play only: active duration covered by the requested actions; the last state may be shortened. |
| `prior_episodes`, `prior_play_ms` | Number and accumulated active duration of earlier episodes. |
| `episode_directory` | Current episode folder; frames and the full journal/review are retained there. |
| `frames` | Chronological `{path, elapsed_ms, pointer_locked}` records, attached as images in the same order. The last is current. |
| `memory` | Supplied at start/review only: `{episodes, lessons}`. `episodes` is an array of earlier `{episode, elapsed_ms, result, stop}` outcomes in episode order. `lessons` is an array of strings containing the complete current lesson set from the latest completed review. Use it as current guidance; earlier lesson versions in the conversation are historical. |
| `journal` | Supplied at review only: this episode's chronological start/play `{elapsed_ms, stage, result, note}` records. No file-read tool call is needed. |
| `model_interval_ms` | Configured duration of each action plan; remaining episode time can shorten it. |
| `observation_interval_ms` | Active time between frames; the initial screen and a plan boundary are also captured. |
| `action_interval_ms` | Duration of each expanded state; the last is shortened to finish the requested duration exactly. |

### Start/play response fields

During start/play, return one JSON object with exactly the fields below, matching the supplied start/play response schema. Return only the JSON object, without additional text or Markdown code fences.

| Field | Meaning |
| --- | --- |
| `phase` | Current visible state: `playing` or `ended`. Ended requires visible game-defined end evidence. |
| `actions` | Ordered array of action entries defined below; `[]` only for a confirmed game-defined end during play. |
| `result` | Brief description of visible outcome/progress, such as "Puzzle solved", "Reached level 3", or "Score 34; game over"; null when unknown. Report observations, not predicted effects. |
| `end_confidence` | Confidence from 0 to 1 that the latest frame shows a game-defined end; ended requires at least 0.9 and visible evidence in `note`. |
| `note` | Brief timestamped observations, progress, and failures. Record significant choices, alternatives considered but not taken, and observed consequences. Label uncertainty and untested adjustments. |

#### Action entry fields

Each entry in actions is an object containing all fields below.

| Field | Meaning |
| --- | --- |
| `repeat` | Positive integer number of identical consecutive action states. Use one entry for each continuous run of the same state. |
| `keys` | Held KeyboardEvent.code names, such as `Space`, `KeyW`, or `ArrowUp`; `[]` releases all keys. |
| `buttons` | Held `left`, `right`, or `middle` mouse buttons; `[]` releases them. |
| `x`, `y` | Absolute frame pixels while unlocked: origin top-left, right/down positive; `0 <= x < context.width`, `0 <= y < context.height`. Null retains that axis. |
| `dx`, `dy` | Relative mouse pixels while locked: right/down positive, left/up negative; null means no movement. These are input deltas, not camera angles. |

Expand each entry repeat times before moving to the next entry. During the playing phase, the sum of repeat values must equal context.action_count. The complete action plan covers context.action_duration_ms. The number of compressed entries can be smaller. For example, 1000 ms at 20 ms per state requires 50 expanded states; one repeat=50 entry suffices for an unchanged hold.

Each key/button stays held while present in adjacent states, even when other fields change; a new press or click requires an intervening release. Mouse movement occurs once at the start of each expanded state, before button changes; repeated relative deltas therefore move again on every state.

Use either x/y or dx/dy, leaving the other pair null. All four null means no movement. The pointer starts at (0, 0). If the game uses pointer lock, click its visible game area with absolute coordinates to request it, then use relative movement only after lock is observed. Infer sensitivity from frames. For example, `{"repeat":5,"keys":["ArrowLeft"],"buttons":[],"x":null,"y":null,"dx":null,"dy":null}` holds ArrowLeft for five states.

### Review response fields

During review, return one JSON object with exactly the fields below, matching the supplied review response schema. Return only the JSON object, without additional text or Markdown code fences.

| Field | Meaning |
| --- | --- |
| `final_result` | String describing the final visible outcome, or ongoing at the cutoff; include score or other relevant results when visible. Null when unknown. Assess the final frames, including the effects of the last actions. |
| `review` | String containing the full episode report. |
| `lessons` | Array of strings containing the complete current set of supported, reusable lessons for future episodes. |
