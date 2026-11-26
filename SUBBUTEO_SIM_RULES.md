# Subbuteo Simulator Rules and Technical Reference

This is the project's self-contained, canonical rules reference. It states
decided rules and the current implementation status. Open questions are kept
in [AI_QUERIES.md](AI_QUERIES.md), not here.

# Subbuteo game

Subbuteo is a tabletop game that recreates association football with miniature
player figures, a ball, goals, and a playing surface. Participants flick their
figures with a finger to strike the ball, pass, defend, and try to score more
goals than the opposing side. A goalkeeper is controlled separately on a rod.

This simulator models that game with two AI-controlled teams. Each AI player
chooses actions for its field pieces and goalkeeper; the pieces are the
physical figures on the pitch, not the AI players themselves. The simulation
focuses on flicks, ball and piece movement, possession, defensive responses,
and scoring, with its own explicitly stated rules where it differs from
traditional tabletop play.

## Match at a glance

- **View:** 2D, top-down.
- **Teams:** One goalkeeper plus 4, 5, or 10 field figures (5-, 6-, or
  11-a-side).
- **Duration:** Two 15-minute halves in real time. The clock runs throughout:
  while pieces and the ball move, while the AI players decide, during the
  0.10-second response window, and during pauses between flicks.
- **Turn cycle:** The attacking player flicks and physics resolves until the
  attack settles. The defending player then has a 0.10-second response window
  to move one field piece with a block-flick. If the defender does not move a
  piece, play continues without a block-flick.
- **Possession:** An attacking foul, a missed attacking flick, or the ball
  contacting a defending field piece or goalkeeper changes possession. An
  illegal defensive block-flick instead resets all attacking field-piece
  touch counts and returns play to the attacker.
- **No limit on an attack:** An attack has no maximum number of flicks; it
  continues until possession changes or a goal is scored. There is no option
  to give up: a player always makes a move.

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
| **Penalty area (18-yard box)** | The larger marked area in front of the goal. Goal-line possession transfers occur only within the overlapping goal-line spans of this area and the goal area. |
| **Goal area (6-yard box)** | The smaller marked area inside the penalty area. The ball must contact the goal-line span within both areas for possession to transfer. |
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
spinning, and curling trajectories. The current simulator uses its existing
friction model; spin and curling are future enhancements and are not currently
simulated. These are qualitative physical specifications; no additional
profile dimensions or spin parameters are defined.

For collision calculations, model the ball and field player pieces as circles
using their specified radii. Model the goalkeeper with a rectangular footprint,
not a circle. Do not assume that the 8 mm rendering thickness is its collision
thickness.

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
  and remaining match time from match state. Keep `demo_scorebug.py` as a
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
- **Player pieces and the net:** For player pieces, each goal line is a wall
  along its full width, including the goal mouth. Player pieces never enter
  the net; only the ball can.
- **Touchlines:** The ball rebounds and stays in play; a touchline rebound
  does not change possession.
- **Goal lines:** The ball rebounds when it contacts either goal line. If the
  ball's center projects onto the goal-line spans within both the penalty area
  and goal area at contact, possession transfers to the defending player (a
  goal-kick outcome in this simulation). If its projection is outside either
  span, the ball rebounds and the attacking player retains possession.
