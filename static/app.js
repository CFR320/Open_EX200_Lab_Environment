const welcome = document.querySelector("#welcome");
const exam = document.querySelector("#exam");
const results = document.querySelector("#results");
const timer = document.querySelector("#timer");
const questionList = document.querySelector("#questions");
const nodeTabs = document.querySelector("#node-tabs");
const toast = document.querySelector("#toast");

let attempt = null;
let activeNode = "all";
let timerHandle = null;
let submitting = false;

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Error HTTP ${response.status}`);
  return body;
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
}

function renderTabs() {
  nodeTabs.replaceChildren();
  for (const [id, label] of [["all", "Todas"], ["node1", "Máquina 1"], ["node2", "Máquina 2"]]) {
    const button = document.createElement("button");
    button.className = `button node-tab${activeNode === id ? " active" : ""}`;
    button.textContent = label;
    button.addEventListener("click", () => {
      activeNode = id;
      renderTabs();
      renderQuestions();
    });
    nodeTabs.append(button);
  }
}

function renderQuestions() {
  questionList.replaceChildren();
  const filtered = attempt.questions.filter((question) => activeNode === "all" || question.node === activeNode);
  for (const question of filtered) {
    const article = document.createElement("article");
    article.className = "question";
    const top = document.createElement("div");
    top.className = "question-top";
    const title = document.createElement("h2");
    title.textContent = `${String(question.number).padStart(2, "0")} · ${question.title}`;
    const right = document.createElement("div");
    right.className = "question-top";
    const node = document.createElement("span");
    node.className = "tag";
    node.textContent = question.node === "node1" ? "Máquina 1" : "Máquina 2";
    const points = document.createElement("span");
    points.className = "points";
    points.textContent = `${question.points} puntos`;
    right.append(node, points);
    top.append(title, right);
    const prompt = document.createElement("p");
    prompt.textContent = question.prompt;
    const source = document.createElement("p");
    source.className = "muted";
    source.textContent = question.source;
    article.append(top, prompt, source);
    questionList.append(article);
  }
  document.querySelector("#exam-status").textContent =
    `${attempt.questions.length} preguntas · 3 horas · 300 puntos máximos · aprobado desde 210 puntos`;
}

function updateTimer() {
  const remaining = Math.max(0, Math.ceil(attempt.deadline - Date.now() / 1000));
  const hours = String(Math.floor(remaining / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((remaining % 3600) / 60)).padStart(2, "0");
  const seconds = String(remaining % 60).padStart(2, "0");
  timer.textContent = `${hours}:${minutes}:${seconds}`;
  timer.classList.toggle("urgent", remaining < 300);
  if (remaining === 0) {
    clearInterval(timerHandle);
    finishAttempt();
  }
}

async function startAttempt() {
  const button = document.querySelector("#start");
  button.disabled = true;
  document.querySelector("#start-error").textContent = "";
  try {
    attempt = await request("/api/attempts", { method: "POST", body: "{}" });
    activeNode = "all";
    welcome.hidden = true;
    exam.hidden = false;
    timer.hidden = false;
    renderTabs();
    renderQuestions();
    updateTimer();
    timerHandle = window.setInterval(updateTimer, 1000);
  } catch (error) {
    document.querySelector("#start-error").textContent = error.message;
    button.disabled = false;
  }
}

function renderResult(result) {
  clearInterval(timerHandle);
  exam.hidden = true;
  timer.hidden = true;
  results.hidden = false;
  document.querySelector("#result-title").textContent = result.passed ? "¡Prueba superada!" : "Prueba no superada";
  document.querySelector("#score").textContent = `${result.score} / ${result.maximum} puntos`;
  document.querySelector("#result-message").textContent =
    `${result.correct} de ${result.total} preguntas validadas. ${result.passed ? "Has alcanzado los 210 puntos necesarios." : "Necesitas al menos 210 puntos para aprobar."}`;
  const details = document.querySelector("#result-details");
  details.replaceChildren();
  for (const item of result.details) {
    const question = attempt.questions.find((entry) => entry.id === item.id);
    const row = document.createElement("div");
    row.className = "result-row";
    const label = document.createElement("span");
    label.textContent = question ? `${question.title} · ${question.node}` : item.id;
    const status = document.createElement("strong");
    status.className = item.passed ? "pass" : "fail";
    status.textContent = item.passed ? `Correcta · ${item.points} pts` : "Pendiente · 0 pts";
    row.append(label, status);
    details.append(row);
  }
}

async function finishAttempt() {
  if (!attempt || submitting) return;
  submitting = true;
  const button = document.querySelector("#finish");
  button.disabled = true;
  button.textContent = "Validando las máquinas…";
  try {
    const result = await request(`/api/attempts/${encodeURIComponent(attempt.id)}/finish`, {
      method: "POST",
      body: "{}",
    });
    renderResult(result);
  } catch (error) {
    showToast(`No se pudo corregir el intento: ${error.message}. Comprueba que ambas VMs están encendidas y vuelve a finalizar.`);
    button.disabled = false;
    button.textContent = "Reintentar corrección";
    submitting = false;
  }
}

document.querySelector("#start").addEventListener("click", startAttempt);
document.querySelector("#finish").addEventListener("click", finishAttempt);
document.querySelector("#again").addEventListener("click", () => window.location.reload());
