# AI Soccer Arena - complete participant training and submission guide

This guide explains how to build, train, test, package, and submit a bot. Start with `README.md` for the short workflow.

## 1. Competition model

There are exactly two independently controlled players and one ball. Each iteration follows this order:

1. Both bots receive the current state.
2. Both independently choose an action.
3. Both player movements are applied simultaneously.
4. The ball advances and resolves walls, obstacle rebounds, and player interceptions.
5. Tackles, possession claims, goals, and anti-stall rules are resolved.
6. The new state and any match events are recorded for the next iteration.

Your bot controls one player. It does not modify the environment and never sees the opponent's action for the current iteration.

Coordinates start at the bottom-left. Player 1 defends the bottom goal and attacks upward. Player 2 defends the top goal and attacks downward. The same physical state is sent to both bots with a player-specific identity and attack direction.

The event uses double elimination. A first series loss moves a team from the Winners Bracket to the Elimination Bracket; a second series loss eliminates it. The organizer chooses one to six games per bracket tie. Multi-game ties alternate sides and use aggregate goals. An aggregate draw is resolved by a recorded, reproducible seeded penalty shootout. A Grand Final reset is played if the previously undefeated finalist loses the first final.

## 2. Official configuration

Final training and evaluation use the bundled `config/game.json`:

- field `100 x 140`, goal width `36`;
- player radius `3`, movement speed `4`;
- ball radius `1.5`, ball speed `8`;
- possession radius `5`;
- kick distances `32`, `64`, and `96`;
- six mirrored `11 x 8` obstacles;
- at most `400` iterations and `7` total goals;
- forced ball release after `10` possession iterations;
- midfield drop-ball after `20` iterations without meaningful progress toward a stationary loose ball.

You may use easier configurations for early curriculum training, but restore the unmodified official file for final training and evaluation.

The obstacle seed changes layouts deterministically. Train on many seeds. Do not assume that organizer evaluation seeds will be public.

## 3. Observation format

Your process receives a JSON object followed by a newline:

```json
{
  "type": "observation",
  "match_id": "example123",
  "observation": {
    "player_id": "player_1",
    "opponent_id": "player_2",
    "attack_direction": "UP",
    "state": {
      "seed": 210196756,
      "iteration": 0,
      "maximum_iterations": 400,
      "players": {
        "player_1": {"x": 50.0, "y": 35.0},
        "player_2": {"x": 50.0, "y": 105.0}
      },
      "ball": {
        "x": 50.0,
        "y": 35.0,
        "status": "possessed",
        "possession": "player_1",
        "velocity": {"x": 0.0, "y": 0.0},
        "remaining_kick_distance": 0.0,
        "possession_steps": 0,
        "loose_ball_steps": 0
      },
      "score": {"player_1": 0, "player_2": 0},
      "obstacles": []
    },
    "action_space": {}
  }
}
```

The complete message also contains the deterministic match seed, field dimensions and player physics, every obstacle rectangle, termination state, and legal moves, kick directions, and powers. Read allowed values from the observation rather than hard-coding assumptions when practical.

## 4. Action format

Return exactly one JSON object and a newline:

```json
{"move":"UP_RIGHT"}
```

Legal movement values are:

- `STAY`
- `UP`, `UP_RIGHT`, `RIGHT`, `DOWN_RIGHT`
- `DOWN`, `DOWN_LEFT`, `LEFT`, `UP_LEFT`

Diagonal and straight movements have the same total speed.

When you possess the ball, you may include a kick:

```json
{"move":"UP","kick":{"direction":"UP_LEFT","power":3}}
```

The kick is ignored when you do not possess the ball. Power is an integer listed in the observation. A moving ball remains independent until its distance is exhausted, it enters a goal, or a player intercepts it. A newly won ball has a short protected control window before contact can become a tackle. Possession held too long is automatically released toward the attacking goal.

Use standard output only for action JSON. Write diagnostic logs to standard error and flush the action line immediately. Invalid, late, missing, or malformed output becomes `STAY` and is recorded as an action error.

