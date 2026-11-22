# AI and simulation questions

This file collects decisions that are not settled by the current rules. Answer
questions in any order, one at a time or several at once. Refer to each item by
its ID.

## How to respond

Replace `Your response` under a question with your decision. You can choose an
option, provide a different rule, or write `TBD` to leave it open for now.
Where a question asks for measurements or conditions, include the units or
trigger when known. For example:

```text
Q1: Use surface-to-surface contact; the pieces collide when their bases overlap.
Q2: TBD
```

## Needs your input

Status as of the latest session. "Answered" means your decision is recorded and
no action is needed from you. "Open" means the work cannot settle it without
you. The last column says what is waiting on each one.

| ID | Topic | Status | Waiting on it |
|---|---|---|---|
| Q1 | Contact geometry, goalkeeper rectangle | Answered; your follow-up question is answered below | Goalkeeper work |
| Q2 | Ball motion, spin and curl | Answered | Nothing |
| Q3 | Simultaneous events | Answered in principle; tie-break is Q12 | Time-of-contact ordering |
| Q4 | Goalkeeper saves | Answered | Nothing (placeholder) |
| Q5 | Teammate contact and fouls | Answered | Nothing |
| Q6 | Clear shooting and passing lanes | **Open** | Defenders, attacker tuning |
| Q7 | Bank shots | **Open** | Attacker tuning |
| Q8 | Setup-pass validity | Answered; optional numeric rule is Q20 | Nothing |
| Q9 | Block-flick timing | Answered; strength cap is Q15 and skipping is Q14 | Defenders |
| Q10 | Formation Y-coordinates | **Open** | Full match |
| Q11 | Goalkeeper collision thickness | **Open** | Goalkeeper work |
| Q12 | Same-time-of-contact tie-break | **Open** | Time-of-contact ordering |
| Q13 | Defenders near the goal and shooting area | **Open** | Defenders |
| Q14 | Defender skipping a move on purpose | **Open** | Defenders |
| Q15 | Strength cap for a block-flick | **Open** | Defenders |
| Q16 | What counts as "displacing" defenders (smashing) | **Open** | Foul detection |
| Q17 | No-move fallback, repositioning and runaway attacks | **Open** | Next planned step |
| Q18 | How match time advances | **Open** | Full match |
| Q19 | Squad size and formation for the first full match | **Open** | Full match |
| Q20 | Numeric rule for a setup pass | Optional | Nothing is blocked |

Most useful to answer first: **Q17** (it is the next piece of work), then
**Q13 to Q16** (defenders), then **Q6, Q7, Q10, Q18 and Q19** (full match).

## Questions

### Q1 — Contact and collision geometry

What counts as contact between the ball and a player piece, or between two
pieces? Should collision checks use their physical shapes and radii (the ball
radius is 11 mm and the player-piece base radius is 9.25 mm), or another
definition?

**Your response: Q1: Radii is fine, no adjustment is required. Rectangle is correct for the goalkeeper,
what impact does this have on collisions/physics?**

> **AI note (answering your follow-up):** The ball and player pieces are
> circles, so they use a simple distance check. A rectangular goalkeeper needs
> a circle-against-rectangle check instead: find the nearest point on the
> rectangle to the circle's center and rebound along that direction. A hit on
> the front face rebounds straight back, and a hit near a corner rebounds
> diagonally. The goalkeeper is not flicked, so it would not need spin or
> rotation. It slides along its rod across the pitch width and stays inside
> the goal area. Today the goalkeeper is still a circle that does not move.
> The one open choice is the rectangle's thickness, see Q11.

### Q2 — Ball motion and settling

What should slow the ball and determine when it has stopped (for example,
rolling friction and a velocity threshold)? Should spin or curve be simulated
now, or treated as a later enhancement?

**Your response: Q2: No adjustment is required. Spin and curls will be implemented later.** 

### Q3 — Simultaneous events

If a single physics step could count as more than one event—for example, a goal
and a figure collision, or contact with multiple figures—which event takes
precedence? If there is no special precedence, should the simulator resolve
events in their actual time-of-contact order?

**Your response: Q3: Yes, time-of-contact. Add a placeholder to the rules to be 
implemented later.** 

