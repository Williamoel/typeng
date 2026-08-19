(() => {
  const panel = document.querySelector("[data-cloze-feedback]");
  if (!panel || !window.fetch) return;

  panel.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button");
      if (!button) return;
      button.disabled = true;
      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          credentials: "same-origin",
          headers: { "X-Requested-With": "fetch" },
        });
        if (!response.ok) throw new Error(`feedback request failed: ${response.status}`);
        panel.querySelectorAll(".cloze-feedback-option").forEach((option) => {
          const selected = option === button;
          option.classList.toggle("selected", selected);
          option.setAttribute("aria-pressed", selected ? "true" : "false");
        });
        const status = panel.querySelector(".cloze-feedback-status");
        if (status) status.textContent = "已记录，可以继续下一题";
      } catch (_error) {
        form.submit();
      } finally {
        button.disabled = false;
      }
    });
  });
})();
