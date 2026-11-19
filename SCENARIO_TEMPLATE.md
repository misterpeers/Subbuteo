# AI flick scenario template

Copy this template for each scenario. Record unknown values as `unknown` rather
than guessing. Coordinates describe object centers: X increases left to right,
Y increases top to bottom. The rulers show millimeters on the 1200 x 800 mm
pitch; the position panel shows normalized coordinates and millimeters.
Displayed values are rounded, so a replay from these notes is approximate.

## Context

- Scenario name and date:
- Purpose / question for the agent:
- Repository commit or version, including any uncommitted changes:
- Mode: free-play sandbox / training
- Ball: on / off
- Window size (dragging positions is pixel-limited):
- Other relevant settings or changes:

## Starting setup

- Possession, active piece, touch counts and score, if relevant:
- Sandbox: aim mode, marker position, power percentage:
- Training without ball: maximum touches, target center and radius:
- Training with ball: right-hand goal; record any relevant prior touches:
- For each obstacle: center, width, height, and padding if known:
- For each moving dummy: center, X/Y axis, direction, speed, travel bounds,
  and timing/phase at start, if known:

| Object | Piece number / ID | X normalized | Y normalized | X mm | Y mm | Notes |
|---|---|---:|---:|---:|---:|---|
| Player piece | P1 (`ai-piece`) | | | | | |
| Player piece, if present | P2 (`ai-piece-2`) | | | | | |
| Player piece, if present | P3 (`ai-piece-3`) | | | | | |
| Ball, if enabled | Ball | | | | | |
| Other object | | | | | | |

## Sequence

Record each action in order, including manual drags, button presses, flicks,
and moving-dummy positions. For each flick record the piece number, action,
aim/target, power, and touch number if available. Record positions after each
movement has stopped, or specify the elapsed time if it has not. Include
collisions, rebounds, possession changes and on-screen messages.

| Step | Action, settings and timing | Object / piece number | X normalized | Y normalized | X mm | Y mm | Events / message |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | | | | | | | |
| 1 | Same step: other moved object | | | | | | |

Repeat rows for every affected object and step. Add screenshots or a video
reference when positions, timing, obstacle geometry or messages are difficult
to capture. Note whether any observations are estimates.

## End state

| Object / piece number | X normalized | Y normalized | X mm | Y mm | Notes |
|---|---:|---:|---:|---:|---|
| | | | | | |

- Final possession, active piece, touch counts, score and message:
- Expected result:
- Actual result:
- Difference / suspected problem:
- Reproduction frequency and any extra context:

## Replay limitations

The demo displays rounded positions, not exact internal state. Frame timing
and moving-dummy phase can affect a run, and some state or object parameters
are not exposed in the editor. Record them when known; otherwise flag them as
unknown. These notes describe a scenario but do not guarantee an exact replay.
