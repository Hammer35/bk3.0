(() => {
  const control = document.querySelector("[data-interface-scale-control]");
  if (!control) return;

  const root = document.documentElement;
  const output = control.querySelector("[data-interface-scale-value]");
  const decreaseButton = control.querySelector("[data-interface-scale-decrease]");
  const increaseButton = control.querySelector("[data-interface-scale-increase]");
  const resetButton = control.querySelector("[data-interface-scale-reset]");
  const status = control.querySelector("[data-interface-scale-status]");
  const minimum = 100;
  const maximum = 200;
  const step = 5;
  let fontScalePercent = Number(root.dataset.interfaceFontScale) || minimum;
  let saving = false;

  const render = () => {
    output.value = `${fontScalePercent}%`;
    output.textContent = `${fontScalePercent}%`;
    root.style.setProperty("--interface-font-scale", String(fontScalePercent / 100));
    root.dataset.fontScaleLarge = String(fontScalePercent > minimum);
    decreaseButton.disabled = saving || fontScalePercent <= minimum;
    increaseButton.disabled = saving || fontScalePercent >= maximum;
    resetButton.disabled = saving || fontScalePercent === minimum;
  };

  const csrfToken = () => {
    const tokenField = control.parentElement.querySelector("input[name='csrfmiddlewaretoken']");
    if (tokenField?.value) return tokenField.value;
    const cookie = document.cookie.split(";").map((item) => item.trim()).find((item) => item.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.slice("csrftoken=".length)) : "";
  };

  const persist = async (nextFontScalePercent) => {
    if (saving || nextFontScalePercent === fontScalePercent) return;
    const previousFontScalePercent = fontScalePercent;
    fontScalePercent = nextFontScalePercent;
    saving = true;
    status.textContent = control.dataset.savingLabel;
    render();

    try {
      const response = await fetch(control.dataset.saveUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
          "X-CSRFToken": csrfToken(),
        },
        body: new URLSearchParams({ font_scale_percent: String(fontScalePercent) }),
      });
      if (!response.ok) throw new Error("interface_font_scale_save_failed");
      const result = await response.json();
      if (!Number.isInteger(result.font_scale_percent) || result.font_scale_percent !== fontScalePercent) {
        throw new Error("interface_font_scale_save_invalid_response");
      }
      status.textContent = control.dataset.savedLabel;
    } catch {
      fontScalePercent = previousFontScalePercent;
      status.textContent = control.dataset.errorLabel;
    } finally {
      saving = false;
      render();
    }
  };

  decreaseButton.addEventListener("click", () => persist(Math.max(minimum, fontScalePercent - step)));
  increaseButton.addEventListener("click", () => persist(Math.min(maximum, fontScalePercent + step)));
  resetButton.addEventListener("click", () => persist(minimum));

  document.addEventListener("pointerdown", (event) => {
    if (control.open && !control.contains(event.target)) control.open = false;
  });
  control.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !control.open) return;
    event.preventDefault();
    control.open = false;
    control.querySelector("summary").focus();
  });

  render();
})();