## 5. Use the starter kit

Copy `submission_kit` to your own working folder. The important files are:

- `submission.json`: public team name and launch command;
- `team_bot/bot.py`: protocol loop; usually leave it unchanged;
- `team_bot/policy.py`: replace the example decision logic;
- `team_bot/models/`: store final inference files;
- `requirements.txt`: approved runtime packages only;
- `README.md`: document your actual startup requirements.

The starter bot predicts a moving ball, presses from the goal side, avoids immediate obstacle collisions, controls new possession, evades a nearby defender, and shoots toward goal. It can load the sparse format-3 RL model created by the included trainer, with the tactical behavior used as a safety fallback for unfamiliar states.

## 6. Train directly in the simulator

Direct engine calls are much faster than starting bot processes. From the standalone participant folder, import the bundled official engine like this:

```python
from soccer_env import GameConfig, SoccerEnv

config = GameConfig.from_json("config/game.json")
env = SoccerEnv(config)
observations = env.reset(seed=1001)

while not env.done:
    action_1 = policy_one(observations["player_1"])
    action_2 = policy_two(observations["player_2"])
    observations, info = env.step(action_1, action_2)

print(env.result())
```

`info["events"]` reports kicks, bounces, interceptions, possession, tackles, goals, restarts, possession timeouts, player contact, stopped balls, and midfield drop-balls.

The included learner runs with:

```powershell
python train_bot.py --episodes 5000
```

Its sparse format-3 model learns the full action space: movement plus kick direction and power. The curriculum includes the actual trained Balanced United RL organizer bot, the readable simple baseline, and aggressive and counter-attacking styles. It masks unsafe opening actions, alternates sides, and uses a different seed per episode. Copy the output into `team_bot/models/` and reference it from `submission.json`. Continue a checkpoint with `--resume MODEL --output MODEL`.

The actual organizer opponent lives in `organizer_rl_bot/`. Its 8 MB model is byte-for-byte identical to Balanced United RL's tournament model and uses the same inference class. Use `--opponents organizer-rl --self-play-ratio 0` to train only against it. The simpler source-readable baseline is in `reference_bot/policy.py` and is selected with `--opponents simple`. The default curriculum rotates all four supplied styles and spends 25% of episodes in shared-policy self-play. In self-play, both sides act from the same learner and both sides update it, so the model learns both attacking directions.

## 7. Reward design

A practical starting reward is:

- `+1` for scoring;
- `-1` for conceding;
- a small reward for ball progress toward the opponent goal;
- a small reward for gaining possession;
- a small penalty when the opponent gains possession.

Keep shaping rewards much smaller than the goal reward. Otherwise, a bot may learn to farm possession or movement without scoring.

Watch for reward exploits such as deliberate rebounds, repeated possession transitions, refusing risky shots, or stalling when ahead. Evaluate final policies using match outcomes, not accumulated shaping reward.

## 8. Training schedule

1. Learn movement and ball approach without obstacles.
2. Learn possession and straight shots.
3. Add official obstacles and rebounds.
4. Benchmark against Balanced United RL, then rotate all supplied styles.
5. Alternate Player 1 and Player 2 every episode.
6. Use a different seed every episode and preserve separate unseen evaluation seeds.
7. Add shared-policy self-play and older frozen snapshots of your own bot as opponents.
8. Reserve unseen validation seeds.
9. Track wins, draws, goals for/against, action errors, and decision time.
10. Select the final model using unseen validation results.

Because Player 1 starts with possession, performance must always be measured on both sides. A single match seed is deterministic, but the official bracket assigns a distinct reproducible seed to every game, including every leg of a multi-game tie.

## 9. Process-level validation

A direct policy can still fail when launched as a process because of imports, buffering, missing weights, startup time, or accidental output.

Run:

```powershell
python validate_submission.py `
  --submission my_team/submission.json `
  --matches-per-side 2
```

