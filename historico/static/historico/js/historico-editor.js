(() => {
  "use strict";

  const root = document.querySelector("[data-historico-editor]");
  if (!root) return;

  const canEdit = root.dataset.canEdit === "1";
  const saveUrl = root.dataset.saveUrl || "";
  const csrfToken = document.querySelector("input[name='csrfmiddlewaretoken']")?.value;
  const saveStatus = document.querySelector("[data-save-status]");
  const saveButton = document.querySelector("[data-action='save']");
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
    if (threshold === null) return grade > 10 ? 60 : 6;
    if (threshold <= 1) return grade > 10 ? threshold * 100 : threshold * 10;
    if (threshold > 10 && grade <= 10) return threshold / 10;
    if (threshold <= 10 && grade > 10) return threshold * 10;
    return threshold;
  }

  function registroIds() {
    return [...new Set(
      [...root.querySelectorAll("[data-registro-id]")]
        .map((el) => el.dataset.registroId)
        .filter(Boolean)
    )];
  }

  function evaluateRecord(registroId) {
    if (!registroId) return;

    const notes = [
      ...root.querySelectorAll(
        `[data-role="nota"][data-registro-id="${registroId}"]`
      ),
    ];
    const status = root.querySelector(
      `[data-role="situacao"][data-registro-id="${registroId}"]`
    );

    let failed = false;

    notes.forEach((cell) => {
      const grade = parseNumber(cleanText(cell));
      const threshold = thresholdForGrade(cell.dataset.mediaMinima || "", grade ?? 0);
      const isFailed = grade !== null && grade < threshold;
      cell.classList.toggle("alerta-reprovado", isFailed);
      if (isFailed) failed = true;
    });

    if (status) {
      const statusFailed =
        failed || cleanText(status).toUpperCase() === "REPROVADO";
      status.classList.toggle("alerta-reprovado", statusFailed);
      status.dataset.status = statusFailed ? "reprovado" : "aprovado";
    }
  }

  const monthMap = {
    JANEIRO: "01",
    FEVEREIRO: "02",
    "FEVEREIRO": "02",
    MARÇO: "03",
    MARCO: "03",
    ABRIL: "04",
    MAIO: "05",
    JUNHO: "06",
    JULHO: "07",
    AGOSTO: "08",
    SETEMBRO: "09",
    OUTUBRO: "10",
    NOVEMBRO: "11",
    DEZEMBRO: "12",
  };

  function collectBirthDate(aluno) {
    const dia = cleanText(root.querySelector("[data-date-part='dia']"));
    const mesRaw = cleanText(root.querySelector("[data-date-part='mes']")).toUpperCase();
    const ano = cleanText(root.querySelector("[data-date-part='ano']"));
    const mes = monthMap[mesRaw] || (mesRaw.match(/^\d{1,2}$/) ? mesRaw.padStart(2, "0") : "");

    if (dia && mes && ano) {
      aluno.nascimento = `${dia.padStart(2, "0")}/${mes}/${ano}`;
    }
  }

  function collectPayload() {
    const aluno = {};
    root.querySelectorAll("[data-model='aluno'][data-field]").forEach((el) => {
      aluno[el.dataset.field] = cleanText(el);
    });
    collectBirthDate(aluno);

    const registros = registroIds().map((id) => {
      const campos = {};
      root.querySelectorAll(
        `[data-registro-id="${id}"][data-model="registro"][data-field]`
      ).forEach((el) => {
        campos[el.dataset.field] = cleanText(el);
      });

      const notas = {};
      root.querySelectorAll(
        `[data-registro-id="${id}"][data-nota]`
      ).forEach((el) => {
        notas[el.dataset.nota] = {
          valor: cleanText(el),
          carga_horaria: "",
        };
      });

      return {
        id: Number(id),
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
    const registroId = target.dataset.registroId;

    if (target.matches("[data-role='nota']")) {
      evaluateRecord(registroId);
    }

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
      if (base64) {
        logo.src = `data:image/jpeg;base64,${base64}`;
      }
    } catch (_) {
      // Mantém o restante do documento utilizável se a imagem falhar.
    }
  }

  registroIds().forEach(evaluateRecord);
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
