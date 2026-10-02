const eventName = document.getElementById("event-name");
const eventStatus = document.getElementById("event-status");
const progressValue = document.getElementById("progress-value");
const progressBar = document.getElementById("progress-bar");
const activeMatch = document.getElementById("active-match");
const announcement = document.getElementById("announcement");
const countdown = document.getElementById("countdown");
const commentary = document.getElementById("commentary");
const standings = document.getElementById("standings");
const fixtures = document.getElementById("fixtures");
const errorBox = document.getElementById("error");
const canvas = document.getElementById("tournament-field");
const placeholder = document.getElementById("pitch-placeholder");
const soundToggle = document.getElementById("sound-toggle");
const roundsSelect = document.getElementById("rounds");
const speedSelect = document.getElementById("match-speed");
const startButton = document.getElementById("start-event");
const pauseButton = document.getElementById("pause-event");
const stepButton = document.getElementById("step-event");
const controlStatus = document.getElementById("control-status");
const fixtureCard = document.getElementById("fixture-card");
const fixtureHome = document.getElementById("fixture-home");
const fixtureAway = document.getElementById("fixture-away");
const fixtureCardMeta = document.getElementById("fixture-card-meta");
const ctx = canvas.getContext("2d");

let latestState = null;
let soundEnabled = false;
let audioContext = null;
let lastGoalKey = "";
let pendingRounds = null;

function resizeCanvas() {
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  if (latestState) drawField(latestState);
}

