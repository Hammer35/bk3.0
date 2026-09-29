(() => {
  const STORAGE_KEY = "boostklient-theme";
  const root = document.documentElement;
  const fontScalePercent = Number(root.dataset.interfaceFontScale);
  if (Number.isInteger(fontScalePercent) && fontScalePercent >= 100 && fontScalePercent <= 200) {
    root.style.setProperty("--interface-font-scale", String(fontScalePercent / 100));
    root.dataset.fontScaleLarge = String(fontScalePercent > 100);
  }

  function systemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function apply(theme) {
    const resolved = theme === "system" ? systemTheme() : theme;
    root.dataset.theme = resolved;
  }

  let selected = localStorage.getItem(STORAGE_KEY) || "light";
  apply(selected);

  document.addEventListener("DOMContentLoaded", () => {
    const buttons = document.querySelectorAll("[data-theme-toggle]");

    function syncButtons() {
      const current = root.dataset.theme;
      buttons.forEach((button) => {
        const label = current === "dark" ? button.dataset.themeLabelDark : button.dataset.themeLabelLight;
        button.setAttribute("aria-pressed", String(current === "dark"));
        button.setAttribute("aria-label", label);
        const output = button.querySelector("[data-theme-label]");
        if (output) output.textContent = label;
      });
    }

    syncButtons();
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        selected = root.dataset.theme === "dark" ? "light" : "dark";
        localStorage.setItem(STORAGE_KEY, selected);
        apply(selected);
        syncButtons();
      });
    });
  });
})();
