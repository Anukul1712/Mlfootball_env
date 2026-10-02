# AI Soccer Arena - participant quick start

This folder contains participant-facing material: a simple training program, a clean ZIP packager, a complete starter submission, and the distributable kit. The authoritative game engine and official configuration live in the neighboring `organizers/` folder and must not be edited for final validation.

For detailed training strategy, the full observation/action protocol, validation, packaging, and event participation rules, read `participants/README_TRAINING_AND_SUBMISSION.md` after this file.

## Folder map

```text
participants/
  README.md                              this quick start
  README_TRAINING_AND_SUBMISSION.md      complete participant guide
  train_bot.py                           full-action-space RL trainer
  package_submission.py                  creates a clean submission ZIP
  submission_kit/
    README.md                            kit-specific packaging instructions
    submission.json                      team name and launch command
    requirements.txt                     approved runtime dependencies only
    team_bot/
      bot.py                             JSON Lines process loop
      policy.py                          replaceable example policy
      models/example_policy.json         example model/config file
  dist/
    ai_soccer_submission_kit.zip         ready-to-share starter archive
    ai_soccer_submission_kit_report.json successful static-check report
```

## Verify the official simulator

Run this from the repository root:

```powershell
python -m unittest discover -s organizers/tests -t organizers -v
python organizers/run_match.py
```

The tests should pass and the sample match should produce a replay below `organizers/logs/`.

Watch the sample match:

```powershell
python organizers/live_viewer.py
```

This opens a localhost page showing the same game state sent to both bots, automatic commentary, and important events.

## Start from the submission skeleton

Make a working copy so the original kit remains unchanged:

```powershell
Copy-Item -Recurse participants\submission_kit participants\my_team
```

Then:

1. Change the team name in `participants/my_team/submission.json`.
2. Replace `choose_action` in `participants/my_team/team_bot/policy.py`.
3. Place trained model files under `participants/my_team/team_bot/models/`.
4. Update the `--model` path in `submission.json`.
5. Add only organizer-approved inference dependencies to `requirements.txt`.
6. Update the submission README with your real startup requirements.

The supplied `bot.py` already reads one JSON observation per line and prints one JSON action per line. Standard output is reserved for actions; write diagnostics to standard error.

## Train the included example

Run a short smoke test:

```powershell
python participants/train_bot.py --episodes 100
```

Run a longer training job and save the model directly into your copied submission:

```powershell
python participants/train_bot.py `
  --episodes 5000 `
  --output participants/my_team/team_bot/models/trained_policy.json
```

The trainer learns movement, dribbling, kick direction, and kick power. It alternates sides, uses a unique deterministic seed each episode, and rotates between tactical, aggressive, and counter-attacking opponents. The starter submission now loads this sparse format-3 model directly and falls back to an obstacle-aware tactical policy in unfamiliar states. You may use another learning framework privately, but submitted inference dependencies must follow organizer policy.

Continue an existing training run with:

```powershell
python participants/train_bot.py `
  --episodes 2000 `
  --resume participants/my_team/team_bot/models/trained_policy.json `
  --output participants/my_team/team_bot/models/trained_policy.json
```

The event is double elimination. A first series loss moves a team into the Elimination Bracket; a second eliminates it. Organizers may select multiple games per bracket tie, with aggregate goals deciding the series.

## Validate your process

Test the skeleton or your copied submission through the actual process protocol:

```powershell
python organizers/validate_submission.py `
  --submission participants/my_team/submission.json
```

The validator automatically launches the bot from the folder containing `submission.json`. It plays on both sides and reports timeouts, malformed responses, crashes, invalid actions, and closed output. Do not submit until it reports zero participant action errors.

## Package and inspect your ZIP

Create a clean archive that excludes caches and generated folders:

```powershell
python participants/package_submission.py `
  participants/my_team `
  participants/dist/my-team.zip
```

Run the same static structure and safety check used by organizers:

```powershell
python organizers/check_submission.py `
  participants/dist/my-team.zip `
  --report participants/dist/my-team-report.json
```

Both the ZIP check and live protocol validator must pass. The checker does not execute the bot; the validator does.

## What you submit

Submit one ZIP whose root contains:

- `submission.json`;
- `README.md`;
- `requirements.txt`;
- your Python package and source;
- every model or data file needed for inference.

Do not include a virtual environment, Git directory, cache, logs, training datasets, API keys, secrets, absolute paths, or internet-dependent code.

The final ZIP must be the exact archive you validated. Keep its SHA-256 and the generated checker report.
