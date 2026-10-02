# AI Soccer Arena submission kit

Copy this folder, replace the example policy with your trained bot, and submit the contents as one ZIP archive. Do not place the outer `submission_kit` directory inside the ZIP; `submission.json` and this README must be at the ZIP root.

## Required structure

```text
submission.json
README.md
requirements.txt
team_bot/
  __init__.py
  bot.py
  policy.py
  models/
    example_policy.json
```

You may rename `team_bot`, but update the module and model paths in `submission.json` when you do.

## Replace the example information

1. Set your final public team name in `submission.json`.
2. Put your decision logic in `team_bot/policy.py`, or import your own policy module from there.
3. Put trained weights under `team_bot/models/`.
4. Update the `--model` path in `submission.json`.
5. Add only organizer-approved runtime packages to `requirements.txt`.
6. Keep diagnostic output on standard error. Standard output must contain only one action JSON line for each observation.

The supplied `bot.py` already handles argument parsing, JSON Lines input, match-end messages, JSON output, and flushing. `policy.py` can directly load the sparse format-3 model produced by `participants/train_bot.py`; unseen states use an obstacle-aware tactical fallback. You can replace this policy with your own implementation.

The current protocol includes `possession_steps` and `loose_ball_steps` in the ball state. Holding possession for ten iterations forces a forward release. If neither player makes progress toward a stationary loose ball for twenty iterations, the referee moves it to midfield. Do not build a strategy around stalling.

From the repository root, train a compatible RL model directly into a copied kit:

```powershell
python participants/train_bot.py --episodes 2400 --output participants/my_team/team_bot/models/trained_rl.json
```

Then change the `--model` value in your copied `submission.json` to `team_bot/models/trained_rl.json`.

## Test the folder before packaging

From the repository root, temporarily point a local match configuration at your bot:

```json
{
  "name": "Your Team Name",
  "command": ["python", "-m", "team_bot.bot", "--model", "team_bot/models/example_policy.json"]
}
```

Run protocol validation from the directory that contains your `submission.json` and `team_bot` folder, or copy the folder into a clean validation workspace:

```powershell
python organizers/validate_submission.py --submission participants/submission_kit/submission.json
```

Your bot must finish matches on both sides with zero action errors.

## Create the ZIP on Windows

From the repository root, run the supplied clean packager. It excludes Python caches and common generated folders while preserving the required directory structure:

```powershell
python participants/package_submission.py participants/submission_kit participants/dist/your-team-name.zip
```

Then run the static archive checker from the organizer repository:

```powershell
python organizers/check_submission.py participants/dist/your-team-name.zip --report participants/dist/your-team-name-report.json
```

The checker does not extract or execute your code. It verifies archive paths, size limits, file types, launch command, model paths, dependency allowlist, and common secret files. Passing the ZIP checker does not replace the live protocol validator; both checks must pass.

## Final checklist

- `submission.json` and `README.md` are at the ZIP root.
- The team name and command are final.
- The launch module and model path exist inside the ZIP.
- The bot needs no internet connection, secret, or absolute path.
- No virtual environment, Git directory, cache, logs, or training dataset is included.
- `requirements.txt` contains only approved runtime dependencies.
- The model is the exact version tested.
- The ZIP checker passes.
- The live validator completes both sides with zero action errors.
