(() => {
  function initializeConfirmation() {
    const dialog = document.querySelector("[data-form-confirmation]");
    if (!dialog) return;

    const message = dialog.querySelector("[data-confirmation-message]");
    const title = dialog.querySelector("[data-confirmation-title]");
    const kicker = dialog.querySelector("[data-confirmation-kicker]");
    const cancelButton = dialog.querySelector("[data-confirmation-cancel]");
    const acceptButton = dialog.querySelector("[data-confirmation-accept]");
    const defaultTitle = title.textContent;
    const defaultKicker = kicker.textContent;
    const defaultAction = dialog.dataset.confirmationAction;
    const deleteAction = dialog.dataset.confirmationDelete;
    let pendingForm = null;
    let pendingSubmitter = null;
    const approvedForms = new WeakSet();

    const requestConfirmation = (form, submitter) => {
      pendingForm = form;
      pendingSubmitter = submitter;
      message.textContent = form.dataset.confirmMessage;
      const isDelete = form.dataset.confirmAction === "delete";
      title.textContent = form.dataset.confirmTitle || defaultTitle;
      kicker.textContent = isDelete ? deleteAction : defaultKicker;
      acceptButton.textContent = isDelete ? deleteAction : defaultAction;
      acceptButton.classList.toggle("button-danger", isDelete);
      acceptButton.classList.toggle("button-primary", !isDelete);

      if (typeof dialog.showModal !== "function") {
        if (window.confirm(form.dataset.confirmMessage)) {
          approvedForms.add(form);
          if (submitter?.form === form) form.requestSubmit(submitter);
          else form.requestSubmit();
        }
        pendingForm = null;
        pendingSubmitter = null;
        return;
      }
      dialog.showModal();
      cancelButton.focus();
    };

    const handleSubmit = (event) => {
      const form = event.currentTarget;
      if (approvedForms.has(form)) {
        approvedForms.delete(form);
        return;
      }
      event.preventDefault();
      requestConfirmation(form, event.submitter);
    };

    document.querySelectorAll("form[data-confirm-message]").forEach((form) => {
      form.addEventListener("submit", handleSubmit);
    });
    cancelButton.addEventListener("click", () => dialog.close());
    dialog.addEventListener("cancel", () => {
      pendingForm = null;
      pendingSubmitter = null;
    });
    dialog.addEventListener("close", () => {
      if (!pendingForm) return;
      const form = pendingForm;
      const submitter = pendingSubmitter;
      pendingForm = null;
      pendingSubmitter = null;
      if (dialog.returnValue !== "confirm") return;
      approvedForms.add(form);
      if (submitter?.form === form) form.requestSubmit(submitter);
      else form.requestSubmit();
    });
    acceptButton.addEventListener("click", () => dialog.close("confirm"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeConfirmation, { once: true });
  } else {
    initializeConfirmation();
  }
})();
