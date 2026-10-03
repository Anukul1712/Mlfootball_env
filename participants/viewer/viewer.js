const canvas = document.getElementById("field");
const ctx = canvas.getContext("2d");
const score = document.getElementById("score");
const iteration = document.getElementById("iteration");
const ballStatus = document.getElementById("ball-status");
const matchLabel = document.getElementById("match-label");
const message = document.getElementById("message");
const controls = document.getElementById("replay-controls");
const timeline = document.getElementById("timeline");
const playButton = document.getElementById("play");
const detail = document.getElementById("frame-detail");
const speed = document.getElementById("speed");
const currentCommentary = document.getElementById("current-commentary");
const commentaryHistory = document.getElementById("commentary-history");
const eventMarkers = document.getElementById("event-markers");

let latestState = null;
let frames = [];
let eventFrames = [];
let frameIndex = 0;
let playing = false;
let timer = null;

function sizeCanvas() {
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  if (latestState) draw(latestState);
}

function draw(state) {
  latestState = state;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  const field = state.field;
  const pad = Math.max(18, Math.min(w, h) * 0.045);
  const scale = Math.min((w - 2 * pad) / field.width, (h - 2 * pad) / field.height);
  const fieldWidth = field.width * scale;
  const fieldHeight = field.height * scale;
  const left = (w - fieldWidth) / 2;
  const top = (h - fieldHeight) / 2;
  const right = left + fieldWidth;
  const bottom = top + fieldHeight;
  const point = (x, y) => [left + x * scale, bottom - y * scale];

  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#19733f";
  ctx.fillRect(left, top, fieldWidth, fieldHeight);
  ctx.strokeStyle = "#f8fafc";
  ctx.lineWidth = 2;
  ctx.strokeRect(left, top, fieldWidth, fieldHeight);
  ctx.beginPath();
  ctx.moveTo(left, (top + bottom) / 2);
  ctx.lineTo(right, (top + bottom) / 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc((left + right) / 2, (top + bottom) / 2, 9 * scale, 0, Math.PI * 2);
  ctx.stroke();

  const goalWidth = field.goal_width * scale;
  const goalX = (left + right - goalWidth) / 2;
  const goalDepth = Math.max(7, 4 * scale);
  ctx.strokeRect(goalX, top - goalDepth, goalWidth, goalDepth);
  ctx.strokeRect(goalX, bottom, goalWidth, goalDepth);

  for (const obstacle of state.obstacles) {
    const [x, y] = point(obstacle.x, obstacle.y + obstacle.height);
    ctx.fillStyle = "#4b5563";
    ctx.fillRect(x, y, obstacle.width * scale, obstacle.height * scale);
    ctx.strokeStyle = "#d1d5db";
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, obstacle.width * scale, obstacle.height * scale);
  }

  for (const [id, position] of Object.entries(state.players)) {
    const [x, y] = point(position.x, position.y);
    const radius = Math.max(8, 3 * scale);
    if (state.ball.possession === id) {
      ctx.beginPath();
      ctx.strokeStyle = "#fde047";
      ctx.lineWidth = 3;
      ctx.arc(x, y, radius + 5, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.fillStyle = id === "player_1" ? "#2563eb" : "#f97316";
    ctx.strokeStyle = "white";
    ctx.lineWidth = 2;
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "white";
    ctx.font = "700 13px Segoe UI, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(id === "player_1" ? "1" : "2", x, y);
  }

  const [ballX, ballY] = point(state.ball.x, state.ball.y);
  ctx.beginPath();
  ctx.fillStyle = "white";
  ctx.strokeStyle = "#111827";
  ctx.lineWidth = 2;
  ctx.arc(ballX, ballY, Math.max(5, 1.5 * scale), 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  score.textContent = `${state.score.player_1} - ${state.score.player_2}`;
  iteration.textContent = `Iteration ${state.iteration} / ${state.maximum_iterations}`;
  ballStatus.textContent = state.ball.possession
    ? `Possession: ${state.ball.possession.replace("_", " ")}`
    : `Ball: ${state.ball.status}`;
}

function describeEvents(events, state) {
  if (!events || !events.length) {
    const owner = state.ball.possession ? ` with ${state.ball.possession.replace("_", " ")}` : "";
    return `Play continues. The ball is ${state.ball.status}${owner}.`;
  }
  return events.map(event => {
    if (event.type === "goal") return `Goal for ${event.scorer.replace("_", " ")}! The score is ${state.score.player_1}-${state.score.player_2}.`;
    if (event.type === "kick") return `${event.player.replace("_", " ")} kicks ${event.direction.toLowerCase().replace("_", " ")} at power ${event.power}.`;
    if (event.type === "interception") return `${event.player.replace("_", " ")} intercepts the moving ball.`;
    if (event.type === "bounce") return `The ball rebounds from the ${event.surface.replace("_", " ")}.`;
    if (event.type === "possession") return `${event.player.replace("_", " ")} takes possession.`;
    if (event.type === "tackle") return `${event.player.replace("_", " ")} wins the ball with a tackle.`;
    if (event.type === "possession_timeout") return `${event.player.replace("_", " ")} is forced to release the ball after holding it too long.`;
    if (event.type === "player_contact") return "The players challenge shoulder-to-shoulder.";
    if (event.type === "drop_ball") return "The referee restarts an unclaimed loose ball at midfield.";
    if (event.type === "restart") return `Kickoff restarts with ${event.possession.replace("_", " ")}.`;
    if (event.type === "player_collision") return "The players collide; both movements are cancelled.";
    if (event.type === "ball_stopped") return "The kick runs out of distance and the ball stops.";
    return event.type.replaceAll("_", " ");
  }).join(" ");
}

function renderCommentary(events, state) {
  currentCommentary.textContent = describeEvents(events, state);
}

function renderReplayHistory() {
  commentaryHistory.replaceChildren();
  const start = Math.max(1, frameIndex - 12);
  for (let index = start; index <= frameIndex; index += 1) {
    if (!frames[index].events.length) continue;
    const item = document.createElement("li");
    item.textContent = `${index}: ${describeEvents(frames[index].events, frames[index].state)}`;
    commentaryHistory.appendChild(item);
  }
}

function renderLiveHistory(history) {
  commentaryHistory.replaceChildren();
  for (const entry of (history || []).slice(-12)) {
    const item = document.createElement("li");
    item.textContent = `${entry.iteration}: ${describeEvents(entry.events, {score: entry.score, ball: entry.ball})}`;
    commentaryHistory.appendChild(item);
  }
}

function renderMarkers() {
  eventMarkers.replaceChildren();
  for (const index of eventFrames) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${index}: ${frames[index].events.map(event => event.type).join(", ")}`;
    button.addEventListener("click", () => { stop(); showFrame(index); });
    eventMarkers.appendChild(button);
  }
}

function showFrame(index) {
  frameIndex = Math.max(0, Math.min(frames.length - 1, index));
  timeline.value = String(frameIndex);
  const frame = frames[frameIndex];
  draw(frame.state);
  const eventNames = frame.events.length ? frame.events.map(event => event.type).join(", ") : "no event";
  detail.textContent = `Frame ${frameIndex} / ${frames.length - 1} | ${eventNames}`;
  renderCommentary(frame.events, frame.state);
  renderReplayHistory();
}

function stop() {
  playing = false;
  playButton.textContent = "Play";
  if (timer) window.clearTimeout(timer);
  timer = null;
}

function advance() {
  if (!playing) return;
  if (frameIndex >= frames.length - 1) return stop();
  showFrame(frameIndex + 1);
  timer = window.setTimeout(advance, Number(speed.value));
}

playButton.addEventListener("click", () => {
  if (playing) return stop();
  if (frameIndex >= frames.length - 1) showFrame(0);
  playing = true;
  playButton.textContent = "Pause";
  advance();
});
document.getElementById("previous").addEventListener("click", () => { stop(); showFrame(frameIndex - 1); });
document.getElementById("next").addEventListener("click", () => { stop(); showFrame(frameIndex + 1); });
document.getElementById("previous-event").addEventListener("click", () => {
  stop();
  const target = [...eventFrames].reverse().find(index => index < frameIndex);
  if (target !== undefined) showFrame(target);
});
document.getElementById("next-event").addEventListener("click", () => {
  stop();
  const target = eventFrames.find(index => index > frameIndex);
  if (target !== undefined) showFrame(target);
});
timeline.addEventListener("input", () => { stop(); showFrame(Number(timeline.value)); });
window.addEventListener("resize", sizeCanvas);
window.addEventListener("keydown", event => {
  if (event.key === " ") { event.preventDefault(); playButton.click(); }
  if (event.key === "ArrowLeft") document.getElementById("previous").click();
  if (event.key === "ArrowRight") document.getElementById("next").click();
});

async function start() {
  const info = await fetch("/api/info").then(response => response.json());
  const players = info.metadata.players || {};
  matchLabel.textContent = `${players.player_1 || "Player 1"} vs ${players.player_2 || "Player 2"} | Seed ${info.metadata.seed ?? "-"}`;
  sizeCanvas();
  if (info.mode === "replay") {
    controls.hidden = false;
    const replay = await fetch("/api/replay").then(response => response.json());
    frames = replay.frames;
    eventFrames = frames.map((frame, index) => frame.events.length ? index : null).filter(index => index !== null);
    timeline.max = String(Math.max(0, frames.length - 1));
    renderMarkers();
    showFrame(0);
    return;
  }

  const poll = async () => {
    try {
      const snapshot = await fetch("/api/state").then(response => response.json());
      if (snapshot.state) {
        draw(snapshot.state);
        renderCommentary(snapshot.events, snapshot.state);
        renderLiveHistory(snapshot.event_history);
      }
      if (snapshot.error) {
        message.textContent = snapshot.error;
        message.className = "error";
        return;
      }
      if (snapshot.result) {
        const winner = snapshot.result.winner || "draw";
        message.textContent = `Match complete: ${winner}. Replay: ${snapshot.result.log_path}`;
        return;
      }
      message.textContent = snapshot.state ? "Live match running" : "Starting bot processes...";
      window.setTimeout(poll, 60);
    } catch (error) {
      message.textContent = `Viewer connection error: ${error}`;
      message.className = "error";
    }
  };
  poll();
}

start().catch(error => {
  message.textContent = `Cannot start viewer: ${error}`;
  message.className = "error";
});