function drawField(state) {
  latestState = state;
  placeholder.hidden = true;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  const field = state.field;
  const pad = Math.max(16, Math.min(w, h) * 0.04);
  const scale = Math.min((w - 2 * pad) / field.width, (h - 2 * pad) / field.height);
  const fw = field.width * scale;
  const fh = field.height * scale;
  const left = (w - fw) / 2;
  const top = (h - fh) / 2;
  const bottom = top + fh;
  const point = (x, y) => [left + x * scale, bottom - y * scale];
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#15803d"; ctx.fillRect(left, top, fw, fh);
  for (let stripe = 0; stripe < 10; stripe += 2) {
    ctx.fillStyle = "rgba(255,255,255,.035)"; ctx.fillRect(left, top + stripe * fh / 10, fw, fh / 10);
  }
  ctx.strokeStyle = "#f8fafc"; ctx.lineWidth = 2; ctx.strokeRect(left, top, fw, fh);
  ctx.beginPath(); ctx.moveTo(left, top + fh / 2); ctx.lineTo(left + fw, top + fh / 2); ctx.stroke();
  ctx.beginPath(); ctx.arc(left + fw / 2, top + fh / 2, 9 * scale, 0, Math.PI * 2); ctx.stroke();
  const goalWidth = field.goal_width * scale;
  const goalX = left + (fw - goalWidth) / 2;
  const goalDepth = Math.max(7, 4 * scale);
  ctx.strokeRect(goalX, top - goalDepth, goalWidth, goalDepth);
  ctx.strokeRect(goalX, bottom, goalWidth, goalDepth);
  for (const obstacle of state.obstacles) {
    const [x, y] = point(obstacle.x, obstacle.y + obstacle.height);
    ctx.fillStyle = "#475569"; ctx.fillRect(x, y, obstacle.width * scale, obstacle.height * scale);
    ctx.strokeStyle = "#cbd5e1"; ctx.lineWidth = 1; ctx.strokeRect(x, y, obstacle.width * scale, obstacle.height * scale);
  }
  for (const [id, player] of Object.entries(state.players)) {
    const [x, y] = point(player.x, player.y);
    const radius = Math.max(8, 3 * scale);
    if (state.ball.possession === id) {
      ctx.beginPath(); ctx.strokeStyle = "#fde047"; ctx.lineWidth = 4; ctx.arc(x, y, radius + 6, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.beginPath(); ctx.fillStyle = id === "player_1" ? "#2563eb" : "#f97316";
    ctx.strokeStyle = "white"; ctx.lineWidth = 2; ctx.arc(x, y, radius, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "white"; ctx.font = "700 13px Segoe UI"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(id === "player_1" ? "1" : "2", x, y);
  }
  const [bx, by] = point(state.ball.x, state.ball.y);
  ctx.beginPath(); ctx.fillStyle = "white"; ctx.strokeStyle = "#111827"; ctx.lineWidth = 2;
  ctx.arc(bx, by, Math.max(5, 1.5 * scale), 0, Math.PI * 2); ctx.fill(); ctx.stroke();
}

function describeEvents(events, match) {
  if (!events || !events.length) return "Play is moving across the field.";
  return events.map(event => {
    const name = event.player === "player_1" ? match?.player_1 : event.player === "player_2" ? match?.player_2 : event.player;
    if (event.type === "goal") return `GOAL for ${event.scorer === "player_1" ? match?.player_1 : match?.player_2}!`;
    if (event.type === "kick") return `${name} launches the ball ${event.direction.toLowerCase().replaceAll("_", " ")}.`;
    if (event.type === "interception") return `${name} makes an interception.`;
    if (event.type === "bounce") return "The ball rebounds off an obstacle.";
    if (event.type === "possession") return `${name} takes possession.`;
    if (event.type === "tackle") return `${name} wins the ball with a tackle.`;
    if (event.type === "possession_timeout") return `${name} is forced to release the ball.`;
    if (event.type === "player_contact") return "A shoulder-to-shoulder challenge!";
    if (event.type === "drop_ball") return "The referee restarts the loose ball at midfield.";
    if (event.type === "player_collision") return "The players collide!";
    return event.type.replaceAll("_", " ");
  }).join(" ");
}

function cheer() {
  if (!soundEnabled || !audioContext) return;
  const duration = 1.5;
  const count = Math.floor(audioContext.sampleRate * duration);
  const buffer = audioContext.createBuffer(1, count, audioContext.sampleRate);
  const samples = buffer.getChannelData(0);
  for (let i = 0; i < count; i += 1) samples[i] = (Math.random() * 2 - 1) * (1 - i / count);
  const source = audioContext.createBufferSource();
  const filter = audioContext.createBiquadFilter();
  const gain = audioContext.createGain();
  filter.type = "bandpass"; filter.frequency.value = 900; filter.Q.value = 0.5;
  gain.gain.setValueAtTime(0.22, audioContext.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration);
  source.buffer = buffer; source.connect(filter).connect(gain).connect(audioContext.destination); source.start();
}

soundToggle.addEventListener("click", async () => {
  soundEnabled = !soundEnabled;
  if (soundEnabled) {
    audioContext ||= new AudioContext();
    await audioContext.resume();
  }
  soundToggle.textContent = soundEnabled ? "🔊 Crowd sound on" : "🔇 Enable crowd sound";
});

async function sendControl(action, extra = {}) {
  const response = await fetch("/api/control", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({action, ...extra}),
  });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || "Control request failed");
  return value.control;
}

startButton.addEventListener("click", async () => {
  try {
    await sendControl("configure", {rounds: Number(roundsSelect.value)});
    await sendControl("start");
  } catch (error) { controlStatus.textContent = String(error); }
});
roundsSelect.addEventListener("change", async () => {
  pendingRounds = Number(roundsSelect.value);
  controlStatus.textContent = "Updating fixture list...";
  try {
    await sendControl("configure", {rounds: pendingRounds});
  } catch (error) {
    controlStatus.textContent = String(error);
  } finally {
    pendingRounds = null;
  }
});
pauseButton.addEventListener("click", async () => {
  try {
    const action = pauseButton.dataset.paused === "true" ? "play" : "pause";
    await sendControl(action);
  } catch (error) { controlStatus.textContent = String(error); }
});
stepButton.addEventListener("click", async () => {
  try { await sendControl("step"); } catch (error) { controlStatus.textContent = String(error); }
});
speedSelect.addEventListener("change", async () => {
  try { await sendControl("speed", {speed: Number(speedSelect.value)}); }
  catch (error) { controlStatus.textContent = String(error); }
});

function render(data) {
  eventName.textContent = data.event_name;
  eventStatus.textContent = data.status === "complete"
    ? "Event complete"
    : data.status === "failed"
      ? "Event failed"
      : data.status === "ready" ? "Ready — configure and start" : "Event in progress";
  progressValue.textContent = `${data.completed_matches} / ${data.total_matches}`;
  progressBar.style.width = `${data.total_matches ? 100 * data.completed_matches / data.total_matches : 0}%`;
  errorBox.textContent = data.error || "";
  announcement.textContent = data.announcement || "";
  announcement.className = data.phase === "goal" ? "goal" : data.phase === "complete" ? "champion" : "";
  countdown.hidden = !data.countdown;
  countdown.textContent = data.countdown || "";
  const control = data.control || {};
  if (pendingRounds === null) roundsSelect.value = String(control.rounds || roundsSelect.value);
  speedSelect.value = String(control.speed || speedSelect.value);
  roundsSelect.disabled = Boolean(control.started);
  startButton.disabled = Boolean(control.started);
  startButton.textContent = control.started ? "Tournament started" : "Start tournament";
  pauseButton.disabled = !control.started || data.status === "complete" || data.status === "failed";
  stepButton.disabled = !control.started || !control.paused || data.status === "complete" || data.status === "failed";
  pauseButton.dataset.paused = String(Boolean(control.paused));
  pauseButton.textContent = control.paused ? "Resume" : "Pause";
  controlStatus.textContent = !control.started
    ? `${control.rounds || 1} game${control.rounds === 1 ? "" : "s"} per bracket tie — up to ${data.total_matches} matches.`
    : control.paused ? "Paused. Use Next play to advance one simulation step." : `Running at ${control.speed}x speed.`;

  activeMatch.replaceChildren();
  if (data.active_match) {
    const match = data.active_match;
    const p1 = document.createElement("div"); p1.className = "team blue"; p1.textContent = match.player_1;
    const score = document.createElement("div"); score.className = "active-score"; score.textContent = match.score ? `${match.score.player_1} - ${match.score.player_2}` : "0 - 0";
    const p2 = document.createElement("div"); p2.className = "team orange"; p2.textContent = match.player_2;
    const meta = document.createElement("div"); meta.className = "active-meta"; meta.textContent = `${match.round} | Match ${match.number} of up to ${data.total_matches} | Game ${match.series_game}/${match.series_games} | Seed ${match.seed} | Iteration ${match.iteration}`;
    activeMatch.append(p1, score, p2, meta);
  } else {
    activeMatch.textContent = data.status === "complete" ? "All fixtures completed." : "Preparing the next fixture.";
  }
  const showingFixture = ["fixture_preview", "match_countdown"].includes(data.phase) && data.active_match;
  fixtureCard.hidden = !showingFixture;
  if (showingFixture) {
    fixtureHome.textContent = data.active_match.player_1;
    fixtureAway.textContent = data.active_match.player_2;
    fixtureCardMeta.textContent = `${data.active_match.round} | ${data.active_match.bracket} | Game ${data.active_match.series_game}/${data.active_match.series_games} | Seed ${data.active_match.seed}`;
  }
  if (data.active_state) {
    drawField(data.active_state);
  } else if (["welcome", "event_countdown", "match_countdown"].includes(data.phase)) {
    latestState = null;
    ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
    placeholder.hidden = false;
  }
  commentary.textContent = describeEvents(data.last_events, data.active_match);
  const goal = (data.last_events || []).find(event => event.type === "goal");
  if (goal && data.active_match) {
    const goalKey = `${data.active_match.number}:${data.active_match.iteration}:${goal.scorer}`;
    if (goalKey !== lastGoalKey) { lastGoalKey = goalKey; cheer(); }
  }

  standings.replaceChildren();
  data.standings.forEach((row, index) => {
    const tr = document.createElement("tr");
    [index + 1, row.name, row.bracket_status, row.bracket_losses, row.played, row.wins, row.draws, row.losses, row.gf, row.ga, row.goal_difference].forEach(value => {
      const td = document.createElement("td"); td.textContent = value; tr.appendChild(td);
    });
    standings.appendChild(tr);
  });
  fixtures.replaceChildren();
  for (const match of data.fixtures) {
    const item = document.createElement("article"); item.className = `fixture ${match.status}`;
    const line = document.createElement("div"); line.className = "fixture-line";
    const teams = document.createElement("strong"); teams.textContent = `${match.player_1} vs ${match.player_2}`;
    const scoreText = document.createElement("span"); scoreText.textContent = match.score ? `${match.score.player_1}-${match.score.player_2}` : "-";
    const meta = document.createElement("div"); meta.className = "fixture-meta"; meta.textContent = `${match.round} | ${match.bracket} | game ${match.series_game}/${match.series_games} | #${match.number} | seed ${match.seed} | ${match.status}`;
    line.append(teams, scoreText); item.append(line, meta); fixtures.appendChild(item);
  }
}

async function poll() {
  try {
    const data = await fetch("/api/dashboard").then(response => response.json());
    render(data);
    window.setTimeout(poll, data.status === "complete" || data.status === "failed" ? 1500 : 100);
  } catch (error) {
    errorBox.textContent = `Dashboard connection error: ${error}`;
    window.setTimeout(poll, 1000);
  }
}

window.addEventListener("resize", resizeCanvas);
resizeCanvas();
poll();
