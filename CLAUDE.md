# Claude Code Project Context: Automated Subbuteo Simulator

Project-wide instructions for Claude Code. They carry over the rules from
`.github/copilot-instructions.md`, which is left in place.

## Mandatory project context

These files are imported so they are loaded at the start of every session:

@SUBBUTEO_SIM_RULES.md
@AI_NOTES.md
@AI_QUERIES.md

- Before answering a project-specific question or planning, reviewing or
  changing project files, make sure you have read [SUBBUTEO_SIM_RULES.md](SUBBUTEO_SIM_RULES.md),
  [AI_NOTES.md](AI_NOTES.md) and [AI_QUERIES.md](AI_QUERIES.md). If an import
  failed or a file cannot be accessed, read it directly. If it still cannot be
  accessed, say so and do not claim to have read it.
- Do not rely on remembered or summarised rules when the canonical document is
  available.
- Explicitly confirm in your first response which files you read.
- [SUBBUTEO_SIM_RULES.md](SUBBUTEO_SIM_RULES.md) is the canonical, self-contained
  rules and terminology reference. In particular, **player** means the AI
  decision-maker, while **player piece** means an individual flicked field
  figure. Follow its glossary and do not use these terms interchangeably.

## Commands

- Tests: `python -m unittest discover -p "test_*.py"`
- Scenario harness: `python sim_scenarios.py --count 100 --seed 0 --team home`
- Current baselines are recorded in the "Next task" section of
  [AI_NOTES.md](AI_NOTES.md).

## Documentation and code changes

- Do not create or modify documentation unless the user explicitly instructs
  you to. This includes [SUBBUTEO_SIM_RULES.md](SUBBUTEO_SIM_RULES.md), README
  files, [MODULES.md](MODULES.md), and other documentation or specification files.
- The only exceptions are [AI_QUERIES.md](AI_QUERIES.md) and
  [AI_NOTES.md](AI_NOTES.md), which you maintain as described below. If other
  documentation falls out of date, tell the user instead of editing it.
- This restriction does not prevent code changes: when implementing a requested
  coding task, create or modify the necessary source, test, configuration or
  other implementation files. Do not update documentation as a side effect
  unless explicitly asked.

## Open queries

- Record every open question or decision that needs the user's input in
  [AI_QUERIES.md](AI_QUERIES.md), not in the rules document, in code comments,
  or only in chat. [SUBBUTEO_SIM_RULES.md](SUBBUTEO_SIM_RULES.md) holds decided
  rules and implementation status only.
- Follow the format already used in that file: the next free `Q` number, a
  heading, a plain-language question with units where relevant, a suggested
  default when you have one, and a `**Your response: TBD**` line for the user
  to fill in. Add the new item to the status table at the top.
- Never edit or overwrite a response the user has written. When the user
  answers a question, treat the answer as decided: record it in
  [AI_NOTES.md](AI_NOTES.md), and tell the user if the rules document should
  change so they can instruct you to update it.
- Still ask the user in the session when a decision blocks the current task,
  and also add it to [AI_QUERIES.md](AI_QUERIES.md) so it is not lost.

## Project plan and notes

- Maintain [AI_NOTES.md](AI_NOTES.md) during every session. It holds the
  handover for the next session: the next task, current status and baselines,
  decisions the user has made, the planned work, and known issues.
- Update it as work progresses, not only at the end: when a plan step is
  finished, started or changed, when the user makes a decision, when you learn
  something that affects the plan, and when baseline figures (test count,
  harness results) change.
- Keep its question list consistent with [AI_QUERIES.md](AI_QUERIES.md); do not
  keep a second, different list.

## Starting a session

This is the only place the start-of-session procedure is written.

Every session, before any project-specific work:

- Read [SUBBUTEO_SIM_RULES.md](SUBBUTEO_SIM_RULES.md), [AI_NOTES.md](AI_NOTES.md)
  and [AI_QUERIES.md](AI_QUERIES.md) (see "Mandatory project context").
- Treat an answer the user has recorded in [AI_QUERIES.md](AI_QUERIES.md) as
  decided, even if [AI_NOTES.md](AI_NOTES.md) has not caught up yet.
- In your first response, confirm which files you read and mention any
  questions the user has answered since [AI_NOTES.md](AI_NOTES.md) was last
  updated.

When the user's message is "HELLO THERE" (any capitalisation), also do the
following, in order:

1. Run the full test suite and the scenario harness using the commands in the
   "Next task" section of [AI_NOTES.md](AI_NOTES.md), and say whether the
   results match the baselines recorded there.
2. Summarise where the project stands in a few lines.
3. Plan out the task described in "Next task". Respect its stopping points; in
   particular, wait for the user's approval before implementing when it says to.
4. If the user adds text after the phrase, follow that text in preference to
   the task, and say so.
5. If "Next task" is missing or unclear, say so and ask the user what to do next
   instead of guessing.

## Ending a session

When the user says "EXECUTE ORDER 66" or a clear equivalent, do a final review
of [AI_NOTES.md](AI_NOTES.md) before replying:

- If code changed during the session, run the full test suite and the scenario
  harness and update the recorded baselines.
- Rewrite "Next task" so the next session can start from it with no other
  context: the task, the commands, and the current baselines.
- Bring the plan, the user's decisions, the known issues and the open-questions
  table up to date, and make them agree with [AI_QUERIES.md](AI_QUERIES.md).
- Note any other documentation (rules, module guide) that is now out of date,
  without editing it unless the user asks.

Then give a short summary of what changed this session and what the next
session will do. Do not commit or push.

## Git practices

- **Do not make commits or pushes on the user's behalf.** The user prefers to
  review and manually commit all changes. After completing code or
  documentation changes, summarise what was modified and let the user decide
  whether and how to commit. Never run `git commit` or `git push` without
  explicit user instruction.

## Core architecture guidelines

- Name core simulator modules with the `sim_` prefix and concise lowercase
  `snake_case` responsibility names (for example `sim_pitch.py`,
  `sim_physics.py` and `sim_tactics.py`).
- Keep demos and previews separate in `demo_<module>.py` files; have them import
  and use the corresponding `sim_<module>.py` core module rather than duplicate
  its implementation.
- **Language and libraries:** Python 3.x using Pygame for rendering and custom
  vector math / Pymunk for physics.
- **Decoupled engine design:** Always separate physics math and zonal state
  calculations from Pygame drawing loops. Physics logic must run headlessly
  without Pygame window dependencies.
- **Coordinates:** Use normalised floats [0.0, 0.0] to [1.0, 1.0]. Convert to
  screen pixel surface coordinates only at the rendering boundary.

## Documentation standards

All code files, functions, methods and classes should include docstrings. Use
multi-line docstrings that describe the purpose of the object and, where
applicable, list arguments and return values or side effects clearly.

## UI and graphical typography

Use the Barlow font family as the preferred typeface for user-interface and
graphical text. Use Barlow Black for prominent score numerals and Barlow
Condensed Medium for team labels where a clear typographic weight contrast is
desired. Keep changing numeric values in fixed-width or tabular cells so their
layout does not shift as digits change. Use the bundled font files and their
license in `assets/fonts/` rather than relying on system-installed fonts.
