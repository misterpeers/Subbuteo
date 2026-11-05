# GitHub Copilot Project Context: Automated Subbuteo Simulator

## Mandatory Project Context
- Before answering a project-specific question or planning, reviewing, or changing project files, read [SUBBUTEO_SIM_RULES.md](../SUBBUTEO_SIM_RULES.md). Do not rely on remembered or summarized rules when the canonical document is available.
- Explicitly confirm in your response that you have read the rules. If the file cannot be accessed, say so and do not claim to have read it.

## Documentation and Code Changes
- Do not create or modify documentation unless the user explicitly instructs you to. This includes [SUBBUTEO_SIM_RULES.md](../SUBBUTEO_SIM_RULES.md), README files, and other documentation or specification files.
- This restriction does not prevent code changes: when implementing a requested coding task, create or modify the necessary source, test, configuration, or other implementation files. Do not update documentation as a side effect unless explicitly asked.

## Core Architecture Guidelines
- Name core simulator modules with the `sim_` prefix and concise lowercase `snake_case` responsibility names (for example, `sim_pitch.py`, `sim_physics.py`, and `sim_tactics.py`).
- Keep demos and previews separate in `<module>_demo.py` files; have them import and use the corresponding `sim_<module>.py` core module rather than duplicate its implementation.
- **Language & Libraries:** Python 3.x using Pygame for rendering and custom vector math / Pymunk for physics.
- **Decoupled Engine Design:** Always separate physics math/zonal state calculations from Pygame drawing loops. Ensure physics logic can run headlessly without Pygame window dependencies.
- **Coordinates:** Use normalized floats [0.0, 0.0] to [1.0, 1.0]. Convert to screen pixel surface coordinates only at the rendering boundary.

## Physics & Boundary Constraints
- All pitch perimeter boundaries rebound the ball with a restitution coefficient of 0.65. Touchline rebounds retain possession; a goal-line rebound transfers possession to the opposing player. Only a valid goal may pass through the goal mouth. See [SUBBUTEO_SIM_RULES.md](../SUBBUTEO_SIM_RULES.md) for the full boundary rule and dimensions.
- The figure-base radius is approximately 10 mm.
- At kick-off, only goalkeeper pieces may be inside a scoring area; field player pieces must be outside both scoring areas.
- Turns run on discrete impulse phases (Attacker impulse -> equilibrium -> Defender block-flick).

## AI Decision-Making (Asimov Laws)
- **Attacker Priority Stack:**
  1. First Law: If the ball's center is strictly inside the opponent's shooting area when the flick begins (X > 0.80 toward increasing X; X < 0.20 toward decreasing X) with a clear ray to goal, shoot. A ball on the shooting line is outside.
  2. Second Law (Quota & Foul): Never collide with a defender before hitting the ball. Maximum 3 consecutive touches per figure. On touch 2, force pass/shot or hit opponent figure to reset counter. For an attacking foul, transfer possession immediately to the fouled defending player from the current board state; do not award a free kick or reposition pieces.
  3. Third Law: When higher priorities permit, progress the ball forward (increasing X toward the opponent's goal).
- **Defender Priority Stack (Block-Flick):**
  1. First Law: A block-flick must not touch the ball or attacking figures; invalidate an illegal block and return play to the attacker.
  2. Second Law: Intercept ray from ball to goal frame.
  3. Third Law: Intercept secondary passing lanes.

## Primary Context File
- Use [SUBBUTEO_SIM_RULES.md](../SUBBUTEO_SIM_RULES.md) as the canonical, self-contained project rules and terminology reference. In particular, **player** means the AI decision-maker, while **player piece** means an individual flicked field figure. Follow its glossary and do not use these terms interchangeably. Formation Y-coordinates and spacing remain to be defined when pitch and player positions have more context; do not guess them.
