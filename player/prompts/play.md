# Agent player: play

## Stage: play

Compare the previous action plan with its chronological frames; the last frame is current. Learn from observed motion, progress, failures, and action consequences. Apply the current lesson set supplied at episode start and choose an action plan covering context.action_duration_ms, with compressed actions whose repeats sum to context.action_count. If the latest frame confidently shows a game-defined end, return ended with actions=[] and visible evidence. Keep note concise, with elapsed times, significant choices and consequences. Return a JSON object following the Start/play response fields table in the shared instructions.
