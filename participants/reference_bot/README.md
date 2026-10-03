# Simple readable training baseline

This deliberately simple, readable baseline predicts a moving ball by one step, avoids immediate obstacle collisions, presses from the goal side, carries possession briefly, evades a nearby defender, and shoots forward.

It is not Balanced United RL. The actual trained organizer RL opponent is in `organizer_rl_bot/`. Use this smaller bot only when you want easily readable behavior for debugging rewards and actions.

Run it through the same JSON-lines protocol with:

```powershell
cd participants
python -m reference_bot.bot
```
