# GitHub Copilot Project Context: Automated Subbuteo Simulator

## Mandatory Project Context
- At the start of the session before answering a project-specific question or planning, reviewing, or changing project files, read [SUBBUTEO_SIM_RULES.md](../SUBBUTEO_SIM_RULES.md). Do not rely on remembered or summarized rules when the canonical document is available.
- Explicitly confirm in your first response that you have read the rules. If the file cannot be accessed, say so and do not claim to have read it.

## Documentation and Code Changes
- Do not create or modify documentation unless the user explicitly instructs you to. This includes [SUBBUTEO_SIM_RULES.md](../SUBBUTEO_SIM_RULES.md), README files, and other documentation or specification files.
- This restriction does not prevent code changes: when implementing a requested coding task, create or modify the necessary source, test, configuration, or other implementation files. Do not update documentation as a side effect unless explicitly asked.

## Documentation standards

All code files, functions, methods, and classes should include docstrings. Use
multi-line docstrings that describe the purpose of the object and, where
applicable, list arguments and return values or side effects clearly.

## UI and graphical typography

Use the Barlow font family as the preferred typeface for user-interface and
graphical text. Use Barlow Black for prominent score numerals and Barlow
Condensed Medium for team labels where a clear typographic weight contrast is
desired. Keep changing numeric values in fixed-width or tabular cells so their
layout does not shift as digits change. Use the bundled font files and their
license in `assets/fonts/` rather than relying on system-installed fonts.

## Git Practices
- **Do not make commits to GitHub on the user's behalf.** The user prefers to review and manually commit all changes. After completing code or documentation changes, summarize what was modified and let the user decide whether and how to commit. Never invoke `git commit` or `git push` without explicit user instruction.

## Core Architecture Guidelines
- Name core simulator modules with the `sim_` prefix and concise lowercase `snake_case` responsibility names (for example, `sim_pitch.py`, `sim_physics.py`, and `sim_tactics.py`).
- Keep demos and previews separate in `demo_<module>.py` files; have them import and use the corresponding `sim_<module>.py` core module rather than duplicate its implementation.
- **Language & Libraries:** Python 3.x using Pygame for rendering and custom vector math / Pymunk for physics.
- **Decoupled Engine Design:** Always separate physics math/zonal state calculations from Pygame drawing loops. Ensure physics logic can run headlessly without Pygame window dependencies.
- **Coordinates:** Use normalized floats [0.0, 0.0] to [1.0, 1.0]. Convert to screen pixel surface coordinates only at the rendering boundary.

## Primary Context File
- Use [SUBBUTEO_SIM_RULES.md](../SUBBUTEO_SIM_RULES.md) as the canonical, self-contained project rules and terminology reference. In particular, **player** means the AI decision-maker, while **player piece** means an individual flicked field figure. Follow its glossary and do not use these terms interchangeably.