The descriptor's folder is used as the default working directory. Add `--working-directory PATH` only when your layout requires another directory.

Fix every participant action error. Inspect JSONL files under `logs/validation/` to find the exact iteration, raw response, and error.

Watch at least one match:

```powershell
python replay_viewer.py logs/validation/MATCH_FILE.jsonl
```

Look for circling, getting stuck on obstacles, own goals, weak defense, repeated contact, stationary possession, wasteful opening kicks, and failure to act correctly as Player 2. The referee drop-ball prevents a deadlock from consuming the rest of a match, but repeated drop-balls still indicate a poor policy.

## 10. Runtime dependencies

Training dependencies do not need to be submitted when the final policy can run without them. Keep inference requirements minimal.

The dependency allowlist is bundled in `config/submission_policy.json`. The default list is empty. A line in `requirements.txt` fails the ZIP checker unless the package name is approved.

Remote URLs, Git dependencies, editable installs, installer options, and local filesystem dependencies are rejected. Never include a virtual environment.

The static safety gate also rejects dangerous imports and calls for networking, child processes, dynamic execution, unsafe deserialization, registry access, environment access, and filesystem mutation. Pickle, Joblib, `.pt`, and `.pth` files are rejected because loading them can execute code. `submission.json` cannot override its working directory. Python source must parse successfully and remain under the published size limit.

At runtime, each response has a two-second deadline and an 8,192-byte maximum. The runner supplies a reduced environment, disables user-site packages, invokes commands without a shell, and records every action error. Passing static checks does not prove code is harmless, so the official event should also run under an offline dedicated operating-system account or isolated machine.

## 11. Package the submission

Create the archive with the clean packager:

```powershell
python package_submission.py my_team dist/my-team.zip
```

The contents of `my_team` become the ZIP root. The packager excludes common caches and generated directories.

Inspect it:

```powershell
python check_submission.py `
  dist/my-team.zip `
  --report dist/my-team-report.json
```

The static checker does not extract or execute code. It verifies structure, sizes, paths, file types, required files, model references, launch command, dependencies, common secret files, and archive integrity. It records SHA-256.

Run the live validator again on the exact folder used to create the final ZIP. Keep the ZIP unchanged after recording its hash.

## 12. Required final archive

The ZIP root must contain:

```text
submission.json
README.md
requirements.txt
your_python_package/
  __init__.py
  bot.py
  policy files
  models/
    final model files
```

Use only relative paths. The bot must run offline and must not depend on your home directory, environment variables containing secrets, cloud services, or files outside the archive.

Do not include:

- `.git`, `.venv`, `venv`, `__pycache__`, logs, or temporary files;
- training datasets, checkpoints that are not used, or experiment outputs;
- passwords, tokens, API keys, `.env`, private keys, or credentials;
- prohibited executables or installers;
- another ZIP containing the actual submission.

## 13. What happens at the event

Organizers statically inspect the original ZIP, record its hash, extract it into isolation, and validate it through the process protocol. Accepted bots are registered in the official event configuration.

Every bracket game receives a unique hidden seed and is deterministic when replayed with that seed, configuration, and action sequence. Multi-game ties alternate side assignments and are decided on aggregate goals. The first series loss moves the team into the Elimination Bracket and the second eliminates it; there is no league-points table. Aggregate ties use a deterministic seeded penalty shootout recorded in the event results.

Your submitted source and model remain frozen after the deadline. Organizers should not modify them during the event.

## Final checklist

- Official tests pass.
- Final training used the unmodified official configuration.
- Training and evaluation covered both sides and many seeds.
- Final selection used unseen validation seeds.
- Standard output contains only action JSON.
- Every action stays within the timeout.
- Protocol validation reports zero participant action errors.
- The bot runs without internet access or secrets.
- `submission.json` points to files inside the submission.
- `requirements.txt` contains only approved dependencies.
- The clean packager created the ZIP.
- The static ZIP checker passes.
- The final ZIP hash is recorded and the archive is unchanged.
