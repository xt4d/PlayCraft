# Implementation

Implement the focused set of changes in `logs/design.md` while preserving their intended player-facing outcomes.

## Task

1. Review the implementation inputs:
   - Read `instruction.md` to understand the current player-facing objective and controls.
   - Read `logs/design.md` to understand the proposed changes, the priorities each change addresses, and the intended player experience.
   - Inspect `src/host` and any other implementation directly affected by the proposed changes to understand the current behavior and technical constraints.

2. Derive implementation requirements and acceptance criteria before making changes:
   - Identify the player-facing outcome each proposed change must produce.
   - Map each change to its stated design priorities.
   - Identify dependencies between changes and the systems they affect.
   - Define observable checks for the affected controls, rules, objectives, world structure, feedback, decisions, presentation, and experience.

3. Reconcile the proposed changes with the existing implementation:
   - Treat the code as the source of truth for current behavior and `logs/design.md` as the desired experience.
   - Preserve the stated design priorities, relevant existing strengths, and intended player-facing outcomes.
   - Adapt implementation details when the proposal conflicts with actual systems or omits necessary details.
   - Do not silently omit a proposed change. Record any material deviation and its reason.
   - Do not introduce unrelated features.

4. Implement the changes in the game code, including `src/host` and any other directly affected project files:

   - Build foundational changes first, followed by dependent changes, and integrate them as a consistent experience.
   - Keep affected controls, rules, objectives, world structure, feedback, decisions, and experience consistent with one another.
   - Integrate new or changed visuals with the game's established or intended aesthetic. Refine their form, proportion, composition, color, material, lighting, motion, and spacing as relevant so they are legible, cohesive, and intentional rather than provisional, cluttered, or visually disconnected.
   - When a change affects spatial layout, inspect and refine the relevant geometry, positions, dimensions, orientations, spacing, and connections so the result is clear and intentional.
   - When adding surface details such as panels, trim, or markings, avoid coplanar or nearly coplanar overlapping faces that can cause z-fighting. Remove duplicate faces, provide sufficient geometric separation, or use an appropriate decal or depth-offset technique while preserving correct occlusion.

5. Verify the implementation before updating documentation:

   - Run relevant build and automated checks.
   - Exercise the affected gameplay enough to confirm the acceptance criteria and that the intended experience is reachable.
   - Inspect affected feedback, geometry, and visuals in the actual game renderer, including relevant viewing angles and camera or object movement. Check aesthetic coherence, legibility, visual hierarchy, composition, and clutter, as well as z-fighting, unintended flicker, clipping, and other visual regressions. If actual rendering cannot be checked, report that limitation explicitly; geometry checks or simplified renders alone do not establish visual correctness or aesthetic quality.
   - Correct discrepancies and repeat the relevant checks before finishing.

   This verification checks implementation correctness and design conformance. Do not claim that the implementation has proven the design targets; those conclusions require subsequent playtesting.

6. After verification, update `instruction.md` to reflect the final game:
   - **Objective:** State the player's goal and basic success/failure conditions.
   - **Controls:** Explain how to start and what each input does, including essential press, hold, and release behavior.
   - Include only what players need to begin meaningful play; leave the rest for them to discover through play.
   - If an Agent API section exists and the implementation changes its documented interface, update that section as well. Preserve other unrelated content.

## Output

Save the implementation report to `logs/implementation.md`:

- **Implemented changes:** What changed and the resulting player-facing behavior.
- **Design coverage:** Which design priorities and proposed changes are addressed.
- **Deviations:** Any material difference from `logs/design.md`, with the technical or design reason.
- **Verification:** Checks performed, scenarios exercised, and their results.
- **Remaining limitations:** Unresolved uncertainty, risk, or follow-up work.

## Rules

* Treat the current working directory as the game project root. Do not access files outside this directory.
* If temporary files are needed, store them in `logs/temp/impl`.
* Start browser verification with a fresh, isolated context or a newly created empty temporary profile. Never reuse an existing profile or restore saved browser state. Track any browser process you launch and close the context and browser in a `finally` block or equivalent cleanup handler, then wait for the process to exit before deleting its temporary profile.