- **Goal mouth:** The opening between the goalposts is the only place where
  the ball can cross the goal-line plane into the net without rebounding from
  the goal line. Passing through the goal mouth does not by itself count as a
  goal; see [Goals and shooting](#goals-and-shooting).
- **Ineligible attempt:** A non-own-goal attempt that passes through the goal
  mouth from outside the shooting area enters the net but is not scored. It
  does not rebound from the goal-line plane; in the current simulation it is
  stopped inside the net. Possession transfers to the defending player because
  the goal mouth lies within both the goal-area and penalty-area spans. This is
  a possession change from the current board state, not a traditional
  goal-kick restart.
- **Goal net:** After a valid goal crosses the goal line through the goal
  mouth, the inside sides and back of the net should rebound the ball with
  stronger damping than the pitch perimeter (a lower coefficient of
  restitution than `0.65`). The implemented net coefficient is `0.3`. These
  post-goal rebounds do not undo the goal.
- Traditional throw-ins, corner-flicks, and free-flicks
  are removed.

## Formations and team setup

Formations are scalable normalized-coordinate templates used for kick-offs
and tactical resets. Positions below are approximate X line-positions.

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

Where a template gives no `Y` positions for a line, space that line's figures
evenly across the pitch width: for `n` figures in a line, place figure `k`
(`k = 1 … n`) at `Y = k / (n + 1)`. For example, two figures sit at
`Y = 0.33/0.67` and four at `Y = 0.2/0.4/0.6/0.8`. Explicit `Y` values in a
template take precedence. This spacing is provisional and will be reviewed in
testing.

Use the active formation template for kick-off placement and possession
resets.

### First full match

The first full match is **5-a-side** (one goalkeeper and four field figures
per team), with both teams in the **2-2 (square/box)** formation and evenly
spaced lines: defenders at `(0.20, 0.33)` and `(0.20, 0.67)`, forwards at
`(0.45, 0.33)` and `(0.45, 0.67)`, in each team's own reference orientation.
This choice is for testing and will be reviewed.

## Turn-taking and possession

### Attacking flicks

- A figure may make up to **three consecutive flicks/touches** of the ball.
- The attacking piece must contact the ball before it contacts any other game
  piece. If it contacts a teammate before the ball, possession transfers to
  the opposing player. After ball contact, collisions with other pieces are
  allowed, subject to the foul rules below.
- The attacking player may switch to another player piece at any time and does
  not need to use all three flicks with one piece. A different player piece
  may take the next flick if it can legally contact the ball, including from
  a diagonal approach.
- Prefer short, controlled flicks and nearby passes that keep the ball within
  safe reach of a friendly player piece. Among safe continuations, prefer the
  lower required flick strength, then the shorter ball movement. A longer or
  stronger flick remains valid when it is the safest way to continue
  possession; do not use power merely to maximize distance.
- After the third consecutive flick, the ball must touch another friendly
  figure, an opposing figure, or the opposing goalkeeper to reset that
  figure's touch counter. A fourth consecutive flick is not allowed.
- A setup pass may be used on a piece's final flick before switching to
  another piece; that final flick need not be the piece's third touch. Use it
  to clear the flicking piece from the ball's path and create a route for the
  next piece, especially when an ordinary forward pass is not available.
- **Touch 3 decisions:** After two touches, the third move must be one of:
  - A **shot** (if the ball is in the opponent's shooting area with a clear ray to goal)
  - A **direct pass** (a traditional pass to a teammate)
  - A **setup pass** (a short, angled nudge that angles the ball trajectory to create space and moves the flicker out of the way, allowing another player piece a clear, safe next contact without repositioning)
  
  A setup pass counts as a touch by the flicking piece; it does not reset that
  piece's touch counter. Contact between the ball and a different figure ends
  the flicking piece's consecutive-touch sequence. A receiving player piece's
  touch counter is set to zero, so its next flick is touch one.
- An attacking flick that misses the ball changes possession. If the ball
  contacts a defending field piece, whether stationary or moving, or the
  goalkeeper, possession transfers to the defending player. Resolve the
  resulting physical motion before the next attacking flick.
- There is no limit on the number of flicks in one attack.
- **Deliberate step back:** When no forward or sideways flick keeps
  possession safely, the attacker may deliberately move the ball backward,
  provided it leaves the ball where a player piece with touches left has a
  clear, legal next contact. This is the standard fallback. Riskier styles of
  play that accept a flick likely to lose possession may be added later as a
  per-team setting; they are not the default.
- **Stuck attacker:** If the attacking player has no flick that can legally
  touch the ball, it does not give up. It makes a block-flick style move with
  one field piece instead, placed to obstruct the opponent's next move. The
  move follows the block-flick constraints below: capped strength, and no
  contact with the ball or an opposing piece. Because the attacker did not
  touch the ball, this counts as a missed flick and possession transfers to the
  opposing player in the normal way. The moved piece stays where it ends.

### Defensive block-flicks

- After the attack settles, the defender may make one block-flick during the
  0.10-second response window, moving one field piece to intercept a shot or
  passing lane. The defender may also choose not to move; play then continues
  normally.
- **Where defending pieces may go:** During play, a defending piece may go
  anywhere on the pitch, including the shooting area and directly in front of
  the goal mouth, but never into the net (see
  [Boundaries and ball-out behavior](#boundaries-and-ball-out-behavior)). The
  formation and scoring-area restrictions apply only at kick-off.
- **Equal AI players:** Until player traits are introduced, the defending
  player never chooses to skip; it always makes a block-flick. If a piece
  already blocks the route it would protect, it blocks the next most useful
  route with a different piece. It does not move only when no legal
  block-flick exists.
- The block-flick action must not cause the defending piece to contact the
  ball or an attacking figure. An illegal block-flick is invalidated, play
  returns to the attacking player, and all attacking field-piece touch
  counters reset to zero.
- A legal block-flicked piece stays where its block-flick leaves it for
  subsequent play.
- The block-flick is a real flick, resolved until everything has stopped and
  then checked for legality. The 0.10-second window is the time to decide, not
  the time the movement takes.
- **Strength cap:** The cap depends on the piece's distance from the ball and
  grows with it, so a distant piece may flick harder to get back into play
  while a piece near the ball may only make a small adjustment. Starting
  values, to be tuned in testing: 20% of a full flick within 100 mm of the
  ball, rising to 60% at 400 mm or more.
- **Piece choice:** The defender moves the piece closest to the ball among
  those that can reach a legal blocking position within their cap.

### Fouls

For an attacking foul listed below, possession transfers immediately to the
defending player from the current board state. No free kick/free-flick,
position reset, or touch-count reset is awarded.

1. **Illegal contact:** An attacking figure hits a defender or goalkeeper
   before touching the ball.
2. **Teammate contact:** An attacking figure hits a teammate before touching
   the ball.
3. **Smashing:** An attacking flick displaces two or more defending figures
   in their half, unless it is a shot on goal. A defending figure counts as
   displaced if, once everything has stopped, it is 5 mm or more from where it
   stood when the flick began. A figure that is nudged and comes back to within
   5 mm does not count. The 5 mm threshold is provisional, to be reviewed in
   testing.

An illegal defensive block-flick is handled differently: it is invalidated,
possession remains with the attacking player, and all attacking field-piece
touch counters reset to zero.

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
- A ball contacting a goal line rebounds. Possession transfers only when
  the ball's center projects onto the goal-line spans within both the penalty
  area and the goal area at contact, except when it scores a valid goal.

## Goals and shooting

- A goal against the opposing team is scored only when the ball is shot from
  completely inside the target's shooting area, within 280 mm of that goal
  line. Judge the **ball's center position when the attacking flick begins**;
  the flicking figure's position does not determine eligibility. The center
  must be strictly inside the shooting area: a ball on the shooting line is
  outside. If `L` is the playing-area length in millimeters, the normalized
  boundary is `X = 1 - 280 / L`. Eligibility is `X > 1 - 280 / L` when
  attacking toward increasing X, and `X < 280 / L` when attacking toward
  decreasing X.
- A non-own-goal shot from outside or on the shooting line cannot score. If
  it passes through the goal mouth, the ball enters the net but is not counted
  as a goal; it does not rebound from the goal-line plane. Possession changes
  as specified under [Boundaries and ball-out behavior](#boundaries-and-ball-out-behavior).
- A ball entering a team's own goal is an own goal and may score from anywhere
  on the pitch, regardless of the shooting-area restriction.

## Goalkeeper

- The goalkeeper is controlled on a rod and operates behind or within the
  goal area.
- Any ball collision with the goalkeeper counts as a save/touch. The
  goalkeeper may make up to three consecutive saves/touches before another
  field player piece must play the ball. Contact between the ball and any
  field player piece resets the goalkeeper's touch count.
- The goalkeeper must not extend past the goal-area line.
- Goalkeeper behavior is not currently incorporated in the simulator; these
  rules are the target behavior for a future implementation.

## AI objectives and decision priorities

The match objective is to score more goals than the opposing team. At any
moment, one AI player is the attacker and the opposing AI player is the
defender. These roles switch when possession changes.

### Attacker

The attacking player's primary objective is to score. To do so, it should
preserve possession across turns, advance the ball toward the opponent's goal,
and create a safe opportunity to shoot from the shooting area. It may switch
field pieces at any time. Avoiding fouls and choosing controlled flicks take
priority over maximizing distance.

Apply these priorities in order; a higher priority overrides a lower one.

1. **Score:** If the ball's center is strictly inside the opponent's shooting
   area when the flick begins (`X > 1 - 280 / L` toward increasing X;
   `X < 280 / L` toward decreasing X, where `L` is the playing-area length in
   millimeters) **and** there is a clear vector to the goal mouth, shoot.
2. **Keep possession and avoid fouls:** Contact the ball before any defender.
   If a direct path risks illegal contact, choose another figure; consider a
   bank shot or bank pass only when no direct shot or pass works (see
   [Clear lanes and bank shots](#clear-lanes-and-bank-shots)). The attacking player may choose any available player piece for a
   flick; it need not use all three touches with the current piece. Prefer a
   controlled move that keeps the ball close to a teammate, selecting the
   lower required flick strength and then the least ball travel among safe
   options. A longer or stronger flick is appropriate when it is the safest
   way to continue possession; do not maximize distance for its own sake.
   
   **Touch strategy:**
   - **Touches 1-2:** Advance the ball forward with decreasing power, keeping it within safe reach of a teammate.
   - **Touch 3 (Critical decision point):** Choose one of:
     - **Shot** (if scoring conditions are met)
     - **Direct Pass** (traditional pass to a teammate)
     - **Setup Pass** (a short, angled nudge that angles the ball trajectory to create space and moves the flicker out of the way, allowing a teammate to continue possession with a clear, safe next contact)
     
     A setup pass does not reset the current piece's touch counter unless the ball touches another figure; the receiver's touch counter resets to 0 upon receiving the ball.
   - **Touch reset:** After the third consecutive flick, the ball must touch another friendly figure, an opposing figure, or the opposing goalkeeper to reset that figure's counter. Never attempt a fourth consecutive flick without this reset.
3. **Advance:** When the higher priorities permit, move the ball forward
   (`X` increasing toward the opponent's goal) or position a receiver in a
   useful forward zone.
4. **Step back:** If no safe forward or sideways move exists, make a
   deliberate step back that leaves a clear, legal next contact.
5. **Stuck:** If no flick can legally touch the ball, make a block-flick style
   move to obstruct the opponent; possession then changes (see
   [Attacking flicks](#attacking-flicks)).

### Defender

The defending player's primary objective is to prevent a goal while keeping
the block-flick legal. During the response window, it may move one field piece
to obstruct a shot or passing route. If it does not make a move, the attack
continues.

1. **Avoid illegal contact:** Never touch the ball or an attacking figure
   during a block-flick. An invalid block is discarded and resets all
   attacking field-piece touch counters to zero.
2. **Block shots:** When the ball is in or near the shooting area, place a
   figure on the line between the ball and the center of the goal mouth.
3. **Intercept passes:** Otherwise, position a figure between the ball and
   the nearest uncontrolled attacking figure.

In each case, move the piece closest to the ball that can legally reach the
blocking position within its strength cap. If a piece already blocks that
route, block the next most useful route with a different piece instead.

### Clear lanes and bank shots

- **Clear lane:** A shot or pass has a clear lane if simulating the flick with
  the real physics, on a copy of the current board, gives the intended result
  without a foul or loss of possession. The simulation accounts for every
  piece's footprint and for wall rebounds with their restitution. No separate
  minimum clearance is defined. The defender uses the same check. This rule is
  provisional and will be reviewed in testing.
- **Bank shot:** A shot or pass that deliberately rebounds off a boundary wall
  (a touchline, or a goal line outside the goal mouth) on its way to the goal
  or a teammate. The attacker considers a bank shot or bank pass only when no
  direct shot or pass has a clear lane.
- Within the final 280 mm, attacker priorities favor direct shots, then bank
  shots, toward goal.

## Engine state cycle

1. The attacking player chooses a field piece and makes a flick.
2. Apply the flick impulse and resolve physics until the attack settles.
3. Check contact, foul, possession, and goal states.
4. If play continues, give the defender a 0.10-second window to make one
   block-flick or skip the response.
5. Validate any block-flick, then continue with the next attacking flick.

If the attacker is stuck (no flick can legally touch the ball), step 1 is its
block-flick style move, and step 3 transfers possession.

Resolve competing collision events in order of time of contact rather than by
arbitrary processing order. If two events happen at exactly the same moment,
a defending piece's touch takes precedence; for example, a defender touching
the ball at the instant it reaches the goal line or goal mouth counts as a
touch by the defender. This is a future physics refinement.

## Implementation status

This section records what the code does today, so that rules above are not
mistaken for implemented behavior. See [MODULES.md](MODULES.md) for the module
guide. Core modules are named for their responsibility, not for a mode: the
training demo and the future full match both use the same physics, planner and
turn controller.

### Implemented

- **Physics:** Headless circle physics for pieces and the ball, wall and net
  rebounds, goal-line possession transfers, shooting-area goal eligibility
  (judged from the ball center when the flick begins), and own goals.
- **Attack direction:** The home team attacks toward increasing X and the away
  team toward decreasing X. The planner accepts an attack direction and mirrors
  its calculations, so both teams get identical plans for mirrored positions.
- **Attacking AI:** Per-team planning of shots, short advances, direct passes,
  and third-touch setup passes, with the three-consecutive-touch limit,
  approach paths that avoid teammates and obstacles, and the shot > setup >
  possession priority order. Shots are aimed at several points across the
  goal mouth (the center and points 20 mm and 38 mm to either side, keeping
  the ball inside the posts), and simulation picks one that scores.
- **Simulation-verified flicks:** Before a flick is used, it is simulated on a
  copy of the world through the normal physics. Flicks that miss the ball,
  strike another piece before the ball, touch an opposing piece or lose
  possession are rejected. A flick is also rejected, unless it scores, if
  afterward no piece that may flick next has a clear, in-range straight path
  to the ball. If no planner candidate survives, exploratory flicks around the
  ball are simulated, which allows sideways and backward moves when they leave
  the ball near a teammate or in the shooting area.
- **Deliberate step back and loop guard:** A flick that moves the ball more
  than 50 mm back is treated as a step back and is used only when no forward or
  sideways move survives; among step backs, one that leaves a piece behind the
  ball (ready to push it forward) is preferred. The controller remembers where
  the ball stopped earlier in the attack, and a flick that returns it within
  8 mm of one of those positions ranks after a step back. Inside the shooting
  area, progress is measured as getting closer to the goal mouth, so a ball
  pinned beside the goal is worked along the goal line toward it.
- **Lone forward lookahead:** A flick that leaves the piece in possession on
  its final touch, with no other piece within flick range of the ball, can
  only be followed by a shot. Outside the shooting area it is a dead end and
  ranks last of all (it is not forbidden). Inside the shooting area it keeps
  its rank only if simulating one flick further finds a scoring shot. When
  nothing better than a dead end exists, stronger exploratory flicks are tried
  so the piece can carry the ball into the shooting area in time.
- **Turn controller:** Touch counts, touch resets on a pass to a teammate, goal
  detection, and possession loss when a flick misses the ball, the ball
  contacts an opposing piece, or play settles with possession transferred. It
  can end the sequence on a loss (training) or hand the attack to the other
  team (match). It records how long each decision took and whether it used a
  planner candidate or a sampled fallback.
- **Scenario harness:** Seeded random attacking scenarios run headlessly to
  report goal rate, flicks per goal, outcome counts, decision statistics and
  reproducible failing seeds. Reference result, 100 seeds with three pieces:
  98% goal rate (11.7 flicks per goal for the home team, 11.8 for the away
  team) with verification, against 23% without it. With four pieces, as in a
  5-a-side team: 99% (12.5 flicks per goal).
- **Rendering:** Pitch, score bug, timer, start menu, and piece rendering.

### Not yet implemented

- **Defending:** Defender planning, the 0.10-second response window, block-flick
  validation, the distance-based strength cap, choosing the piece closest to
  the ball, and the illegal block-flick reset.
- **Stuck attacker move:** The stuck attacker's block-flick style move is not
  built; it will reuse the defender's block-flick planner.
- **Fouls in play:** Illegal contact, teammate contact before the ball, and
  smashing are not applied as rulings during a match. The verifier only uses
  the first two to reject an attacker's own candidate flicks. Smashing is not
  detected at all, and the three-touch limit is enforced by the planner.
- **Goalkeeper behavior, spin and curl, time-of-contact collision ordering.**
- **Player traits:** Both AI players are equal. Per-player traits (for
  example intelligence and risk, rated 0 to 100) are a later stage, after a
  full match works; candidate traits are logged in
  [AI_QUERIES.md](AI_QUERIES.md).
- **Clear-lane and bank-shot logic:** The geometric planner assumes straight
  ball paths. Simulation now checks the real result, including wall rebounds,
  but the planner does not deliberately propose bank shots and does not
  account for moving defenders.
- **Match flow:** Kick-off, halves, the real-time match clock, formations
  (including even `Y` spacing and the first 5-a-side 2-2 match), and restarts.
  The demo shows only an attacking sequence.
- **No-move outcome:** A sequence still ends with a `no_plan` outcome if no
  safe flick exists. This no longer happens in the reference scenarios, but the
  outcome remains in code until the stuck attacker's move is built; the rules
  allow no such outcome in a match (see "Stuck attacker"). A few slow attacks
  (2%) reach the scenario harness's 30-flick cut-off, which is a test stop
  only, not a game rule.
