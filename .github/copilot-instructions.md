# GitHub Copilot Project Context: Automated Subbuteo Simulator

## Mandatory Project Context
- At the start of the session before answering a project-specific question or planning, reviewing, or changing project files, read [SUBBUTEO_SIM_RULES.md](../SUBBUTEO_SIM_RULES.md). Do not rely on remembered or summarized rules when the canonical document is available.
- Explicitly confirm in your first response that you have read the rules. If the file cannot be accessed, say so and do not claim to have read it.

## Documentation and Code Changes
- Do not create or modify documentation unless the user explicitly instructs you to. This includes [SUBBUTEO_SIM_RULES.md](../SUBBUTEO_SIM_RULES.md), README files, and other documentation or specification files.
- This restriction does not prevent code changes: when implementing a requested coding task, create or modify the necessary source, test, configuration, or other implementation files. Do not update documentation as a side effect unless explicitly asked.

## Core Architecture Guidelines
- Name core simulator modules with the `sim_` prefix and concise lowercase `snake_case` responsibility names (for example, `sim_pitch.py`, `sim_physics.py`, and `sim_tactics.py`).
- Keep demos and previews separate in `demo_<module>.py` files; have them import and use the corresponding `sim_<module>.py` core module rather than duplicate its implementation.
- **Language & Libraries:** Python 3.x using Pygame for rendering and custom vector math / Pymunk for physics.
- **Decoupled Engine Design:** Always separate physics math/zonal state calculations from Pygame drawing loops. Ensure physics logic can run headlessly without Pygame window dependencies.
- **Coordinates:** Use normalized floats [0.0, 0.0] to [1.0, 1.0]. Convert to screen pixel surface coordinates only at the rendering boundary.

## Physics & Boundary Constraints
- All pitch perimeter boundaries rebound the ball with a restitution coefficient of 0.65. Touchline rebounds retain possession; a goal-line rebound transfers possession to the opposing player. See [SUBBUTEO_SIM_RULES.md](../SUBBUTEO_SIM_RULES.md) for the full boundary rule and dimensions.
- The figure-base radius is approximately 10 mm.
- At kick-off, only goalkeeper pieces may be inside a scoring area; field player pieces must be outside both scoring areas.
- Turns run on discrete impulse phases (Attacker impulse -> equilibrium -> Defender block-flick).

## AI Decision-Making (Asimov Laws)

### Strategic Context: AI Player Motivation
The attacking AI player's ultimate goal is to score. To score, the ball must reach the opponent's goal line. To reach the goal line reliably, the attacking player must maintain possession across multiple turns, controlling the ball's position and preventing the defender from gaining access. This requires:
- **Possession Preservation**: Keep the ball in contact range of an available piece through tight flicks and tactical positioning
- **Touch Quota Management**: Use the 3-touch rule strategically—advance on touches 1-2, then on touch 3 either shoot (if eligible), pass to a teammate, or set up the next piece's continuation via an angled nudge that moves the flicker out of the way
- **Board Control**: Maintain piece positioning such that teammates are always available for the next contact without requiring piece repositioning that loses possession

### Attacker Priority Stack (Hierarchical Decision-Making)
1. **First Law (Scoring)**: If the ball's center is strictly inside the opponent's shooting area when the flick begins (X > 0.80 toward increasing X; X < 0.20 toward decreasing X) **AND** a clear ray exists from the ball center to the goal mouth, shoot for the goal. A ball on the shooting line is outside; a blocked ray makes shooting unsafe.

2. **Second Law (Possession & Touch Mechanics)**:
   - **Safety Constraint**: Never allow the flicking piece to collide with a defender before the piece contacts the ball.
   - **Flick Selection**: Among safe continuation options, prefer the lowest required flick strength; among equal-strength flicks, prefer shorter ball movement. A longer or stronger flick is valid only when it is the safest way to maintain possession; never use power merely to maximize distance.
   - **Touch 1-2 Behavior**: Advance the ball forward with decreasing power, keeping it within safe reach of a teammate.
   - **Touch 3 Behavior** (Critical): On the third consecutive touch with the same piece, the attacking player must choose one of:
     - **Shot** (if First Law conditions are met)
     - **Direct Pass** (a traditional pass to a teammate)
     - **Setup Pass** (a short, angled nudge that angles the ball trajectory to create space and moves the flicker out of the way, allowing a teammate to continue possession without repositioning)
     
     A setup pass does not reset the current piece's touch count unless the ball touches another figure; when the receiver contacts the ball, their touch count resets to 0. Never attempt a fourth touch without a valid reset (another piece touching the ball first).
   - **Piece Switching**: The player may switch pieces at any time and need not use all 3 touches; this enables tactical repositioning.
   - **Attacking Fouls**: If the attacking piece collides with a defender, transfer possession immediately to the fouled defending player from the current board state; do not award a free kick or reposition pieces.

3. **Third Law (Forward Progress)**: When higher-priority laws permit, progress the ball forward (increasing X toward the opponent's goal).

### Defender Priority Stack (Block-Flick Response)
1. **First Law**: A block-flick must not touch the ball or attacking figures; invalidate an illegal block by returning play to the attacker.
2. **Second Law**: Intercept the ray from ball to goal frame.
3. **Third Law**: Intercept secondary passing lanes.

## Primary Context File
- Use [SUBBUTEO_SIM_RULES.md](../SUBBUTEO_SIM_RULES.md) as the canonical, self-contained project rules and terminology reference. In particular, **player** means the AI decision-maker, while **player piece** means an individual flicked field figure. Follow its glossary and do not use these terms interchangeably. Formation Y-coordinates and spacing remain to be defined when pitch and player positions have more context; do not guess them.
