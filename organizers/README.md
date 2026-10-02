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

The command finds all accepted teams, opens the live browser arena, and waits for you. In the browser you can inspect the opening bracket, choose the number of games per tie, then start, pause, resume, single-step, or change match speed. Bracket status and results update after every match. Keep the terminal open. After the final result is saved, press `Ctrl+C` in the terminal to close the local dashboard server.

In the browser, click **Enable crowd sound** once. Browsers require this click before they allow sound. The live screen includes:

- a moving soccer field with both players, the ball, obstacles, and possession ring;
- a large pre-event and pre-match countdown;
- live score, iteration, commentary, standings, and fixture progress;
- a large goal announcement, a two-second goal pause, and a crowd cheer;
- a result display and four-second buildup before the next match;
- a final champion announcement.
- organizer controls for games per bracket tie, start/pause/resume, next play, and live speed.

## Try the visual event before submissions arrive

Run the included bots through the same presentation:

```powershell
python organizers/start_tournament.py --demo
```

The demo tournament contains four teams with balanced, tactical, high-press,
and counter-attacking styles, so it exercises the complete Winners Bracket,
Elimination Bracket, Grand Final, and possible reset final presentation.

Balanced United RL uses a trained Q-learning model that learns movement,
dribbling, kick direction, and kick power. Retrain it after changing the game
physics with:

```powershell
python organizers/train_reinforcement_bot.py --episodes 2400
```

New possession is action-masked to forward control touches before shooting,
and the evaluation policy falls back to the tactical baseline when its learned
advantage is too uncertain. Every generated fixture receives its own recorded,
reproducible seed—even across multi-game ties and tournaments with many teams.

This is intentionally paced like an event. It is no longer the instant terminal demo. For a quick technical check with all pauses removed, use:

```powershell
python organizers/start_tournament.py --demo --fast
```

## How long will it take?

The official format is double elimination: the first series loss moves a team to the Elimination Bracket and the second eliminates it. The default is one game per tie. A tournament has `2 × teams - 2` series, or one additional series when the Grand Final resets. Each game can run for up to 400 iterations.

| Teams | Games (one per tie) | Rough presentation time |
|---:|---:|---:|
| 2 | 2-3 | 2-4 minutes |
| 3 | 4-5 | 4-7 minutes |
| 4 | 6-7 | 6-10 minutes |
| 6 | 10-11 | 10-16 minutes |

Matches can end early at seven total goals, so actual time varies. These values create buildup while keeping the event practical.

## Change the show pacing

The simple presentation controls are in `organizers/config/tournament_settings.json`:

```json
{
  "format": "double_elimination",
  "games_per_tie": 1,
  "seeds": [101, 202, 303, 404],
  "presentation_delay_seconds": 0.08,
  "event_countdown_seconds": 5,
  "match_countdown_seconds": 3,
  "goal_pause_seconds": 2.0,
  "between_matches_seconds": 4.0
}
```

Recommended fair values are already set. Multi-game ties automatically alternate sides. If the show is too slow, change only `presentation_delay_seconds` to `0.05`. If it is too fast, use `0.12`. These timing values affect the presentation only; they do not change physics, bot observations, scores, or fairness.

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