> **AI note:** Not implemented yet. Contacts are still recorded per step as
> sets, so which one happened first is unknown within a step. Q12 asks for the
> tie-break.

### Q4 — Goalkeeper saves

What makes a ball contact a goalkeeper save: any collision with the goalkeeper,
or only contact while the ball is in a specified area or direction? Does a save
count as one of the goalkeeper's three consecutive touches, and what event
resets that count?

**Your response: Q4: Any collision with the goalkeeper. A save does count as a touch, the goalkeepers 
touch count resets the same way as other player pieces; contact with any other player piece. 
Goalkeeper behaviour is not currently incorporated.
Add as a placeholder for now.** 

### Q5 — Flicking-piece movement and teammate contact

Can a flicking piece collide with or move a teammate while approaching the
ball? If so, is that legal, and can the teammate's movement affect possession
or touch counts?

**Your response: Q5: No, an attacking player piece can not collide with anything before making contact with
the ball, after contact with the ball collisions with other pieces is allowed. The sanction for an attacker hitting a teammate before reaching the ball is a change of possession to the opposing team. 
A defender must not touch the ball or an opposing
player's player piece at all. Once the moving ball (hit by the attacker) hits a stationary or moving defending figure (or the goalkeeper), the defender immediately becomes the new attacker and takes over play.** 

### Q6 — Clear shooting and passing lanes

How should the AI decide that a shot or pass has a clear path? Should it test
the ball's full path against the physical footprints of figures and the
goalkeeper, including any expected wall rebounds, or use another rule?

**Your response: TBD** 

> **Current state:** The attacker no longer relies on a geometric lane test
> alone. Each candidate flick is simulated on a copy of the world with the real
> physics, so it already accounts for the footprints of every piece and for
> wall rebounds, and it rejects any flick that hits another piece before the
> ball or loses possession. The geometric planner still assumes straight
> paths when it proposes flicks. **Decision needed:** is "simulate it and see"
> acceptable as the rule, or do you want an explicit lane rule written down
> (for example, a minimum clearance in millimetres from other pieces)? The same
> choice applies to the defender, which will use the same check.

### Q7 — Bank shots

When should the attacker consider a bank shot, and how should it choose one?
For example, should it compare predicted rebound paths against direct shots and
passes, or only use a bank shot when a direct route is blocked?

**Your response: TBD** 

> **Current state:** The planner does not propose bank shots on purpose. The
> exploratory flicks can produce a rebound by accident, and simulation would
> accept it if the result is good. **Decision needed:** should bank shots be a
> deliberate option, and if so, only when the direct route is blocked, or
> compared with direct shots whenever both are available?

### Q8 — Setup-pass validity

What makes a setup pass distinct from an ordinary short pass? Must it travel a
minimum distance or create a clear next contact for a different friendly piece,
or are those tactical goals rather than strict validity conditions?

**Your response: Q8: A setup pass is typically used on a player piece's last flick and is
primarily used to touch the ball and ensure they move out of the way of the ball to allow
the next player piece a clear route. Last flick doesn't always mean third flick, a player may decide to change 
player pieces before reaching the three flick cap. An ordinary pass is used to move up the pitch, whereas 
as setup pass is used to set up play with another player piece, it is used when either a player piece is on their final touch
or they are in a position where they cannot make an ordinary pass. ** 

> **Current state:** Implemented as a short third-touch nudge (15 or 30 mm of
> ball movement) that leaves another piece a clear next contact. No numeric
> rule is enforced beyond that. See Q20 if you want one.

### Q9 — Defensive block-flick timing

At what point after an attacking flick does the defender make the block-flick:
after the ball has fully stopped, or at another point in the turn? Does the
block-flicked piece remain where it ends for subsequent play?

**Your response: Q9: Retain current set up, block-flick happening after the attack settles. There is no set wait time in
official Subbuteo but for the purposes of the simulation I am incorporating a 0.10 second period between attacking plays. The 
defender should use this time to make their move.
To clarify the 0.10 seconds is a pause between attacking plays, but the defender is able to move one player piece during this time.
If they don't make a move the play countines as normal, though I wouldn't expect to see it in a simulator unless its a forced trait of
a lower skilled team for example.** 

