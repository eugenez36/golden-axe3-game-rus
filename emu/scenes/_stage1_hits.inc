# Stage 1 is running (HP is initialised about 200 frames after the last START):
# take three enemy hits (C = attack, used to provoke contact), then let the HUD
# health bar settle. Include after `wait 200`, optionally with a poke in between.
press c 8
wait 40
press c 8
wait 40
press c 8
wait 90
