# Design

Design changes to the game so that repeated play produces meaningful improvements in expected performance through better understanding, decisions, and execution. Base the proposal on how the recorded players actually play and learn.

## Design-Targets

- **Performance anchors.** The following results should be achievable within {{play_time_ms}} ms of active play under the same rules, through strategies that remain advantageous under the game's objectives independently of this time window.

   - **Games with a completion objective:** The most skilled players should be capable of completing the objective; their expected results define the 100% reference. For beginners, expected results should be approximately 10-30% of that reference. For intermediate players, expected results should be approximately 50-70% of that reference.
   - **Games without a completion objective:** The most skilled players should be able to experience the core loop and major challenges; their expected results define the 100% reference. For beginners, expected results should be approximately 10-30% of that reference. For intermediate players, expected results should be approximately 50-70% of that reference.

   Ground performance expectations in the recorded player's demonstrated abilities and skills; zero previous episodes does not imply zero skill.

- **Skill-based improvement.** The game should provide meaningful opportunities for better decisions and execution, with understandable benefits, costs, and risks. As players gain experience and skill, they should be able to exploit these opportunities to achieve continued improvements in their expected performance through better play.

## Task

1. Read `instruction.md` to understand the game objective, rules, and controls, and identify the primary metrics of player performance.
2. Review relevant previous `design.md` and `implementation.md` files in `logs/history` to understand earlier design directions and their reported implementation. Use this history to connect current findings with earlier changes, preserve useful work, identify unresolved issues, and make the next proposal build on or deliberately depart from previous directions.
3. Use all available current play records matching `logs/play-*/play.md` to identify ways to move the game toward the design-targets. Consider strengths to preserve, gaps to address, and promising opportunities.
   - Understand the recorded player's experience and results.
   - Estimate the player's baseline abilities and skills from the available play records, then estimate the player's expected beginner, intermediate, and expert performance in the current game, accounting for uncertainty from limited evidence. Compare these performance estimates across proficiency levels and against the design-targets.
   - If a previous design is available, compare its expectations with current play records to identify which expectations were supported, contradicted, or remain uncertain or untested.
   - Identify where the game falls short of the design-targets and why, considering its entry difficulty; demands on understanding, perception, and execution; opportunities for strategic choice; reward structure; challenge progression; and performance ceilings.
   - Assess whether to explore new design ideas or refine a previous design direction. Explain the rationale based on the available evidence and the remaining gaps to the design-targets. When exploring new ideas, consider a broad range of possibilities. Compare directions against the design-targets and the guidelines below, then select the most promising direction and explain why.

4. Develop a focused design proposal following these guidelines:
   - **Prioritize novel designs to deepen strategic play.** Prefer distinctive changes or additions that enable new strategies, tactics, and meaningful choices while preserving the game's defining interactions and player experience.
   - **Keep the design coherent and simple.** Integrate new mechanics with the game's core interactions so they form a clear, unified play experience. Evaluate supporting rules by the learning benefit they add and the complexity they introduce. Consider whether a simpler, more unified design could achieve the same benefit.
   - Build on the player's baseline abilities and skills. Account for their observation and input capabilities and the strategies they could readily discover and execute during initial play. Create challenges that reward further learning through better decisions and execution. Do not assume unfamiliar mechanics alone produce low beginner performance or a strong learning curve.
   - Favor designs that make the game visually appealing, clean, and clear. Consider the combined effect of proposed changes on the whole game during play. Simplify or reconsider designs that create clutter, competing distractions, misleading impressions, or an incoherent appearance.
   - Make objects, actions, and consequences understandable through their presentation and behavior. Avoid adding indicators or explanatory displays unless they are necessary to communicate essential gameplay information.
   - Preserve the existing camera setup by default. Change it only when necessary to resolve a demonstrated gameplay issue, while retaining the game's defining viewing perspective.
   - Do not add, remove, or change the game's objectives.
   - Do not use selectable difficulty levels as a substitute for skill progression within the core game.
   - Do not change canvas dimensions.

## Output

Save the proposal to `logs/design.md`:

- **Design overview:** A short summary of the proposed changes and the experience they collectively create.
- **Current-game opportunity:** Summarize the findings that motivate the proposal, including where the game falls short of the design-targets and which aspects of its design contribute to those gaps. State any relevant uncertainties.
- **Supporting designs:** A numbered list describing each proposed change, how it works for the player, and which design-targets or guidelines it addresses.
- **Player experience and performance:** State the player's baseline abilities and skills—those present before any experience with the game—and how performance is measured. Describe the player's experience and expected results at beginner, intermediate, and expert levels under the proposed changes. Treat expected beginner performance, given those baseline abilities and skills, as the starting point. Explain how strategies and decisions evolve through practice and why this produces better results. State the basis and uncertainty of the estimates.

Use clear, concise language without repeating the same explanation. 

## Rules

* Treat the current working directory as the game project root. Do not access files outside this directory.
* If temporary files are needed, store them in `logs/temp/design`.
