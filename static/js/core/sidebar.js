(() => {
  const storageKey = "boostklient-sidebar-collapsed";
  let isCollapsed = false;
  try {
    isCollapsed = window.localStorage.getItem(storageKey) === "true";
  } catch {
    isCollapsed = false;
  }
  document.documentElement.dataset.sidebarCollapsed = String(isCollapsed);

  document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.querySelector("[data-sidebar-toggle]");
    const updateToggle = () => {
      const collapsed = document.documentElement.dataset.sidebarCollapsed === "true";
      const label = collapsed ? toggle?.dataset.expandLabel : toggle?.dataset.collapseLabel;
      toggle?.setAttribute("aria-expanded", String(!collapsed));
      if (label) {
        toggle.setAttribute("aria-label", label);
        toggle.title = label;
      }
    };

    toggle?.addEventListener("click", () => {
      isCollapsed = document.documentElement.dataset.sidebarCollapsed !== "true";
      document.documentElement.dataset.sidebarCollapsed = String(isCollapsed);
      try {
        window.localStorage.setItem(storageKey, String(isCollapsed));
      } catch {
        // Keep the control usable when browser storage is unavailable.
      }
      updateToggle();
    });
    updateToggle();

  });
})();
