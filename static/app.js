const welcome = document.querySelector("#welcome");
const exam = document.querySelector("#exam");
const results = document.querySelector("#results");
const timer = document.querySelector("#timer");
const questionList = document.querySelector("#questions");
const nodeTabs = document.querySelector("#node-tabs");
const toast = document.querySelector("#toast");
const machineNames = [["gateway", "Pasarela"], ["node1", "Máquina 1"], ["node2", "Máquina 2"]];
const API_BASE = window.location.port === "8080"
  ? `${window.location.protocol}//${window.location.hostname}:8000`
  : "";

let attempt = null;
let activeNode = "all";
let timerHandle = null;
let submitting = false;
let pollingLab = false;
let pendingResetOperation = null;
let consoleRenderKey = null;

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
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

function updateLabControls(status) {
  const provider = document.querySelector("#provider");
  const deploy = document.querySelector("#deploy");
  const start = document.querySelector("#start");
  const busy = status.running;
  const machines = status.machines || {};
  const machineSummary = ["gateway", "node1", "node2"]
    .map((name) => `${name}: ${machines[name] || "desconocido"}`)
    .join(" · ");

  provider.disabled = busy;
  deploy.disabled = busy;
  start.disabled = busy || !status.ready;
  document.querySelector("#reset").disabled = busy;
  document.querySelector("#again").disabled = busy;

  const statusText = document.querySelector("#lab-status");
  if (status.running) {
    statusText.textContent = `${status.phase} (${status.provider})…`;
  } else if (status.status_error) {
    statusText.textContent = `No se pudo consultar Vagrant: ${status.status_error}`;
  } else if (status.success === false) {
    statusText.textContent = `La operación falló: ${status.error}`;
  } else if (status.ready) {
    statusText.textContent = `Laboratorio listo (${machineSummary}).`;
  } else {
    statusText.textContent = `Máquinas no listas (${machineSummary}). Inicia el despliegue.`;
  }

  const log = document.querySelector("#lab-log");
  log.hidden = !status.output?.length;
  document.querySelector("#lab-output").textContent = (status.output || []).join("\n");
  renderConsoles(status);
}

function renderConsoles(status) {
  const panel = document.querySelector("#console-panel");
  const provider = status.provider;
  if (!provider) {
    panel.hidden = true;
    return;
  }

  panel.hidden = false;
  const renderKey = JSON.stringify([provider, status.machines, status.consoles, status.console_error]);
  if (renderKey === consoleRenderKey) return;
  consoleRenderKey = renderKey;
  document.querySelector("#console-help").textContent = provider === "hyperv"
    ? "Hyper-V no expone una consola de framebuffer web estándar. El enlace abre Windows Admin Center si se ha configurado; para GRUB y arranque se necesita VMConnect/RDP desde el anfitrión."
    : provider === "virtualbox"
      ? "VirtualBox usa VRDE/RDP (requiere Oracle Extension Pack y Apache Guacamole para navegador). En Guacamole/noVNC, los controles de teclado dependen de la conexión."
      : "VMware usa VNC por máquina. Configura noVNC o Apache Guacamole para abrir cada pantalla y enviar teclas especiales.";

  const list = document.querySelector("#console-list");
  list.replaceChildren();
  for (const [machine, label] of machineNames) {
    const card = document.createElement("article");
    card.className = "console-card";
    const heading = document.createElement("h3");
    heading.textContent = label;
    const machineState = document.createElement("p");
    machineState.className = "muted";
    machineState.textContent = status.machines?.[machine] || (status.running ? "operación en curso" : "estado desconocido");
    const url = status.consoles?.[machine];
    if (url && status.machines?.[machine] === "running") {
      if (provider !== "hyperv") {
        const embedButton = document.createElement("button");
        embedButton.className = "button secondary console-embed";
        embedButton.type = "button";
        embedButton.textContent = "Ver en esta página";
        embedButton.addEventListener("click", () => {
          const existingFrame = card.querySelector("iframe");
          if (existingFrame) {
            existingFrame.remove();
            embedButton.textContent = "Ver en esta página";
            return;
          }
          const frame = document.createElement("iframe");
          frame.className = "console-frame";
          frame.title = `Consola de ${label}`;
          frame.src = url;
          frame.referrerPolicy = "no-referrer";
          card.append(frame);
          embedButton.textContent = "Ocultar consola";
        });
        card.append(heading, machineState, embedButton);
      } else {
        card.append(heading, machineState);
      }
      const link = document.createElement("a");
      link.className = "button secondary console-link";
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = provider === "hyperv" ? "Abrir Windows Admin Center" : "Abrir consola web";
      card.append(link);
    } else if (url) {
      const unavailable = document.createElement("p");
      unavailable.className = "muted";
      unavailable.textContent = "La consola estará disponible cuando la VM esté encendida.";
      card.append(heading, machineState, unavailable);
    } else {
      const unavailable = document.createElement("p");
      unavailable.className = "muted";
      unavailable.textContent = provider === "hyperv"
        ? "Configura la URL de Windows Admin Center para este host."
        : "Configura la URL de la conexión del navegador para esta VM.";
      card.append(heading, machineState, unavailable);
    }
    list.append(card);
  }
  document.querySelector("#console-config-error").textContent = status.console_error || "";
}

async function pollLabStatus() {
  if (pollingLab) return;
  pollingLab = true;
  try {
    const status = await request("/api/lab/status");
    updateLabControls(status);
    if (pendingResetOperation && status.id === pendingResetOperation && !status.running) {
      pendingResetOperation = null;
      if (status.success && status.ready) {
        await startAttempt();
      } else {
        document.querySelector("#start-error").textContent =
          status.error || status.status_error || "El laboratorio no quedó listo tras el reinicio.";
      }
    }
  } catch (error) {
    document.querySelector("#lab-status").textContent = `No se pudo consultar el laboratorio: ${error.message}`;
  } finally {
    pollingLab = false;
  }
}

async function beginLabOperation(action, onAccepted = () => {}) {
  const provider = document.querySelector("#provider").value;
  const status = await request(`/api/lab/${action}`, {
    method: "POST",
    body: JSON.stringify({ provider }),
  });
  pendingResetOperation = action === "reset" ? status.id : null;
  onAccepted();
  await pollLabStatus();
}

async function resetLab() {
  if (!window.confirm(
    "Se destruirán las tres máquinas virtuales y se borrarán sus discos y datos. " +
    "Después se desplegará un laboratorio limpio y se sortearán nuevas preguntas. ¿Continuar?"
  )) return;

  try {
    await beginLabOperation("reset", () => {
      clearInterval(timerHandle);
      attempt = null;
      submitting = false;
      welcome.hidden = false;
      exam.hidden = true;
      results.hidden = true;
      timer.hidden = true;
      document.querySelector("#start-error").textContent = "";
    });
  } catch (error) {
    showToast(error.message);
  }
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
document.querySelector("#deploy").addEventListener("click", async () => {
  try {
    await beginLabOperation("deploy");
  } catch (error) {
    document.querySelector("#start-error").textContent = error.message;
  }
});
document.querySelector("#reset").addEventListener("click", resetLab);
document.querySelector("#finish").addEventListener("click", finishAttempt);
document.querySelector("#again").addEventListener("click", resetLab);

pollLabStatus();
window.setInterval(pollLabStatus, 3000);
