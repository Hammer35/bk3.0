(() => {
  const STORAGE_KEY = "boostklient-theme";
  const root = document.documentElement;

  function systemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function apply(theme) {
    const resolved = theme === "system" ? systemTheme() : theme;
    root.dataset.theme = resolved;
  }

  let selected = localStorage.getItem(STORAGE_KEY) || "system";
  apply(selected);

  document.addEventListener("DOMContentLoaded", () => {
    const button = document.querySelector("[data-theme-toggle]");
    if (!button) return;

    button.addEventListener("click", () => {
      const current = root.dataset.theme;
      selected = current === "dark" ? "light" : "dark";
      localStorage.setItem(STORAGE_KEY, selected);
      apply(selected);
    });
  });
})();
