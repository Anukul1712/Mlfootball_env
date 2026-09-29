# AI Soccer Arena - organizer quick start

You do not need to edit `config/event.json` or type team commands by hand. Use this exact workflow from the repository root, the folder containing `organizers/` and `participants/`.

## The whole event in three steps

### 1. Collect the teams

Ask every team for the ZIP created by the participant submission kit. Copy all received ZIP files directly into:

```text
organizers/incoming/
  team-falcon.zip
  blue-strikers.zip
  robot-united.zip
```

Do not extract the ZIPs yourself and do not put them in `config/`.

### 2. Check and install every team

Run:

```powershell
python organizers/accept_submissions.py
```

For each ZIP, this command:

1. checks its paths, files, size, dependencies, model, and launch command;
2. safely extracts it to a temporary folder;
3. runs it against the official practice bot from both sides;
4. installs a passing team under `organizers/submissions/TEAM-NAME/`;
5. moves the original ZIP to `organizers/submission_archives/`;
6. saves its check report under `organizers/reports/`.

Failed ZIPs remain in `organizers/incoming/` so you can return them to the team. A passing inbox becomes empty. Do not edit accepted team folders.

Open `organizers/submissions/` and confirm there are at least two team folders. Each folder must contain `submission.json` at its top level. That is all the registration the tournament needs.

### 3. Start the complete tournament

Run one command:

```powershell
python organizers/start_tournament.py
```

The command finds all accepted teams, creates the round robin automatically, opens the live browser arena, runs every match, updates standings, and saves every result. Keep the terminal open. After the final result is saved, press `Ctrl+C` in the terminal to close the local dashboard server.

In the browser, click **Enable crowd sound** once. Browsers require this click before they allow sound. The live screen includes:

- a moving soccer field with both players, the ball, obstacles, and possession ring;
- a large pre-event and pre-match countdown;
- live score, iteration, commentary, standings, and fixture progress;
- a large goal announcement, a two-second goal pause, and a crowd cheer;
- a result display and four-second buildup before the next match;
- a final champion announcement.

## Try the visual event before submissions arrive

Run the included bots through the same presentation:

```powershell
python organizers/start_tournament.py --demo
```

This is intentionally paced like an event. It is no longer the instant terminal demo. For a quick technical check with all pauses removed, use:

```powershell
python organizers/start_tournament.py --demo --fast
```

## How long will it take?

The official defaults use four seeds and swap sides, producing eight matches for every pair of teams. Each match can run for up to 400 iterations. At the presentation speed of `0.08` seconds per iteration, a full length match takes about 32 seconds, plus countdowns and goal pauses.

| Teams | Pairings | Matches | Rough presentation time |
|---:|---:|---:|---:|
| 2 | 1 | 8 | 5-7 minutes |
| 3 | 3 | 24 | 15-20 minutes |
| 4 | 6 | 48 | 30-40 minutes |
| 6 | 15 | 120 | 75-100 minutes |

Matches can end early at seven total goals, so actual time varies. These values create buildup while keeping the event practical.

## Change the show pacing

The simple presentation controls are in `organizers/config/tournament_settings.json`:

```json
{
  "seeds": [101, 202, 303, 404],
  "swap_sides": true,
  "presentation_delay_seconds": 0.08,
  "event_countdown_seconds": 5,
  "match_countdown_seconds": 3,
  "goal_pause_seconds": 2.0,
  "between_matches_seconds": 4.0
}
```

Recommended fair values are already set. Keep all four seeds and `swap_sides: true`. If the show is too slow, change only `presentation_delay_seconds` to `0.05`. If it is too fast, use `0.12`. These timing values affect the presentation only; they do not change physics, bot observations, scores, or fairness.

The official game rules and physics are in `organizers/config/game.json`. Do not change that file after participants start training.

## Where results go

Every start creates a separate timestamped directory:

```text
organizers/logs/tournaments/YYYY-MM-DD_HH-MM-SS/
  standings.csv
  event_results.json
  match_...jsonl
```

Keep that whole directory after the event. `standings.csv` is the final table, `event_results.json` contains match summaries, and every `.jsonl` file is a complete replay and audit record.

Open a saved match later with:

```powershell
python organizers/replay_viewer.py organizers/logs/tournaments/TIME_FOLDER/match_FILE.jsonl
```

## Before event day

Run the automated checks once:

```powershell
python -m unittest discover -s organizers/tests -t organizers -v
```

Then run `python organizers/start_tournament.py --demo` on the event computer, test full-screen display or projector output, click the sound button, and confirm that the field animates smoothly. Use Chrome or Edge at normal zoom. Keep the machine awake and close heavy background programs.

For security policy, disputes, dry runs, and archiving, read `organizers/README_OPERATIONS.md`.
