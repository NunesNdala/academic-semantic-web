// ============================================================
// app.js — lógica de interface: tabs, consultas SPARQL, CRUD
// ============================================================

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// ---------------- Tabs ----------------

$$(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    $$(".tab").forEach(t => t.classList.remove("active"));
    $$(".panel").forEach(p => p.classList.remove("active"));
    tab.classList.add("active");
    $(`#${tab.dataset.tab}`).classList.add("active");

    if (tab.dataset.tab === "dados") loadDados();
    if (tab.dataset.tab === "gestao") loadCursos();
  });
});

// ---------------- Renderização de tabela de resultados ----------------

function renderResultTable(target, rows) {
  if (!rows || rows.length === 0) {
    target.innerHTML = `<div class="result-placeholder">Sem resultados.</div>`;
    return;
  }
  const cols = Object.keys(rows[0]);
  const thead = `<tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr>`;
  const tbody = rows.map(r =>
    `<tr>${cols.map(c => `<td>${formatCell(r[c])}</td>`).join("")}</tr>`
  ).join("");

  target.innerHTML = `
    <div class="result-meta">${rows.length} resultado(s)</div>
    <table><thead>${thead}</thead><tbody>${tbody}</tbody></table>
  `;
}

function formatCell(value) {
  if (value === null || value === undefined) return "—";
  // Limpa URIs completos para mostrar apenas o nome local
  if (typeof value === "string" && value.startsWith("http")) {
    return value.split("#").pop().split("/").pop();
  }
  return value;
}

// ---------------- Tab 1: Consultas Inteligentes ----------------

async function loadQueries() {
  const res = await fetch("/api/sparql/predefinidas");
  const queries = await res.json();
  const list = $("#queryList");
  list.innerHTML = "";

  Object.entries(queries).forEach(([id, q]) => {
    const card = document.createElement("button");
    card.className = "query-card";
    card.innerHTML = `<h3>${q.label}</h3><p>${q.description}</p>`;
    card.addEventListener("click", () => runQuery(id, card));
    list.appendChild(card);
  });
}

async function runQuery(id, card) {
  $$(".query-card").forEach(c => c.classList.remove("active"));
  card.classList.add("active");

  const target = $("#queryResult");
  target.innerHTML = `<div class="result-placeholder">A consultar o grafo…</div>`;

  try {
    const res = await fetch(`/api/sparql/predefinidas/${id}`);
    const data = await res.json();
    if (data.erro) {
      target.innerHTML = `<div class="error-msg">${data.erro}</div>`;
      return;
    }
    renderResultTable(target, data.resultados);
  } catch (e) {
    target.innerHTML = `<div class="error-msg">Erro de ligação: ${e}</div>`;
  }
}

// ---------------- Tab 2: Dados do Grafo ----------------

let dadosLoaded = false;

async function loadDados() {
  if (dadosLoaded) return;
  dadosLoaded = true;

  const [estudantes, ucs, docentes, avaliacoes] = await Promise.all([
    fetch("/api/estudantes").then(r => r.json()),
    fetch("/api/ucs").then(r => r.json()),
    fetch("/api/docentes").then(r => r.json()),
    fetch("/api/avaliacoes").then(r => r.json()),
  ]);

  fillTable("#tblEstudantes", estudantes, ["numero", "nome", "email", "curso"]);
  fillTable("#tblUCs", ucs, ["codigo", "nome", "ects", "semestre", "curso"]);
  fillTable("#tblDocentes", docentes, ["nome", "email", "ucs"]);
  fillTable("#tblAvaliacoes", avaliacoes, ["estudanteNome", "ucNome", "nota", "ano"]);
}

function fillTable(selector, rows, fields) {
  const tbody = $(selector + " tbody");
  tbody.innerHTML = rows.map(r =>
    `<tr>${fields.map(f => `<td>${formatCell(r[f])}</td>`).join("")}</tr>`
  ).join("") || `<tr><td colspan="${fields.length}">Sem registos.</td></tr>`;
}

// ---------------- Tab 3: SPARQL Livre ----------------

$("#runSparql").addEventListener("click", async () => {
  const query = $("#sparqlInput").value;
  const target = $("#sparqlResult");
  target.innerHTML = `<div class="result-placeholder">A executar…</div>`;

  try {
    const res = await fetch("/api/sparql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    if (data.erro) {
      target.innerHTML = `<div class="error-msg">${data.erro}</div>`;
      return;
    }
    renderResultTable(target, data.resultados);
  } catch (e) {
    target.innerHTML = `<div class="error-msg">Erro de ligação: ${e}</div>`;
  }
});

// ---------------- Tab 4: Gestão (CRUD) ----------------

let cursosLoaded = false;

async function loadCursos() {
  if (cursosLoaded) return;
  cursosLoaded = true;

  const cursos = await fetch("/api/cursos").then(r => r.json());
  const options = cursos.map(c =>
    `<option value="${c.curso}">${c.designacao}</option>`
  ).join("");

  $("#cursoSelectEstudante").innerHTML = `<option value="">— sem curso —</option>` + options;
  $("#cursoSelectUC").innerHTML = `<option value="">— sem curso —</option>` + options;
}

function showFormMsg(form, msg, ok) {
  const el = form.querySelector(".form-msg");
  el.textContent = msg;
  el.className = "form-msg " + (ok ? "success" : "error");
}

$("#formEstudante").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = Object.fromEntries(new FormData(form).entries());
  if (!data.cursoUri) delete data.cursoUri;
  if (!data.email) delete data.email;

  const res = await fetch("/api/estudantes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const result = await res.json();
  if (res.ok) {
    showFormMsg(form, "Estudante adicionado ao grafo.", true);
    form.reset();
    dadosLoaded = false;
  } else {
    showFormMsg(form, result.erro || "Erro ao adicionar.", false);
  }
});

$("#formAvaliacao").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = Object.fromEntries(new FormData(form).entries());
  if (!data.anoLetivo) delete data.anoLetivo;
  data.nota = parseFloat(data.nota);

  const res = await fetch("/api/avaliacoes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const result = await res.json();
  if (res.ok) {
    showFormMsg(form, "Avaliação registada no grafo.", true);
    form.reset();
    dadosLoaded = false;
  } else {
    showFormMsg(form, result.erro || "Erro ao registar.", false);
  }
});

$("#formUC").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = Object.fromEntries(new FormData(form).entries());
  if (!data.cursoUri) delete data.cursoUri;
  data.ects = parseInt(data.ects, 10);
  data.semestre = parseInt(data.semestre, 10);

  const res = await fetch("/api/ucs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const result = await res.json();
  if (res.ok) {
    showFormMsg(form, "UC adicionada ao grafo.", true);
    form.reset();
    dadosLoaded = false;
  } else {
    showFormMsg(form, result.erro || "Erro ao adicionar.", false);
  }
});

// ---------------- Init ----------------

loadQueries();
