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

## Questions

### Q1 — Contact and collision geometry

What counts as contact between the ball and a player piece, or between two
pieces? Should collision checks use their physical shapes and radii (the ball
radius is 11 mm and the player-piece base radius is 9.25 mm), or another
definition?

**Your response: Q1: Radii is fine, no adjustment is required. Rectangle is correct for the goalkeeper,
what impact does this have on collisions/physics?**

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

### Q7 — Bank shots

When should the attacker consider a bank shot, and how should it choose one?
For example, should it compare predicted rebound paths against direct shots and
passes, or only use a bank shot when a direct route is blocked?

**Your response: TBD** 

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

### Q10 — Formation Y-coordinates

How should the unspecified Y-coordinates and spacing in the formation
templates be chosen? Should unspecified lines use even spacing across the pitch,
or do you want to specify positions for each squad and formation?

**Your response: TBD** 
