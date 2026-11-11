# Subbuteo Simulator Rules and Technical Reference

This is the project's self-contained, canonical rules reference. Unspecified
implementation details are listed under [Items to confirm](#items-to-confirm)
rather than silently resolved.

## Module naming convention

Core simulator modules use the `sim_` prefix followed by a concise lowercase
`snake_case` name describing the module's responsibility. For example,
`sim_pitch.py` contains reusable pitch functionality, `sim_physics.py` handles
physics, and `sim_tactics.py` builds simulator tactics. Demos and previews use
separate `<module>_demo.py` files and import the corresponding core module
rather than duplicating its implementation.

### Documentation standards

All code files, functions, methods, and classes should include docstrings. Use
multi-line docstrings that describe the purpose of the object and, where
applicable, list arguments and return values or side effects clearly.

### UI and graphical typography

Use the Barlow font family as the preferred typeface for user-interface and
graphical text. Use Barlow Black for prominent score numerals and Barlow
Condensed Medium for team labels where a clear typographic weight contrast is
desired. Keep changing numeric values in fixed-width or tabular cells so their
layout does not shift as digits change. Use the bundled font files and their
license in `assets/fonts/` rather than relying on system-installed fonts.

## Match at a glance

- **View:** 2D, top-down.
- **Teams:** One goalkeeper plus 4, 5, or 10 field figures (5-, 6-, or
  11-a-side).
- **Duration:** Two 15-minute halves, simulated or real-time.
- **Turn cycle:** Attacker decision and flick, physics resolution until the
  ball stops, state checks, then the next turn. The defender may make one
  block-flick after each attacking flick.
- **Possession:** Fouls, a missed attacking flick, or the ball hitting a
  stationary defender or goalkeeper can change possession.

## Project dictionary

Use these terms consistently in project discussions, documentation, and code:

| Term | Meaning |
|---|---|
| **Player** | An AI-controlled decision-maker responsible for one team's pieces. A player is not a physical figure on the pitch. |
| **Team** | One AI player and that player's goalkeeper and field pieces. |
| **Player piece** | An individual field figure controlled by a player and moved by flicking. Also called a **figure** in these rules. |
| **Goalkeeper piece** | The team's goalkeeper, controlled on a rod; distinct from a flicked player piece. |
| **Game piece** | A player piece or goalkeeper piece. Use this broader term when a rule applies to both. |
| **Attacking player / defending player** | The AI player currently in possession / the opposing AI player responding defensively. |
| **Attacking piece / defending piece** | A player piece belonging to the attacking / defending player. Use **attacking figure** or **defending figure** only as synonyms for these pieces, never for the AI player. |
| **Flick** | An impulse action taken by a player piece to contact or move the ball. A defensive block-flick is a separate defensive positioning action. |
| **Possession** | The team's right to make the next attacking flick, subject to the turn and foul rules. |
| **Shooting area** | The region strictly inside the 280 mm shooting line at the target goal. Shot eligibility is evaluated from the ball center when the flick begins. |
| **Goal mouth** | The opening between the goalposts; the only opening in the pitch perimeter. |

## Pitch and physical specifications

| Specification | Value |
|---|---:|
| Default playing-area length × width (touchlines × goal-lines) | 1,200 × 800 mm |
| Playing-area length (touchlines) | 900–1,400 mm |
| Playing-area width (goal-lines) | 600–1,000 mm |
| Playing-area width relative to length | At least 300 mm less than its length |
| Playing-area shape and division | Rectangular; a centre line divides it into two equal halves |
| Shooting-area depth at each end | 280 mm |
| Penalty-area width × depth (default render) | 390 × 150 mm |
| Goal-area width × depth | 240 × 60 mm |
| Goal width × depth × height | 120 × 60 × 40 mm |
| Center-circle radius | 120 mm |
| Penalty-spot distance from goal line (default render) | 90 mm |
| Ball radius | 11 mm |
| Player-piece base (OO scale, 1:76) | 18.5 mm diameter (9.25 mm radius) |
| Side-wall coefficient of restitution | 0.65 recommended |

The player-piece base is described as concave/rounded, allowing sliding,
spinning, and curling trajectories. These are qualitative specifications; no
additional profile dimensions or spin parameters are defined.

### Coordinates

Use normalized pitch coordinates. For the reference orientation, `X = 0` is
the team's own goal line, `X = 1` is the opponent's goal line, and `Y` runs
across the width from `0` to `1`.

- Own goal center: `(0, 0.5)`
- Center spot/circle: `(0.5, 0.5)`
- Opponent goal center: `(1, 0.5)`
- The opponent's shooting area is the final 280 mm of the pitch. If `L` is
  the playing-area length in millimeters, its normalized boundary is
  `X = 1 - 280 / L`. Reverse the X direction when evaluating the other team.

Convert normalized coordinates to pixels only at the rendering boundary.

### Pitch rendering design standard

The following is the visual gold standard for the Pygame pitch preview. Treat
these choices as intentional design requirements when recreating the pitch;
they are presentation guidance, not additional gameplay rules.

- **Default view:** A resizable 1,280 × 900 pixel window, with a 640 × 480
  pixel minimum. Center the board and preserve the 1,200:800 playing-area
  aspect ratio. Scale the board uniformly to fit inside a 24-pixel window
  margin.
- **Board and frame:** Surround the playing area with an 80 mm-wide,
  solid dark-green frame (`RGB 7, 82, 43`). Give the board corners a subtle
  radius of one fifth of the frame width. Do not draw a contrasting outline
  around the frame. Leave a dark charcoal-green background (`RGB 19, 31, 25`)
  outside the board.
- **Turf:** Use 12 alternating, full-width lengthwise bands. Start with light
  green (`RGB 27, 145, 75`) at the left goal line, alternating with dark
  green (`RGB 19, 126, 64`). Divide each 280 mm shooting area into three
  equal bands and the 640 mm middle section into six equal bands. This makes
  both shooting lines, at 280 mm and 920 mm, coincide with color boundaries.
  Compute band positions from the playing-area dimensions so the pattern
  scales with the pitch.
- **Markings:** Use a warm off-white (`RGB 242, 245, 229`) for all markings.
  Scale their width as 2.5 mm, with a minimum of 2 pixels. Draw the touchlines
  and goal lines, centered goal openings, halfway line, center circle and
  spot, both shooting lines, and the penalty and goal areas using their
  specified physical dimensions above. Use a 6 mm radius for the center spot
  and both penalty spots. Place each penalty spot 90 mm from its goal line,
  centered between the touchlines.
- **Corner arcs:** Do not draw corner arcs in the current Pygame pitch preview.
- **Goals:** Show each goal outside its goal line as a centered, dashed
  120 × 60 mm outline. Use dashes 8 mm long with 5 mm gaps, with minimum
  lengths of 3 and 2 pixels respectively. The 80 mm frame should contain the
  entire 60 mm goal depth and leave 20 mm of frame behind it.
- **Layering:** Draw the background, solid frame, alternating turf, and then
  pitch and goal markings, in that order. Do not add player pieces, a ball,
  logos, labels, or other decoration to the empty design preview.

### Score bug rendering standard

The score bug is a separate match UI element, not part of the empty pitch
design preview. Use these visual requirements when displaying match
information over the pitch:

- **Placement:** Center the score bug horizontally over the pitch, in the
  board's upper frame. Place a separate match-timer pill on the same row at
  the upper left; align its left edge with the pitch's top-left corner.
- **Score pill:** Use a compact white rounded pill with dark-green score
  numerals. Center the complete score-and-separator group inside the pill.
- **Team indicators:** Place each team's circular piece-color badge outside
  the corresponding end of the score pill, with the team name farther
  outward. Use each team's configured piece color for its badge.
- **Timer pill:** Match the score pill's white fill, rounded shape, height,
  and dark-green numerals. Show time as `MM:SS`; keep numeric cells
  fixed-width/tabular so changing digits do not shift the layout. The design
  preview may show a static `15:00`; in a match view, display the time from
  match state.
- **Typography:** Use Barlow Black for score and timer numerals and Barlow
  Condensed Medium for team labels. Team labels should be prominent but
  subordinate to the score numerals. Use the bundled fonts in `assets/fonts/`.
- **Sizing:** Use a score-bug row height of up to 38 pixels, reduced as needed
  to fit the board frame while preserving clear spacing and alignment.
- **Integration:** Keep score-bug drawing in the reusable `sim_scorebug.py`
  module, separate from match rules and state. The match view should render
  the pitch first, then call this module with scores, team names and colors,
  and remaining match time from match state. Keep `scorebug_demo.py` as a
  standalone visual preview, not the match implementation.

### Match setup piece rendering standard

The match setup is a separate view from the empty pitch design preview. Use
these visual specifications when rendering its pieces; they are presentation
guidance and do not change the nominal physical player-piece base dimensions
or gameplay rules.

- **Player pieces:** Render each as a flat, circular, two-color disc with no
  number, dot, head, or other internal marking. The outer diameter is 21 mm,
  using the visual allowance shown by the demo; the solid center disc is
  16 mm in diameter. The remaining 2.5 mm radial width is a continuous,
  contrasting border, for 21 mm total diameter.
- **Team colors:** Derive each team's center and border colors from that
  team's configured colors; do not treat the demo palette as a fixed team
  color requirement. The current demo uses a blue center (`RGB 57, 126, 224`)
  with a white border (`RGB 245, 245, 245`) for one team, and a red center
  (`RGB 218, 74, 62`) with a black border (`RGB 20, 20, 20`) for the other.
  Keep both regions flat and solid, and use the teams' configured palette
  instead of these example RGB values in other matches.
- **Goalkeepers:** Distinguish each goalkeeper with a rectangular disc using
  its team's same center and border colors. In the current top-down view, use
  an 8 mm thickness along the pitch length and a 21 mm width across the pitch.
  Inset the center color by 2.5 mm on each edge where space permits, matching
  the player-piece border. This 8 mm thickness is a deliberate visual
  compromise over the 6 mm reference thickness. For the demo setup, center
  each goalkeeper 22 mm inward from its own goal line.
- **Scaling:** Convert all piece dimensions from millimeters using the same
  uniform pitch scale; render in screen pixels only at the drawing boundary.

## Boundaries and ball-out behavior

- **Perimeter:** All pitch boundary lines behave as solid rebound walls with
  the same recommended coefficient of restitution, `0.65`.
- **Touchlines:** The ball rebounds and stays in play; a touchline rebound
  does not change possession.
- **Goal lines:** When the ball contacts either goal line, it rebounds and
  possession changes to the opposing player. This also applies when an
  ineligible attempt passes through the goal mouth: treat it as a goal-line
  rebound and change possession.
- **Goal mouth:** The opening between the goalposts is the sole exception to
  the goal-line rebound. A ball may pass through it without rebounding only to
  score under [Goals and shooting](#goals-and-shooting).
- **Goal net:** After a valid goal crosses the goal line through the goal
  mouth, the inside sides and back of the net should rebound the ball with
  stronger damping than the pitch perimeter (a lower coefficient of
  restitution than `0.65`). Choose the exact net coefficient when implementing
  the physics. These post-goal rebounds do not undo the goal.
- Traditional throw-ins, goal-line restarts, corner-flicks, and free-flicks
  are removed.

## Formations and team setup

Formations are scalable normalized-coordinate templates used for kick-offs
and tactical resets. Positions below are the source's approximate X
line-positions; except where stated, it does not specify complete Y
coordinates or exact spacing for each lineup.

### Defensive line templates

- **Flat defensive wall:** Figures are spaced evenly across the defensive
  shooting line at approximately `X = 280 / L`, where `L` is the playing-area
  length in millimeters. For 11-a-side, place 10 field
  figures across `Y = 0.10–0.90`; for 6- or 5-a-side, place 5 or 4 figures
  across approximately `Y = 0.15–0.85`.
- **Forward arrow (wedge):** The central figure is furthest forward at
  approximately `(0.35, 0.50)`; figures step back toward the wings, around
  `X = 0.18`, `Y = 0.10/0.90`.
- **Backward arrow (inverse wedge):** Wingers are forward at approximately
  `X = 0.32`, `Y = 0.10/0.90`, funneling toward a deeper central sweeper at
  `(0.15, 0.50)`.

### Scalable lineup templates

The following are field-figure counts; each team also has one goalkeeper.

| Squad | Formation | Role line positions from own goal (`X`) |
|---|---|---|
| 11-a-side | 4-4-2 (classic flat) | 4 defenders `0.18`, 4 midfielders `0.35`, 2 forwards `0.48` |
| 11-a-side | 4-3-3 (retro wingers) | 4 defenders `0.18`, 3 midfielders `0.33`, 3 forwards `0.48` |
| 11-a-side | W-M (1930s retro) | 3 defenders `0.15`, 2 deep midfielders `0.28`, 2 attacking midfielders `0.38`, 3 forwards `0.48` |
| 6-a-side | 2-2-1 (balanced) | 2 defenders `0.20`, 2 midfielders `0.35`, 1 forward `0.48` |
| 6-a-side | 2-1-2 (attacking) | 2 defenders `0.20`, 1 midfielder `0.35`, 2 forwards `0.48` |
| 6-a-side | 3-1-1 (pyramid/arrow) | 3 defenders `0.18`, 1 midfielder `0.33`, 1 forward `0.48` |
| 5-a-side | 1-2-1 (diamond) | 1 defender `0.18`, 2 midfielders at (`0.33`, `Y = 0.25/0.75`), 1 forward at (`0.48`, `Y = 0.50`) |
| 5-a-side | 2-2 (square/box) | 2 defenders `0.20`, 2 forwards `0.45` |
| 5-a-side | 3-0-1 (park the bus) | 3 defenders `0.16`, 1 forward `0.48` |

Use the active formation template for kick-off placement and possession
resets. Where a template does not specify Y positions or spacing, those
placements still need to be defined by the project.

## Turn-taking and possession

### Attacking flicks

- A figure may make up to **three consecutive flicks/touches** of the ball.
- After the third consecutive flick, the ball must touch another friendly
  figure, an opposing figure, or the opposing goalkeeper to reset that
  figure's touch counter. A fourth consecutive flick is not allowed.
- The AI guidance further says that after two touches, the next move should
  be a pass, a shot, or a soft touch against an opposing figure.
- An attacking flick that misses the ball, hits a stationary defender or
  goalkeeper, or commits a foul changes possession.

### Defensive block-flicks

- After each attacking flick, the defender may make one block-flick to
  intercept a shot or passing lane.
- A block-flick must not touch the ball or any attacking figure. If it would,
  invalidate the block and return play to the attacker.

### Fouls

When a player commits a foul or other illegal move covered by these rules,
the sanction is an immediate change of possession to the fouled team. The
fouled player takes over from the current board state: do not award a free
kick/free-flick, reset positions, or pause play for repositioning.

1. **Illegal contact:** An attacking figure hits a defender or goalkeeper
   before touching the ball.
2. **Smashing:** An attacking flick displaces two or more defending figures
   in their half, unless it is a shot on goal.

For these attacking fouls, possession transfers to the defending player.
An illegal defensive block-flick is invalidated and play returns to the
attacking player, as specified under [Defensive block-flicks](#defensive-block-flicks).

## Kick-off and restarts

- Kick-off occurs at the start of each half and after every goal.
- Place figures in their own halves using the active formation. Defenders
  must remain outside the center circle (radius 120 mm).
- At kick-off, goalkeeper pieces may occupy their own team's scoring area
  (shooting area). All field player pieces must be outside both teams'
  scoring areas.
- The attacking player takes the first impulse flick from the center spot.
  The ball may be passed backward into the attacker's own half to retain
  possession; it does not have to enter the opponent's half on the first flick.
- A ball contacting a touchline rebounds without changing possession.
- A ball contacting a goal line rebounds and transfers possession to the
  opposing player, except when it scores a valid goal.

## Goals and shooting

- A valid goal is scored only when the ball is shot from completely inside
  the target's shooting area, within 280 mm of that goal line. Judge the
  **ball's center position when the attacking flick begins**; the flicking
  figure's position does not determine eligibility. The center must be
  strictly inside the shooting area: a ball on the shooting line is outside.
  If `L` is the playing-area length in millimeters, the normalized boundary
  is `X = 1 - 280 / L`. Eligibility is `X > 1 - 280 / L` when attacking toward
  increasing X, and `X < 280 / L` when attacking toward decreasing X.
- A shot from outside or on the shooting line cannot score. If it passes
  through the goal mouth, it is treated as an ineligible attempt: the ball
  rebounds from the goal-line plane and possession changes to the opposing
  player.
- Own goals may be scored from anywhere on the pitch.

## Goalkeeper

- The goalkeeper is controlled on a rod and operates behind or within the
  goal area.
- The goalkeeper may make up to three consecutive saves/touches before
  another figure must play the ball.
- The goalkeeper must not extend past the goal-area line.

## AI decision priorities

### Attacker

Apply these priorities in order; a higher priority overrides a lower one.

1. **Score:** If the ball's center is strictly inside the opponent's shooting
   area when the flick begins (`X > 1 - 280 / L` toward increasing X;
   `X < 280 / L` toward decreasing X, where `L` is the playing-area length in
   millimeters) and there is a clear vector to the goal mouth, shoot.
2. **Keep possession and avoid fouls:** Contact the ball before any defender.
   If a direct path risks illegal contact, choose a bank shot or another
   figure. Respect the consecutive-touch limit and advance the ball by passing
   or shooting when required.
3. **Advance:** When the higher priorities permit, move the ball forward
   (`X` increasing toward the opponent's goal) or position a receiver in a
   useful forward zone.

### Defender

1. **Avoid illegal contact:** Never touch the ball or an attacking figure
   during a block-flick. Discard an invalid block.
2. **Block shots:** When the ball is in or near the shooting area, place a
   figure on the line between the ball and the center of the goal mouth.
3. **Intercept passes:** Otherwise, position a figure between the ball and
   the nearest uncontrolled attacking figure.

Within the final 280 mm, attacker priorities should favor direct or bank-shot
attempts toward goal. Raycasting for shots and passes must account for wall
rebound vectors and the wall restitution value.

## Engine state cycle

1. Decide the move.
2. Apply the flick impulse/vector.
3. Resolve physics until velocity reaches zero.
4. Check possession, goal, and foul states.
5. Continue with the next turn.

## Items to confirm

- **Formation placement:** The source gives role line positions but not all
  Y-coordinates or spacing for the scalable lineup templates. Complete these
  when the pitch and player positions are defined in more detail.
