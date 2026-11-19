# Create Game

## Game Prompt
{{game_prompt}}

## Build

- Build a complete, playable browser game with Three.js.
- Keep the game playable with a canvas as small as 480 × 480 pixels.
- Place all first-party JavaScript in `src/host/`.
- Use ES module versions of third-party JavaScript libraries and place them in `src/vendor/`.
- Keep the game's HTML and CSS at the project root.
- Use `index.html` as the game's sole entry point.

## Write `instruction.md`

Use the following template. Include only what players need to start playing.

```md
# Game Name — Player Instructions

## Objective

State the goal and explain what counts as a win or a failure.

## Gameplay rules

Explain the rules players can observe, including limits on movement and interactions, resources, scoring, progression, and hazards, as applicable.

## Controls

List the supported inputs and what they do, including keyboard keys, pointer buttons, and pointer movement as applicable.
```

## Rules

- Treat the current working directory as the game project root. Access files only within this directory.
