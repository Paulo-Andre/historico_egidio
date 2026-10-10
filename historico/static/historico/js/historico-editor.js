(() => {
  "use strict";

  const root = document.querySelector("[data-historico-editor]");
  if (!root) return;

  const canEdit = root.dataset.canEdit === "1";
  const saveUrl = root.dataset.saveUrl || "";
  const csrfToken = document.querySelector("input[name='csrfmiddlewaretoken']")?.value;
  const saveStatus = document.querySelector("[data-save-status]");
  const saveButton = document.querySelector("[data-action='save']");
  const avgOutput = document.querySelector("[data-summary-average]");
  const loadOutput = document.querySelector("[data-summary-load]");
  const alertOutput = document.querySelector("[data-summary-alerts]");
  const logo = document.querySelector("[data-letterhead]");

  let saveTimer = null;
  let saving = false;
  let pendingSave = false;

  const cleanText = (element) => (element?.textContent || "").trim();

  function parseNumber(value) {
    const text = String(value ?? "").trim();
    if (!text || /^N\d/i.test(text) || text === "*" || text === "-") return null;
    const match = text.replace(",", ".").match(/-?\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : null;
  }

  function recordIdFromElement(element) {
    return element?.closest("[data-registro-id]")?.dataset.registroId || null;
  }

  function rowsForRecord(id) {
    if (!id) return [];
    return [...root.querySelectorAll(`[data-registro-id="${id}"]`)];
  }

  function firstInRows(rows, selector) {
    for (const row of rows) {
      const found = row.querySelector(selector);
      if (found) return found;
    }
    return null;
  }

  function allInRows(rows, selector) {
    return rows.flatMap((row) => [...row.querySelectorAll(selector)]);
  }

  function thresholdForGrade(rawThreshold, grade) {
    let threshold = parseNumber(rawThreshold);
    if (threshold === null) return grade > 10 ? 60 : 6;
    if (threshold <= 1) return grade > 10 ? threshold * 100 : threshold * 10;
    if (threshold > 10 && grade <= 10) return threshold / 10;
    if (threshold <= 10 && grade > 10) return threshold * 10;
    return threshold;
  }

  function evaluateRecord(recordId, autoStatus = false) {
    const rows = rowsForRecord(recordId);
    if (!rows.length) return false;

    const firstRow = rows[0];
    const thresholdRaw = firstRow.dataset.mediaMinima || "";
    const serie = Number(firstRow.dataset.serie || "0");
    const noteCells = allInRows(rows, "[data-role='nota']");
    const statusCell = firstInRows(rows, "[data-field='resultado']");

    let anyFailed = false;
    let numericCount = 0;

    noteCells.forEach((cell) => {
      const grade = parseNumber(cleanText(cell));
      let failed = false;
      if (grade !== null) {
        numericCount += 1;
        failed = grade < thresholdForGrade(thresholdRaw, grade);
      }
      cell.classList.toggle("alerta-reprovado", failed);
      if (failed) anyFailed = true;
    });

    if (autoStatus && canEdit && statusCell && numericCount > 0) {
      const current = cleanText(statusCell).toUpperCase();
      const locked = new Set(["EM CURSO", "EM CONTINUIDADE"]);
      if (!locked.has(current)) {
        if ((serie === 3 || serie === 5) && anyFailed) {
          statusCell.textContent = "REPROVADO";
        } else {
          statusCell.textContent = "APTO";
        }
      }
    }

    const explicitReprovado = cleanText(statusCell).toUpperCase() === "REPROVADO";
    const warning = anyFailed || explicitReprovado;

    if (statusCell) {
      statusCell.classList.toggle("alerta-reprovado", warning);
      statusCell.dataset.status = warning ? "reprovado" : "aprovado";
    }

    rows.forEach((row) => row.classList.toggle("registro-com-alerta", warning));
    return warning;
  }

  function syncAnnualLoad(recordId, source) {
    const rows = rowsForRecord(recordId);
    const value = cleanText(source);
    allInRows(rows, "[data-field='carga_horaria']").forEach((cell) => {
      if (cell !== source) cell.textContent = value;
    });
  }

  function recalcSummary() {
    const grades = [...root.querySelectorAll("[data-registro-id] [data-role='nota']")]
      .map((cell) => parseNumber(cleanText(cell)))
      .filter((value) => value !== null)
      .map((value) => (value > 10 ? value / 10 : value));

    const loads = [...root.querySelectorAll("[data-role='carga-horaria-total']")]
      .map((cell) => parseNumber(cleanText(cell)))
      .filter((value) => value !== null);

    const alertedIds = new Set(
      [...root.querySelectorAll(".registro-com-alerta[data-registro-id]")]
        .map((row) => row.dataset.registroId)
        .filter(Boolean)
    );

    if (avgOutput) {
      if (grades.length) {
        const avg = grades.reduce((sum, value) => sum + value, 0) / grades.length;
        avgOutput.textContent = avg.toLocaleString("pt-BR", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      } else {
        avgOutput.textContent = "—";
      }
    }

    if (loadOutput) {
      const total = loads.reduce((sum, value) => sum + value, 0);
      loadOutput.textContent = total
        ? total.toLocaleString("pt-BR", { maximumFractionDigits: 2 })
        : "—";
    }

    if (alertOutput) alertOutput.textContent = String(alertedIds.size);
  }

  function uniqueRecordIds() {
    return [...new Set(
      [...root.querySelectorAll("[data-registro-id]")]
        .map((row) => row.dataset.registroId)
        .filter(Boolean)
    )];
  }

  function collectPayload() {
    const aluno = {};
    root.querySelectorAll("[data-model='aluno'][data-field]").forEach((element) => {
      aluno[element.dataset.field] = cleanText(element);
    });

    const registros = uniqueRecordIds().map((id) => {
      const rows = rowsForRecord(id);
      const campos = {};
      allInRows(rows, "[data-model='registro'][data-field]").forEach((element) => {
        campos[element.dataset.field] = cleanText(element);
      });

      const notas = {};
      allInRows(rows, "[data-nota]").forEach((element) => {
        notas[element.dataset.nota] = {
          valor: cleanText(element),
          carga_horaria: "",
        };
      });

      return { id: Number(id), campos, notas };
    });

    return { aluno, registros };
  }

  function setSaveState(message, cssClass = "") {
    if (!saveStatus) return;
    saveStatus.textContent = message;
    saveStatus.className = `save-status ${cssClass}`.trim();
  }

  async function saveNow() {
    if (!canEdit || !saveUrl || !csrfToken) return;
    if (saving) {
      pendingSave = true;
      return;
    }

    saving = true;
    pendingSave = false;
    setSaveState("Salvando…", "is-saving");

    try {
      const response = await fetch(saveUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(collectPayload()),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        throw new Error(data.erro || "Não foi possível salvar.");
      }
      setSaveState("Alterações salvas", "is-saved");
    } catch (error) {
      setSaveState(error.message || "Erro ao salvar", "is-error");
    } finally {
      saving = false;
      if (pendingSave) {
        pendingSave = false;
        saveNow();
      }
    }
  }

  function scheduleSave() {
    if (!canEdit) return;
    window.clearTimeout(saveTimer);
    setSaveState("Alterações pendentes");
    saveTimer = window.setTimeout(saveNow, 900);
  }

  function onInput(event) {
    const target = event.target;
    const recordId = recordIdFromElement(target);

    if (target.matches("[data-role='nota']") && recordId) {
      evaluateRecord(recordId, true);
    } else if (target.matches("[data-field='carga_horaria']") && recordId) {
      syncAnnualLoad(recordId, target);
    } else if (target.matches("[data-field='resultado']") && recordId) {
      evaluateRecord(recordId, false);
    }

    recalcSummary();
    scheduleSave();
  }

  function setupEditableFields() {
    if (!canEdit) return;

    root.querySelectorAll("[contenteditable='true']").forEach((element) => {
      element.addEventListener("input", onInput);
      element.addEventListener("blur", () => {
        window.clearTimeout(saveTimer);
        saveNow();
      });
      element.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && element.dataset.multiline !== "1") {
          event.preventDefault();
          element.blur();
        }
      });
      element.addEventListener("paste", (event) => {
        event.preventDefault();
        const text = event.clipboardData?.getData("text/plain") || "";
        document.execCommand("insertText", false, text);
      });
    });
  }

  async function hydrateLetterheadFallback() {
    if (!logo || !logo.dataset.fallbackB64Url) return;
    if (logo.complete && logo.naturalWidth > 0) return;

    try {
      const response = await fetch(logo.dataset.fallbackB64Url);
      if (!response.ok) return;
      const base64 = (await response.text()).trim();
      if (base64) logo.src = `data:image/jpeg;base64,${base64}`;
    } catch (_) {
      // Mantém o restante do documento disponível mesmo se a imagem falhar.
    }
  }

  uniqueRecordIds().forEach((id) => evaluateRecord(id, false));
  recalcSummary();
  setupEditableFields();

  saveButton?.addEventListener("click", () => {
    window.clearTimeout(saveTimer);
    saveNow();
  });

  if (logo) {
    logo.addEventListener("error", hydrateLetterheadFallback, { once: true });
    if (logo.complete && logo.naturalWidth === 0) hydrateLetterheadFallback();
  }
})();
