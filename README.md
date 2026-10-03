# AI Soccer Competition — Participant Development Kit

Welcome to the AI Soccer competition. This repository contains the complete participant kit needed to create, train, watch, test, validate, and package a football bot.

The participant kit is self-contained inside `participants/`. It does not require the private organizer folder.

## What is included

- The official game environment, physics, obstacles, and rules
- A starter submission bot
- The actual trained Balanced United RL organizer bot as a fixed training opponent
- A simpler source-readable opponent
- Reinforcement-learning, curriculum, and shared-policy self-play tools
- A live browser match viewer
- A replay viewer with stepping and event navigation
- Local process validation and submission safety checks
- A clean submission ZIP packager
- Detailed training and improvement guidance

Balanced United RL is supplied as a frozen reference opponent. Training does not modify its weights. Your bot can train against it, rotate through other opponents, and train its own shared policy from both sides using self-play. Keeping the organizer RL bot fixed gives every participant the same reproducible benchmark.

## Requirements

- Python 3.11 or newer
- Windows PowerShell for the commands shown below
- No third-party dependency is required by the starter kit

## Start here

Open PowerShell in the repository and enter the participant kit:

```powershell
cd participants
```

Confirm that the standalone environment works:

```powershell
python -m unittest discover -s tests -v
```

Run the starter bot against Balanced United RL and watch it in the browser:

```powershell
python live_viewer.py
```

The terminal prints a localhost address and normally opens it automatically. Keep the terminal running while viewing the match; press `Ctrl+C` when finished.

## Create your team

Copy the starter submission:

```powershell
Copy-Item -Recurse submission_kit my_team
```

Then:

1. Change the public team name in `my_team/submission.json`.
2. Edit `my_team/team_bot/policy.py`, or train a compatible model.
3. Store final model files under `my_team/team_bot/models/`.
4. Update the `--model` path in `my_team/submission.json`.
5. Keep standard output exclusively for JSON actions. Write concise diagnostics to standard error.

## Train against the organizer RL bot

Start with a short check:

```powershell
python train_bot.py `
  --episodes 100 `
  --opponents organizer-rl `
  --self-play-ratio 0 `
  --output my_team/team_bot/models/trained_policy.json
```

Then use a longer curriculum with self-play:

```powershell
python train_bot.py `
  --episodes 5000 `
  --opponents curriculum `
  --self-play-ratio 0.35 `
  --resume my_team/team_bot/models/trained_policy.json `
  --output my_team/team_bot/models/trained_policy.json
```

The curriculum rotates:

- Balanced United RL
- The simple readable baseline
- An aggressive attacking policy
- A counter-attacking policy
- Shared-policy self-play from both player perspectives

Do not evaluate progress using only training reward or one seed. Compare old and new models on the same unseen seeds, on both sides, and record match results and action errors.

## Watch your bot

After `my_team/submission.json` points to your trained model:

```powershell
python live_viewer.py `
  --submission my_team/submission.json `
  --opponent organizer-rl `
  --seed 101
```

Try several unseen seeds. Use the easier opponent when debugging basic behavior:

```powershell
python live_viewer.py `
  --submission my_team/submission.json `
  --opponent simple `
  --seed 202
```

Local matches write JSONL replays under `participants/logs/`. Inspect the newest replay with:

```powershell
python replay_viewer.py
```

## Validate and package your submission

Your process must complete matches on both sides with zero action errors:

```powershell
python validate_submission.py `
  --submission my_team/submission.json `
  --matches-per-side 2
```

Create and inspect the final archive:

```powershell
python package_submission.py my_team dist/my-team.zip
python check_submission.py dist/my-team.zip --report dist/my-team-report.json
```

Submit only `dist/my-team.zip`. Do not submit this entire development repository, the environment, training logs, or the bundled organizer RL model. Keep the SHA-256 printed by the checker and do not modify the ZIP after validation.

## Competition format

The event uses double elimination:

- The first series loss moves a team into the Elimination Bracket.
- The second series loss eliminates the team.
- A bracket tie may contain one to six games and alternates sides.
- Aggregate goals decide multi-game ties.
- Aggregate draws use a recorded seeded penalty shootout.
- A reset final is played if the previously undefeated finalist loses the first Grand Final.

Every fixture receives its own deterministic seed.

## Safety and fairness

Submissions must pass both the static archive checker and live process validation. Among other published limits, submissions may not use networking, subprocesses, shell execution, dynamic code execution, unsafe serialization, secret files, filesystem mutation, unapproved dependencies, or working-directory escapes. Action responses must arrive within two seconds and remain under 8,192 bytes.

Read the complete rules before final training or submission:

- [Participant quick-start and workflow](participants/README.md)
- [Complete training and submission guide](participants/README_TRAINING_AND_SUBMISSION.md)
- [Organizer RL reference details](participants/organizer_rl_bot/README.md)