> **Current state:** Not implemented yet. The agreed design is that the
> block-flick is a real flick, resolved until everything stops, and then
> checked for legality. Because 0.10 seconds is too short for a flick to
> finish, I treat it as the time the defender has to decide, not the time the
> movement takes. The block-flicked piece stays where it ends. Q14 asks how a
> weaker team skips a move, and Q15 how hard a block-flick may be.

### Q10 — Formation Y-coordinates

How should the unspecified Y-coordinates and spacing in the formation
templates be chosen? Should unspecified lines use even spacing across the pitch,
or do you want to specify positions for each squad and formation?

**Your response: TBD** 

### Q11 — Goalkeeper collision thickness

The goalkeeper is a rectangle. Its width across the pitch is 21 mm. Its
thickness along the pitch length is undecided: the reference is 6 mm, and the
drawing uses 8 mm as a visual compromise. Which should the collision shape use?

**Your response: TBD** 

### Q12 — Same-time-of-contact tie-break

You chose time-of-contact order for simultaneous events (Q3). If two events
happen at exactly the same moment, which wins? For example, the ball reaches
the goal line at the same instant a defender touches it. Options: a goal always
wins; a defender touch always wins; or the order they appear in the list of
pieces.

**Your response: TBD** 

### Q13 — Defenders near the goal and in the shooting area

There is no goalkeeper in training yet. In the first defender drill, may a
defender stand inside the shooting area or in front of the goal mouth? If so,
may it fully block the mouth? The suggested default is yes, anywhere on the
pitch except overlapping another piece, so the drill shows whether the attacker
can still find a lane.

**Your response: TBD** 

### Q14 — A defender skipping a move on purpose

You mentioned that a lower-skilled team might not use its block-flick. How
should this be set? For example, a skill value per team from 0 to 1 giving the
chance of skipping each response, or a fixed list of settings such as
"always responds", "sometimes responds" and "rarely responds". Should the
choice be random (with a fixed seed so runs repeat) or follow a rule?

**Your response: TBD** 

### Q15 — Strength cap for a block-flick

A block-flick is a capped-strength flick. What cap should it have, as a
percentage of a full flick? A low cap keeps it a positioning move, while a high
cap lets a defender cross much more of the pitch. The suggested starting point
is 50%.

**Your response: TBD** 

### Q16 — What counts as "displacing" defenders

The smashing foul applies when an attacking flick displaces two or more
defending figures in their half, unless it is a shot. How far must a defender
move to count as displaced: any movement, or a minimum distance such as 5 mm?
Does a piece that is nudged and then comes back count? The suggested default is
a minimum of 5 mm from its start position when everything has stopped.

**Your response: TBD** 

### Q17 — No-move fallback, repositioning and runaway attacks

This is the next piece of work. Out of 100 test attacks, 18 end because no safe
flick exists, and 8 run to the 30-flick limit without scoring. Please decide:

1. **Order of fallbacks** when no safe flick exists. The suggested order is: a
   deliberate step back that leaves the ball near another piece, then a riskier
   flick that may lose possession, then ending the attack.
2. **Repositioning:** may a piece move without touching the ball when the
   attacker is stuck? The rules do not describe this, so the answer is no unless
   you say otherwise.
3. **Runaway attacks:** should there be a maximum number of flicks in one
   attack before possession passes to the other team? If so, how many? Real
   Subbuteo has no such limit, but the simulator needs a safety stop. The
   suggested default is 30 flicks.

**Your response: TBD** 

### Q18 — How match time advances

For the 15-minute halves, does the clock run while the ball and pieces are
moving, during the 0.10-second response window, and during the pauses between
flicks? Or does each flick cost a fixed amount of match time? Is the clock
based on real time or on simulated time?

**Your response: TBD** 

### Q19 — Squad size and formation for the first full match

Which squad size and formation should the first full match use: 5-a-side,
6-a-side or 11-a-side? The suggested start is 5-a-side, because it has the
fewest pieces and the fastest decisions. It needs a decision on which template
to use, for example 2-2 (square), and the Y-coordinates in Q10.

**Your response: TBD** 

### Q20 — Numeric rule for a setup pass (optional)

You described a setup pass in words (Q8). Do you want a numeric rule as well,
for example the ball must move at least 10 mm and no more than 60 mm, or must
end within a stated distance of another piece? Skipping this is fine; the
current behaviour is described under Q8.

**Your response: TBD** 
