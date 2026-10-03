# Balanced United RL — organizer training reference

This is the actual trained organizer RL opponent used by the demo tournament, not a simplified imitation. The bundled `models/balanced_united_rl.json` is an exact copy of the tournament model, and the wrapper uses the bundled official `ReinforcementPolicy` implementation and evaluation settings.

Use it as a strong fixed benchmark and curriculum opponent. It exposes one trained policy, so training only against it can overfit its state/action preferences. Final training should combine it with the other supplied styles, self-play, frozen snapshots, and unseen seeds.

Train only against Balanced United RL:

```powershell
python train_bot.py --episodes 2400 --opponents organizer-rl --self-play-ratio 0
```

Run it through the JSON-lines match protocol:

```powershell
cd participants
python -m organizer_rl_bot.bot
```

The reference model is for local training and benchmarking. Do not include this 8 MB organizer model in a final team submission unless the published competition rules explicitly allow copying organizer assets.
