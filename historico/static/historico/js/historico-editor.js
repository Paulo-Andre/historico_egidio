(() => {
  "use strict";

  const root = document.querySelector("[data-historico-editor]");
  if (!root) return;

  const canEdit = root.dataset.canEdit === "1";
  const saveUrl = root.dataset.saveUrl || "";
  const csrfToken = document.querySelector(
    "input[name='csrfmiddlewaretoken']"
  )?.value;
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
    if (!text || /^N\d/i.test(text) || text === "*" || text === "-") {
      return null;
    }
    const match = text.replace(",", ".").match(/-?\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : null;
  }

  function thresholdForGrade(rawThreshold, grade) {
    let threshold = parseNumber(rawThreshold);
    if (threshold === null) {
      return grade > 10 ? 60 : 6;
    }
    if (threshold <= 1) {
      return grade > 10 ? threshold * 100 : threshold * 10;
    }
    if (threshold > 10 && grade <= 10) return threshold / 10;
    if (threshold <= 10 && grade > 10) return threshold * 10;
    return threshold;
  }

  function markStatus(element, failed) {
    if (!element) return;
    element.classList.toggle("alerta-reprovado", failed);
    element.dataset.status = failed ? "reprovado" : "aprovado";
  }

  function evaluateRecord(block, autoStatus = false) {
    if (!block) return false;

    const thresholdRaw = block.dataset.mediaMinima || "";
    const noteCells = [...block.querySelectorAll("[data-role='nota']")];
    const statusCell = block.querySelector("[data-field='resultado']");
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

    const currentStatus = cleanText(statusCell).toUpperCase();
    const specialStatuses = new Set([
      "EM CONTINUIDADE",
      "EM CURSO",
      "APTO",
      "APTA",
    ]);

    if (
      autoStatus &&
      canEdit &&
      statusCell &&
      numericCount > 0 &&
      !specialStatuses.has(currentStatus)
    ) {
      statusCell.textContent = anyFailed ? "REPROVADO" : "APROVADO";
    }

    const statusFailed =
      cleanText(statusCell).toUpperCase() === "REPROVADO" || anyFailed;

    markStatus(statusCell, statusFailed);
    block.classList.toggle("registro-com-alerta", statusFailed);
    return statusFailed;
  }

  function recalcRecordLoad(block) {
    const componentLoads = [
      ...block.querySelectorAll("[data-role='carga-componente']"),
    ];
    const totalCell = block.querySelector("[data-role='carga-horaria-total']");
    if (!totalCell) return;

    const values = componentLoads
      .map((cell) => parseNumber(cleanText(cell)))
      .filter((value) => value !== null);

    if (values.length > 0) {
      const sum = values.reduce((acc, value) => acc + value, 0);
      totalCell.textContent = Number.isInteger(sum)
        ? String(sum)
        : sum.toLocaleString("pt-BR", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
          });
    }
  }

  function recalcSummary() {
    const grades = [...root.querySelectorAll("[data-role='nota']")]
      .map((cell) => parseNumber(cleanText(cell)))
      .filter((value) => value !== null)
      .map((value) => (value > 10 ? value / 10 : value));

    const loads = [...root.querySelectorAll("[data-role='carga-horaria-total']")]
      .map((cell) => parseNumber(cleanText(cell)))
      .filter((value) => value !== null);

    const alerts = root.querySelectorAll(".registro-com-alerta").length;

    if (avgOutput) {
      if (grades.length) {
        const avg =
          grades.reduce((acc, value) => acc + value, 0) / grades.length;
        avgOutput.textContent = avg.toLocaleString("pt-BR", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      } else {
        avgOutput.textContent = "—";
      }
    }

    if (loadOutput) {
      const total = loads.reduce((acc, value) => acc + value, 0);
      loadOutput.textContent = total
        ? total.toLocaleString("pt-BR", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
          })
        : "—";
    }

    if (alertOutput) {
      alertOutput.textContent = String(alerts);
    }
  }

  function collectPayload() {
    const aluno = {};
    root.querySelectorAll("[data-model='aluno'][data-field]").forEach((el) => {
      aluno[el.dataset.field] = cleanText(el);
    });

    const registros = [
      ...root.querySelectorAll("[data-registro-bloco]"),
    ].map((block) => {
      const campos = {};
      block.querySelectorAll("[data-model='registro'][data-field]").forEach(
        (el) => {
          campos[el.dataset.field] = cleanText(el);
        }
      );

      const notas = {};
      block.querySelectorAll("[data-nota]").forEach((el) => {
        const componente = el.dataset.nota;
        const carga = block.querySelector(
          `[data-carga-componente="${componente}"]`
        );
        notas[componente] = {
          valor: cleanText(el),
          carga_horaria: cleanText(carga),
        };
      });

      return {
        id: Number(block.dataset.registroId),
        campos,
        notas,
      };
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
    clearTimeout(saveTimer);
    setSaveState("Alterações pendentes", "");
    saveTimer = window.setTimeout(saveNow, 900);
  }

  function onInput(event) {
    const target = event.target;
    const block = target.closest("[data-registro-bloco]");

    if (target.matches("[data-role='nota']")) {
      evaluateRecord(block, true);
    } else if (target.matches("[data-role='carga-componente']")) {
      recalcRecordLoad(block);
    } else if (target.matches("[data-field='resultado']")) {
      evaluateRecord(block, false);
    }

    recalcSummary();
    scheduleSave();
  }

  function setupEditableFields() {
    if (!canEdit) return;

    root.querySelectorAll("[contenteditable='true']").forEach((element) => {
      element.addEventListener("input", onInput);

      element.addEventListener("blur", () => {
        clearTimeout(saveTimer);
        saveNow();
      });

      element.addEventListener("keydown", (event) => {
        if (
          event.key === "Enter" &&
          element.dataset.multiline !== "1"
        ) {
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
      // O texto institucional continua visível mesmo sem a imagem.
    }
  }

  root.querySelectorAll("[data-registro-bloco]").forEach((block) => {
    evaluateRecord(block, false);
  });
  recalcSummary();
  setupEditableFields();

  if (saveButton) {
    saveButton.addEventListener("click", () => {
      clearTimeout(saveTimer);
      saveNow();
    });
  }

  if (logo) {
    logo.addEventListener("error", hydrateLetterheadFallback, { once: true });
    if (logo.complete && logo.naturalWidth === 0) {
      hydrateLetterheadFallback();
    }
  }
})();
