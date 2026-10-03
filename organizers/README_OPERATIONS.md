# AI Soccer Arena - complete organizer operations guide

This is the detailed operating procedure for preparing and conducting the competition. Use `organizers/README.md` for everyday commands.

## 1. Establish the official release

1. Run `python -m unittest discover -s organizers/tests -t organizers -v`.
2. Review `organizers/config/game.json` and confirm every numerical value.
3. Keep the finalized configuration unchanged for qualification and finals.
4. Publish the participant protocol and development configuration from this repository.
5. Publish a small set of development seeds. Keep evaluation seeds private.
6. Record a Git commit or SHA-256 of the released configuration and engine.
7. Confirm the double-elimination format and games-per-tie setting in the event configuration.

The same seed, starting state, configuration, and action sequence must always produce the same result. If an engine fix becomes necessary after release, version it explicitly and rerun every affected qualification match.

## 2. Decide submission and machine policy

Before teams begin, publish:

- submission deadline and timezone;
- maximum ZIP, expanded, file, and model sizes;
- approved runtime dependencies;
- Python version;
- CPU, memory, process, and response-time limits;
- whether compiled extensions or GPU use are allowed;
- prohibition on network access and secrets;
- ranking and tie-break rules;
- games per bracket tie, unique hidden fixture seeds, aggregate scoring, and penalty tie-breaks;
- dispute deadline and replay publication policy.

Edit `organizers/config/submission_policy.json` to match those published rules. Its `allowed_dependencies` list is empty by default, meaning submitted inference code must use the standard library. Add exact approved package names before accepting entries if the event permits them.

The supplied process runner enforces the action timeout and protocol. It is not an operating-system security sandbox. Run untrusted submissions inside separate containers, restricted users, or equivalent isolation with no network access for a public event.

## 3. Receive a submission safely

Keep the original ZIP unchanged. Give it a stable filename containing a team identifier and submission timestamp, then copy it to `organizers/incoming/`. Put every received ZIP in this one inbox; do not extract it manually.

Process the complete inbox:

```powershell
python organizers/accept_submissions.py
```

The command performs static inspection and two live protocol-validation matches before accepting a team. Passing code is installed under `organizers/submissions/TEAM-SLUG/`, the unchanged ZIP moves to `organizers/submission_archives/`, and the SHA-256 report is saved under `organizers/reports/`. Failed ZIPs stay in the inbox. Return those to their teams with the reported errors.

The checker rejects:

- `..`, absolute paths, backslashes, and case-colliding names;
- symbolic links and encrypted ZIP members;
- configured size, count, and compression-ratio violations;
- executable scripts and secret-bearing filenames prohibited by policy;
- virtual environments, Git folders, caches, logs, and temporary directories;
- missing root `submission.json`, `README.md`, or `requirements.txt`;
- missing Python launch modules, scripts, or `--model` files;
- shell control characters in the launch command;
- working-directory overrides, invalid Python syntax, dangerous imports/calls, and filesystem mutation;
- executable serialization formats such as Pickle, Joblib, `.pt`, and `.pth`;
- remote, local-path, editable, or unapproved dependencies.

Static inspection never proves code is safe. The intake command uses a temporary validation area, but the participant process still needs operating-system or container isolation for a public event.

## 4. Validate the bot protocol

For an extracted submission:

```powershell
python organizers/validate_submission.py `
  --submission organizers/submissions/team/submission.json `
  --working-directory organizers/submissions/team `
  --matches-per-side 2 `
  --seed 7000 `
  --timeout 2.0
```

Validation checks real process startup and JSON Lines behavior. It runs the participant against the official practice bot on both sides. Review every reported action-error count. A timeout, crash, closed output, malformed JSON, or invalid response is a failure even when the final score is acceptable.

Open at least one replay visually to detect strategic failures that protocol checks cannot find:

```powershell
python organizers/replay_viewer.py organizers/logs/validation/MATCH_FILE.jsonl
```

Confirm that the bot:

- returns exactly one action for each observation;
- writes diagnostic information only to standard error;
- does not depend on internet access, the submitter's home directory, or absolute paths;
- loads its model from the submitted folder;
- behaves from both player perspectives;
- stays within the published timeout and resource limits.

## 5. Register accepted competitors

Registration is automatic. Every immediate folder under `organizers/submissions/` that contains a root `submission.json` becomes one competitor. The launcher reads its team name, command, and working directory. Do not add competitors to `event.json` manually.

For example, the intake command creates a layout like this:

```text
organizers/submissions/
  team-falcon/submission.json
  blue-strikers/submission.json
