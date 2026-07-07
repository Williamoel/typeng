(function () {
  const SCROLL_KEY = "typeng:scroll-position";
  const OPTION_STORAGE_PREFIX = "typeng:practice-options:";

  function currentPageKey() {
    return `${window.location.pathname}${window.location.search}`;
  }

  function isPracticePage() {
    return Boolean(document.querySelector("[data-practice-center]"));
  }

  function saveScrollPosition() {
    if (isPracticePage()) {
      return;
    }
    try {
      window.sessionStorage.setItem(
        SCROLL_KEY,
        JSON.stringify({
          page: currentPageKey(),
          x: window.scrollX,
          y: window.scrollY,
          savedAt: Date.now(),
        }),
      );
    } catch (_error) {
      // Ignore storage errors; scroll restoration is a convenience.
    }
  }

  function restoreScrollPosition() {
    if (isPracticePage()) {
      return;
    }
    let payload = null;
    try {
      payload = JSON.parse(window.sessionStorage.getItem(SCROLL_KEY) || "null");
      window.sessionStorage.removeItem(SCROLL_KEY);
    } catch (_error) {
      return;
    }

    if (!payload || Date.now() - Number(payload.savedAt || 0) > 30000) {
      return;
    }

    const targetY = Math.max(0, Number(payload.y || 0));
    window.requestAnimationFrame(() => {
      window.scrollTo(Number(payload.x || 0), targetY);
      window.requestAnimationFrame(() => {
        const maxY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
        window.scrollTo(Number(payload.x || 0), Math.min(targetY, maxY));
      });
    });
  }

  function bindScrollPersistence() {
    document.addEventListener("submit", () => {
      saveScrollPosition();
    }, true);

    document.addEventListener("click", (event) => {
      const link = event.target.closest("a[href]");
      if (!link) {
        return;
      }
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin) {
        return;
      }
      if (link.closest(".topbar")) {
        return;
      }
      saveScrollPosition();
    }, true);
  }

  function clearRow(row) {
    row.querySelectorAll("input, select").forEach((field) => {
      field.value = "";
    });
  }

  function bindAddWordRows() {
    const form = document.querySelector("[data-add-word-form]");
    if (!form) {
      return;
    }

    const rows = form.querySelector("[data-add-word-rows]");
    const addButton = form.querySelector("[data-add-word-row]");
    if (!rows || !addButton) {
      return;
    }

    addButton.addEventListener("click", () => {
      const template = rows.querySelector(".add-word-row");
      if (!template) {
        return;
      }
      const row = template.cloneNode(true);
      clearRow(row);
      rows.appendChild(row);
      const firstInput = row.querySelector("input");
      if (firstInput) {
        firstInput.focus();
      }
    });

    rows.addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-word-row]");
      if (!button) {
        return;
      }
      const row = button.closest(".add-word-row");
      if (!row) {
        return;
      }
      if (rows.querySelectorAll(".add-word-row").length === 1) {
        clearRow(row);
        row.querySelector("input, select")?.focus();
        return;
      }
      row.remove();
    });
  }

  function bindBulkDelete() {
    const form = document.querySelector("[data-bulk-delete-form]");
    if (!form) {
      return;
    }

    const checkboxes = Array.from(document.querySelectorAll("[data-word-select]"));
    const selectAll = document.querySelector("[data-select-all-words]");
    const countLabel = document.querySelector("[data-selected-count]");
    const deleteButton = document.querySelector("[data-bulk-delete-button]");

    function selectedCount() {
      return checkboxes.filter((checkbox) => checkbox.checked).length;
    }

    function updateState() {
      const count = selectedCount();
      if (countLabel) {
        countLabel.textContent = `${count} selected`;
      }
      if (deleteButton) {
        deleteButton.disabled = count === 0;
      }
      if (selectAll) {
        selectAll.checked = count > 0 && count === checkboxes.length;
        selectAll.indeterminate = count > 0 && count < checkboxes.length;
      }
    }

    checkboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", updateState);
    });

    if (selectAll) {
      selectAll.addEventListener("change", () => {
        checkboxes.forEach((checkbox) => {
          checkbox.checked = selectAll.checked;
        });
        updateState();
      });
    }

    form.addEventListener("submit", (event) => {
      const count = selectedCount();
      if (count === 0) {
        event.preventDefault();
        return;
      }
      if (!window.confirm(`Delete ${count} selected words? This cannot be undone.`)) {
        event.preventDefault();
      }
    });

    updateState();
  }

  function bindExcludeForm() {
    const form = document.querySelector("[data-exclude-form]");
    if (!form) {
      return;
    }

    form.addEventListener("submit", (event) => {
      const select = form.querySelector("select[name='source_library_id']");
      const sourceName = select?.selectedOptions?.[0]?.textContent?.trim() || "the selected library";
      if (!window.confirm(`Remove overlapping words from this library using ${sourceName}?`)) {
        event.preventDefault();
      }
    });
  }

  function bindClozeOptions() {
    document.querySelectorAll(".session-options").forEach((fieldset) => {
      const withCloze = fieldset.querySelector("[data-cloze-with]");
      const onlyCloze = fieldset.querySelector("[data-cloze-only]");
      if (!withCloze || !onlyCloze) {
        return;
      }

      withCloze.addEventListener("change", () => {
        if (withCloze.checked) {
          onlyCloze.checked = false;
        }
      });

      onlyCloze.addEventListener("change", () => {
        if (onlyCloze.checked) {
          withCloze.checked = false;
        }
      });
    });
  }

  function centerPracticeView() {
    const wrap = document.querySelector("[data-practice-center]");
    const card = wrap?.querySelector(".practice-card");
    if (!wrap || !card) {
      return;
    }

    window.requestAnimationFrame(() => {
      const rect = card.getBoundingClientRect();
      const targetY = window.scrollY + rect.top + rect.height / 2 - window.innerHeight / 2;
      const maxY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      window.scrollTo({ top: Math.max(0, Math.min(targetY, maxY)), left: 0, behavior: "auto" });
    });
  }

  function optionFormKey(form, index) {
    const action = form.getAttribute("action") || window.location.pathname;
    return `${OPTION_STORAGE_PREFIX}${window.location.pathname}:${action}:${index}`;
  }

  function optionCheckboxes(form) {
    return Array.from(form.querySelectorAll(".session-options input[type='checkbox'][name]"));
  }

  function readSavedOptions(key) {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(key) || "null");
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_error) {
      return null;
    }
  }

  function saveOptions(key, checkboxes) {
    const payload = {};
    checkboxes.forEach((checkbox) => {
      payload[checkbox.name] = checkbox.checked;
    });
    try {
      window.localStorage.setItem(key, JSON.stringify(payload));
    } catch (_error) {
      // Ignore storage errors; options still work for the current page.
    }
  }

  function restorePracticeOptions() {
    const forms = Array.from(document.querySelectorAll("form")).filter((form) => {
      return form.querySelector(".session-options");
    });

    forms.forEach((form, index) => {
      const checkboxes = optionCheckboxes(form);
      if (!checkboxes.length) {
        return;
      }

      const key = optionFormKey(form, index);
      const saved = readSavedOptions(key);
      if (saved) {
        checkboxes.forEach((checkbox) => {
          if (Object.prototype.hasOwnProperty.call(saved, checkbox.name)) {
            checkbox.checked = Boolean(saved[checkbox.name]);
          }
        });
        const withCloze = form.querySelector("[data-cloze-with]");
        const onlyCloze = form.querySelector("[data-cloze-only]");
        if (withCloze?.checked && onlyCloze?.checked) {
          onlyCloze.checked = false;
          saveOptions(key, checkboxes);
        }
      }

      checkboxes.forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
          const withCloze = form.querySelector("[data-cloze-with]");
          const onlyCloze = form.querySelector("[data-cloze-only]");
          if (checkbox === withCloze && checkbox.checked && onlyCloze) {
            onlyCloze.checked = false;
          }
          if (checkbox === onlyCloze && checkbox.checked && withCloze) {
            withCloze.checked = false;
          }
          saveOptions(key, checkboxes);
        });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    restoreScrollPosition();
    bindScrollPersistence();
    bindAddWordRows();
    bindBulkDelete();
    bindExcludeForm();
    bindClozeOptions();
    restorePracticeOptions();
    centerPracticeView();
  });
})();
