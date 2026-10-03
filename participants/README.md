# AI Soccer participant development kit

This folder is self-contained. Copy `participants/` anywhere and it still provides the official simulator, game configuration, trained organizer RL opponent, starter submission, training program, browser viewer, replay viewer, validator, safety checker, and packager. Python 3.11 or newer is the only default requirement.

## Five-minute start

Open PowerShell in this folder. If you are in the full repository first run:

```powershell
cd participants
```

Verify the standalone kit:

```powershell
python -m unittest discover -s tests -v
```

Run the starter bot against the actual Balanced United RL organizer bot:

```powershell
python run_match.py
```

Watch the same matchup live in a browser:

```powershell
python live_viewer.py
```

The terminal prints a localhost URL and normally opens it automatically. Keep the terminal open while watching. Press `Ctrl+C` to stop the web server.

## What is included

```text
participants/
  config/
    game.json                    frozen official physics and rules
    demo_match.json              editable practice matchup
    submission_policy.json       official static safety constraints
  soccer_env/                    complete standalone simulator
  viewer/                        browser field, controls, and commentary
  organizer_rl_bot/
    models/balanced_united_rl.json
    policy.py                    actual Balanced United RL wrapper
  reference_bot/                 smaller source-readable baseline
  submission_kit/                copy this to begin your team
  train_bot.py                   full-action RL curriculum trainer
  run_match.py                   headless deterministic match
  live_viewer.py                 live browser match
  replay_viewer.py               inspect saved JSONL matches
  validate_submission.py         process validation on both sides
  check_submission.py            static archive safety check
  package_submission.py          clean ZIP creator
  tests/                         standalone-kit smoke tests
```

The 8 MB model in `organizer_rl_bot/models/` is byte-for-byte identical to the demo tournament's Balanced United RL model. It uses the same local `ReinforcementPolicy` implementation as the official environment.

## 1. Create your team

Keep the original starter intact and make a working copy:

```powershell
Copy-Item -Recurse submission_kit my_team
```

Then:

1. Change the public name in `my_team/submission.json`.
2. Edit `my_team/team_bot/policy.py`, or train a compatible model.
3. Store final inference files under `my_team/team_bot/models/`.
4. Point `--model` in `my_team/submission.json` at the selected model.
5. Keep standard output exclusively for one JSON action per observation. Send concise diagnostics to standard error.

## 2. Learn against the actual organizer RL bot

Start with a short training check:

```powershell
python train_bot.py `
  --episodes 100 `
  --opponents organizer-rl `
  --self-play-ratio 0 `
  --output my_team/team_bot/models/trained_policy.json
```

Then run a useful training job:

```powershell
python train_bot.py `
  --episodes 2400 `
  --opponents organizer-rl `
  --self-play-ratio 0.15 `
  --output my_team/team_bot/models/trained_policy.json
```

Balanced United RL is a strong fixed reference, but training against only one fixed policy encourages overfitting. Final training should use the complete curriculum:

```powershell
python train_bot.py `
  --episodes 5000 `
  --opponents curriculum `
  --self-play-ratio 0.35 `
  --resume my_team/team_bot/models/trained_policy.json `
  --output my_team/team_bot/models/trained_policy.json
```

The curriculum rotates Balanced United RL, the readable baseline, aggressive attacks, and counter-attacks. During shared-policy self-play, both players use and update the learner, teaching the same model both sides of the field.

Useful options:

- `--opponents organizer-rl`: only the actual trained organizer RL bot.
- `--opponents simple`: only the small readable baseline.
- `--opponents curriculum`: every supplied opponent style.
- `--self-play-ratio 0.0` to `1.0`: fraction of episodes updating the learner from both sides.
- `--resume MODEL`: continue an existing format-3 model.
- `--seed NUMBER`: reproduce a training run.

## 3. Watch your trained model

After updating `my_team/submission.json` to reference the trained model, watch it without editing the demo configuration:

```powershell
python live_viewer.py --submission my_team/submission.json --seed 101
python live_viewer.py --submission my_team/submission.json --seed 202
python live_viewer.py --submission my_team/submission.json --seed 303
```

Add `--opponent simple` when you want the easier readable baseline instead of Balanced United RL. The same `--submission`, `--opponent`, and `--seed` options work with `run_match.py`.

Every seed deterministically changes obstacles and evaluation exploration. Different official fixtures receive different seeds.

## 4. Inspect replays

Every local match writes a complete JSONL replay under `logs/`. Open the newest replay with:

```powershell
python replay_viewer.py
```

The replay UI can pause, step, change speed, jump between important events, and show applied actions and commentary. Use it to identify:

- bad opening kicks or own goals;
- obstacle loops and repeated drop-balls;
- failure to approach a stationary ball;
- possession timeouts;
- weak Player 2 behavior;
- shots taken with a blocked lane;
- excessive action errors or `STAY` decisions.

## 5. Improve scientifically

Use this loop rather than judging one attractive match:

1. Choose separate training and evaluation seed sets.
2. Train on both player sides and multiple opponent styles.
3. Keep the old model as a frozen benchmark.
4. Evaluate old and new models on the same unseen seeds and both sides.
5. Record wins, draws, losses, goals for/against, action errors, and average decision time.
6. Watch several losses and repeated failure patterns.
7. Change one major idea at a time—state representation, reward, exploration, opponent mixture, or training duration.
8. Promote a model only when unseen evaluation improves, not merely training reward.

Good reward priorities are: goals first, then possession changes and forward ball progress. Keep shaping rewards small enough that the learner cannot earn more by circling, holding the ball, or farming tackles than by scoring.

## 6. Validate the real process

Direct training does not test imports, buffering, startup, model paths, or JSON-lines behavior. Validate the submitted process on both sides:

```powershell
python validate_submission.py --submission my_team/submission.json --matches-per-side 2
```

The result must report zero participant action errors. A timeout, crash, malformed output, oversized response, or closed stream is a failure regardless of score.

## 7. Package and run the safety check

```powershell
python package_submission.py my_team dist/my-team.zip
python check_submission.py dist/my-team.zip --report dist/my-team-report.json
```

Submit the exact ZIP that passed. Do not modify it afterward; retain the reported SHA-256.

The current gate requires:

- ZIP at most 100 MB, 250 MB expanded, 150 MB per file, 2,000 files, and 200:1 compression ratio;
- root `submission.json`, `README.md`, and `requirements.txt`;
- Python-only launch commands without a shell or working-directory override;
- valid Python source no larger than 512 KB per source file;
- no network, subprocess, registry, environment, dynamic-code, unsafe-deserialization, or filesystem-mutation capabilities prohibited by `config/submission_policy.json`;
- no executable model formats such as Pickle, Joblib, `.pt`, or `.pth`;
- no executables, native libraries, symbolic links, encrypted members, secrets, environments, caches, logs, or unsafe paths;
- only explicitly approved dependencies—the supplied kit needs none;
- one action response within two seconds and no larger than 8,192 bytes.

The organizer RL model is a training asset. Do not include that 8 MB model in your final submission unless the published rules explicitly permit copying organizer assets.

## Tournament format

The event is double elimination. A first series loss moves a team to the Elimination Bracket; a second eliminates it. A tie may contain one to six games, alternates sides, and uses aggregate goals. Aggregate draws use a recorded seeded penalty shootout. If the undefeated finalist loses the Grand Final, a reset final decides the champion.

For protocol details, reward advice, archive structure, and the final checklist, read [README_TRAINING_AND_SUBMISSION.md](README_TRAINING_AND_SUBMISSION.md).
