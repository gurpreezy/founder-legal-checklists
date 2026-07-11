// SMS Screenshot Task Agent — dashboard
// Configure the backend URL + API key via the Settings modal (stored in localStorage).

const state = {
  apiUrl: localStorage.getItem("taskagent.apiUrl") || "",
  apiKey: localStorage.getItem("taskagent.apiKey") || "",
  tasks: [],
  lists: [],
  activeList: null,
};

const $ = (id) => document.getElementById(id);

// ---------- API ----------

async function api(path, options = {}) {
  const res = await fetch(state.apiUrl.replace(/\/$/, "") + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "x-api-key": state.apiKey,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

async function loadTasks() {
  const query = state.activeList ? `?list=${encodeURIComponent(state.activeList)}` : "";
  const data = await api(`/api/tasks${query}`);
  state.tasks = data.tasks;
  state.lists = data.lists;
  render();
}

// ---------- rendering ----------

function render() {
  renderFilters();
  renderTasks();
}

function renderFilters() {
  const el = $("filters");
  el.innerHTML = "";
  const all = chip("All", state.activeList === null, () => {
    state.activeList = null;
    loadTasks();
  });
  el.appendChild(all);
  for (const list of state.lists) {
    el.appendChild(
      chip(list, state.activeList === list, () => {
        state.activeList = list;
        loadTasks();
      })
    );
  }
}

function chip(label, active, onClick) {
  const b = document.createElement("button");
  b.className = "chip" + (active ? " active" : "");
  b.textContent = label;
  b.onclick = onClick;
  return b;
}

function renderTasks() {
  const el = $("task-list");
  el.innerHTML = "";
  if (!state.tasks.length) {
    el.innerHTML = `<p class="empty">No tasks yet. Text a screenshot to your Twilio number to get started.</p>`;
    return;
  }
  for (const task of state.tasks) el.appendChild(taskCard(task));
}

function taskCard(task) {
  const card = document.createElement("div");
  card.className = "task" + (task.status === "done" ? " done" : "");

  if (task.screenshot_signed_url) {
    const img = document.createElement("img");
    img.className = "thumb";
    img.src = task.screenshot_signed_url;
    img.alt = "screenshot";
    img.onclick = () => showLightbox(task.screenshot_signed_url);
    card.appendChild(img);
  }

  const main = document.createElement("div");
  main.className = "task-main";

  const title = document.createElement("div");
  title.className = "task-title";
  title.textContent = task.title;
  main.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "task-meta";
  meta.appendChild(badge(task.assigned_list, "list"));
  if (task.due_date) meta.appendChild(badge(`due ${task.due_date}`, "due"));
  if (task.priority) meta.appendChild(badge(task.priority, `priority-${task.priority}`));
  if (task.routing_source === "auto" && task.confidence_score != null) {
    meta.appendChild(badge(`auto ${Math.round(task.confidence_score * 100)}%`, "auto"));
  }
  if (task.routing_source === "corrected") meta.appendChild(badge("corrected", ""));
  const when = document.createElement("span");
  when.textContent = new Date(task.created_at).toLocaleString();
  meta.appendChild(when);
  main.appendChild(meta);
  card.appendChild(main);

  const actions = document.createElement("div");
  actions.className = "task-actions";

  // Reroute dropdown — the manual-override / learning signal.
  const select = document.createElement("select");
  select.title = "Move to another list (teaches the agent)";
  const listSet = new Set([task.assigned_list, ...state.lists]);
  for (const list of listSet) {
    const opt = document.createElement("option");
    opt.value = list;
    opt.textContent = list;
    opt.selected = list === task.assigned_list;
    select.appendChild(opt);
  }
  const newOpt = document.createElement("option");
  newOpt.value = "__new__";
  newOpt.textContent = "+ New list…";
  select.appendChild(newOpt);
  select.onchange = async () => {
    let target = select.value;
    if (target === "__new__") {
      target = prompt("New list name:");
      if (!target) { select.value = task.assigned_list; return; }
    }
    await api(`/api/tasks/${task.id}`, {
      method: "PATCH",
      body: JSON.stringify({ assigned_list: target }),
    });
    loadTasks();
  };
  actions.appendChild(select);

  const row = document.createElement("div");
  const doneBtn = iconBtn(task.status === "done" ? "↩︎" : "✓", async () => {
    await api(`/api/tasks/${task.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: task.status === "done" ? "open" : "done" }),
    });
    loadTasks();
  });
  doneBtn.title = task.status === "done" ? "Reopen" : "Mark done";
  const delBtn = iconBtn("🗑", async () => {
    if (!confirm("Delete this task?")) return;
    await api(`/api/tasks/${task.id}`, { method: "DELETE" });
    loadTasks();
  });
  delBtn.title = "Delete";
  row.appendChild(doneBtn);
  row.appendChild(delBtn);
  actions.appendChild(row);

  card.appendChild(actions);
  return card;
}

function badge(text, cls) {
  const s = document.createElement("span");
  s.className = `badge ${cls}`;
  s.textContent = text;
  return s;
}

function iconBtn(label, onClick) {
  const b = document.createElement("button");
  b.className = "icon-btn";
  b.textContent = label;
  b.onclick = onClick;
  return b;
}

function showLightbox(src) {
  const box = document.createElement("div");
  box.id = "lightbox";
  const img = document.createElement("img");
  img.src = src;
  box.appendChild(img);
  box.onclick = () => box.remove();
  document.body.appendChild(box);
}

// ---------- insights ----------

async function showInsights() {
  const modal = $("insights-modal");
  modal.showModal();
  const body = $("insights-body");
  body.innerHTML = `<p class="empty">Loading…</p>`;
  try {
    const s = await api("/api/insights");
    const accuracy =
      s.auto_routing_accuracy == null ? "—" : `${Math.round(s.auto_routing_accuracy * 100)}%`;
    let html = `
      <div class="insights-stat"><span>Training examples</span><span>${s.training_examples}</span></div>
      <div class="insights-stat"><span>Auto-routed tasks</span><span>${s.auto_routed_tasks}</span></div>
      <div class="insights-stat"><span>Corrections you made</span><span>${s.corrections}</span></div>
      <div class="insights-stat"><span>Auto-routing accuracy</span><span>${accuracy}</span></div>
      <hr style="border-color:var(--border);margin:10px 0">
    `;
    const lists = Object.entries(s.examples_by_list || {});
    if (lists.length) {
      html += `<div class="insights-stat"><span>Examples per list</span><span></span></div>`;
      for (const [list, counts] of lists) {
        const total = counts.explicit + counts.correction + counts.auto_confirmed;
        html += `<div class="insights-list-row">${list}: ${total} (${counts.explicit} explicit, ${counts.correction} corrections)</div>`;
      }
    }
    body.innerHTML = html;
  } catch (err) {
    body.innerHTML = `<p class="empty">${err.message}</p>`;
  }
}

// ---------- settings ----------

function openSettings() {
  $("api-url").value = state.apiUrl;
  $("api-key").value = state.apiKey;
  $("settings-modal").showModal();
}

function saveSettings() {
  state.apiUrl = $("api-url").value.trim();
  state.apiKey = $("api-key").value.trim();
  localStorage.setItem("taskagent.apiUrl", state.apiUrl);
  localStorage.setItem("taskagent.apiKey", state.apiKey);
  $("settings-modal").close();
  loadTasks().catch(showError);
}

function showError(err) {
  $("task-list").innerHTML = `<p class="empty">⚠️ ${err.message}<br><br>Check Settings (backend URL + API key).</p>`;
}

// ---------- init ----------

$("settings-btn").onclick = openSettings;
$("settings-save").onclick = saveSettings;
$("insights-btn").onclick = showInsights;

if (!state.apiUrl || !state.apiKey) {
  openSettings();
  $("task-list").innerHTML = `<p class="empty">Enter your backend URL and API key to connect.</p>`;
} else {
  loadTasks().catch(showError);
  setInterval(() => loadTasks().catch(() => {}), 15000); // keep the 30s SLA visible
}