```

Team names in the descriptors must be unique because standings use names as identifiers. `start_tournament.py` stops with a clear error when fewer than two teams exist or when names collide.

The event uses double elimination and automatically alternates sides in multi-game ties. For many competitors, estimate the fixture range before event day:

```text
minimum matches = (2 x teams - 2) x games per tie
maximum matches = (2 x teams - 1) x games per tie  # reset final required
```

## 6. Conduct a dry run

1. Confirm that the intended team folders are present in `organizers/submissions/`.
2. Temporarily select one game per tie and shorten presentation delays if a shorter dry run is needed; restore the official settings afterward.
3. Run `python organizers/start_tournament.py --fast` for an unpaced technical dry run.
4. Confirm every process starts and no action errors appear.
5. Check the dashboard, final standings, and event result JSON.
6. Open several replays, including matches with goals, bounces, interceptions, and restarts.
7. Deliberately validate a malformed example to confirm failure handling and logs.
8. Estimate total event duration and disk usage.
9. Restart the event machine and repeat one match from a recorded seed.

Do not use dry-run outcomes as final standings.

## 7. Freeze event inputs

Before the official run:

- stop accepting replacement files;
- hash every submission ZIP and extracted runtime folder;
- freeze `game.json`, `tournament_settings.json`, every accepted submission, the engine, and Python environment;
- back up the private seed list;
- ensure sufficient disk space;
- close unrelated heavy software;
- disable network access for participant processes;
- synchronize the system clock and record the timezone;
- create an empty official output directory.

Never edit competitor code or models during the event. If a submission fails, apply the published failure rule consistently.

## 8. Run the official event

Start the dashboard:

```powershell
python organizers/start_tournament.py
```

The launcher discovers accepted submissions and generates `organizers/config/generated_event.json`; this records the exact resolved inputs for that run. Keep the terminal visible. The browser dashboard is a presentation layer; the terminal process runs the event. Do not close the terminal until the final standings and result paths are printed.

The dashboard shows one active match because the official runner executes fixtures sequentially. It updates score and iteration during the match, then moves the fixture to completed and recalculates standings.

If the dashboard browser closes, reopen the localhost URL printed in the terminal. If the terminal process stops unexpectedly, preserve existing logs before investigating. Do not manually invent missing match results.

## 9. Understand scoring and termination

A match ends when it reaches `maximum_iterations` or the configured total-goal limit. A bracket tie is decided by aggregate goals across the configured games per tie. If aggregate goals are level, the recorded seeded penalty shootout decides the series.

The tournament uses double elimination. A first series loss moves a team from the Winners Bracket to the Elimination Bracket. A second series loss eliminates it. If the undefeated finalist loses the first Grand Final, a reset final decides the champion.

## 10. Review a dispute

Each JSONL replay contains:

1. `match_start` with seed, exact configuration, competitors, obstacles, and initial state;
2. one `iteration` record per turn with state before, raw responses, action errors, normalized actions, events, and state after;
3. `match_end` with score, winner, iteration count, termination reason, and error counts.

Use `python organizers/replay_viewer.py PATH_TO_REPLAY` to inspect important-event markers and commentary. For a technical dispute, compare the raw action, normalized action, error field, and next state in the JSONL record. The visual viewer is explanatory; the JSONL record is authoritative.

Reproduce a match only with the exact frozen engine, configuration, submission files, seed, and action sequence. Document any rerun and keep the original result.

## 11. Close and archive the event

After completion:

1. Verify that the number of completed fixtures equals the scheduled total.
2. Confirm `standings.csv` agrees with `event_results.json`.
3. Check logs for action errors and unexpected process exits.
4. Copy the entire official log directory to read-only storage.
5. Archive configuration files, code revision, Python version, submission ZIPs, reports, and hashes.
6. Publish standings and permitted replays.
7. Keep private seeds confidential if they may be reused; preferably never reuse them.
8. Record any incident and the rule used to resolve it.

The organizer archive should be sufficient for an independent reviewer to explain every score and reproduce every deterministic state transition.
