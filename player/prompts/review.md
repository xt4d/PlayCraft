# Agent player: review

## Stage: review

Use context.journal, the final frames, and this conversation to review the episode. The journal is already supplied; do not read it with a tool. Do not issue actions, restart the game, or create a controller. Return a JSON object following the Review response fields table in the shared instructions. In final_result, summarize the final visible outcome; a time cutoff does not establish a game-defined end. In review, fill in the Markdown template below, replacing the bracketed guidance with episode-specific content. Preserve the labels and order. Keep each entry on one line, with no blank lines between entries. In lessons, return the complete current set of supported, reusable lessons for future episodes, following the consolidation instructions below.

### Player-experience report template

- **Starting conditions:** [Number of prior episodes and accumulated active play time from context; experience carried from them; instructions consulted, including on-screen instructions.]
- **Progress:** [Significant milestones, obstacles, and failures in chronological order with elapsed game times; furthest point reached.]
- **Final result:** [Game-defined outcome, or ongoing at the configured cutoff; active duration from context.elapsed_ms; score and other visible results; reason the episode ended.]
- **Decisions:** [Significant choices and alternatives actually considered; brief reasons, expectations, and observed consequences.]
- **Player's view:** [What you understood and what remained confusing. What you anticipated and how observed outcomes compared with your expectations. What felt easy and what felt difficult. Distinguish your interpretation from facts established by the game.]
- **Learning:** [What you learned from your actions and observations; how feedback informed adjustments and their observed results; changes from earlier episodes; what you would try next.]

### Lessons

Lessons are supported insights from experience that can guide future play. They may describe game mechanics, useful strategies, or conditions under which an action helps or causes problems. Build the complete current lesson set by consolidating context.memory.lessons with findings from this episode and earlier episodes. Retain supported lessons, merge overlapping lessons, and revise or remove contradicted lessons. Do not restore superseded claims from older reviews without new supporting evidence. Keep lessons concise, actionable, and generalizable across situations rather than episode-specific. If nothing changes, return the existing set unchanged. Return lessons=[] only when no reusable lessons remain.
