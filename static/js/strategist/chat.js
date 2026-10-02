(() => {
  const history = document.querySelector(".chat-history");
  const form = document.getElementById("chat-composer");
  if (!history || !form) return;

  const messageField = form.querySelector("textarea");
  const sendButton = form.querySelector("button[type='submit']");
  const requestError = form.querySelector(".chat-request-error");
  const chatMap = document.querySelector("[data-chat-map]");
  const sessionItem = document.querySelector(".sidebar-session.is-current");

  const showError = (message) => {
    if (!requestError) return;
    requestError.textContent = message;
    requestError.hidden = !message;
  };

  const resizeComposer = () => {
    if (!messageField) return;
    const maxHeight = Math.max(44, Math.floor(window.innerHeight / 3));
    messageField.style.height = "auto";
    const nextHeight = Math.min(messageField.scrollHeight, maxHeight);
    messageField.style.height = `${nextHeight}px`;
    messageField.style.overflowY = messageField.scrollHeight > maxHeight ? "auto" : "hidden";
  };

  function addChatMapItem(messageNode) {
    if (!chatMap || chatMap.querySelector(`[data-chat-target="${messageNode.id}"]`)) return;
    chatMap.querySelector(".chat-map-empty")?.remove();

    const question = messageNode.querySelector(".chat-message-content")?.textContent?.trim() || "";
    const item = document.createElement("li");
    const button = document.createElement("button");
    const index = document.createElement("span");
    const text = document.createElement("span");
    button.type = "button";
    button.className = "chat-map-item";
    button.dataset.chatTarget = messageNode.id;
    button.title = question;
    button.setAttribute("aria-label", question);
    index.className = "chat-map-index";
    index.textContent = String(chatMap.querySelectorAll(".chat-map-item").length + 1).padStart(2, "0");
    text.className = "chat-map-item-text";
    text.textContent = question;
    button.append(index, text);
    item.append(button);
    chatMap.append(item);
  }

  const createOptimisticUserMessage = (content) => {
    const message = document.createElement("article");
    const author = document.createElement("strong");
    const body = document.createElement("div");
    message.id = `chat-message-pending-${Date.now()}`;
    message.className = "chat-message chat-message-user";
    message.tabIndex = -1;
    author.textContent = form.dataset.userLabel || "Вы";
    body.className = "chat-message-content";
    body.textContent = content;
    message.append(author, body);
    return message;
  };

  const appendMessages = (markup, optimisticMessage = null) => {
    if (!markup) return null;
    history.querySelector(".empty-state")?.remove();
    const template = document.createElement("template");
    template.innerHTML = markup;
    const serverUserMessages = [...template.content.querySelectorAll(".chat-message-user[id]")];
    if (optimisticMessage?.isConnected && serverUserMessages.length) {
      const canonicalUserMessage = serverUserMessages.shift();
      optimisticMessage.replaceWith(canonicalUserMessage);
      addChatMapItem(canonicalUserMessage);
    } else if (optimisticMessage?.isConnected) {
      optimisticMessage.remove();
    }
    const lastMessage = template.content.querySelector(".chat-message:last-child");
    history.append(template.content);
    serverUserMessages.forEach(addChatMapItem);
    return lastMessage ? history.lastElementChild : null;
  };

  chatMap?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-chat-target]");
    if (!button) return;
    const target = document.getElementById(button.dataset.chatTarget);
    target?.scrollIntoView({
      block: "center",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
    target?.focus({ preventScroll: true });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (form.dataset.submitting === "true") return;
    const submittedMessage = messageField?.value || "";
    if (!submittedMessage.trim()) {
      messageField?.focus();
      return;
    }
    const formData = new FormData(form);
    const optimisticMessage = createOptimisticUserMessage(submittedMessage);
    history.querySelector(".empty-state")?.remove();
    history.append(optimisticMessage);
    messageField.value = "";
    resizeComposer();
    optimisticMessage.scrollIntoView({ block: "nearest", behavior: "smooth" });

    form.dataset.submitting = "true";
    form.setAttribute("aria-busy", "true");
    if (sendButton) sendButton.disabled = true;
    showError("");

    try {
      const response = await fetch(form.action || window.location.href, {
        method: "POST",
        body: formData,
        headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
      });
      const result = await response.json();
      const lastMessage = appendMessages(result.messages_html, optimisticMessage);

      if (result.conversation_url) {
        window.history.replaceState({}, "", result.conversation_url);
        form.action = result.conversation_url;
      }
      if (result.conversation_title && sessionItem) {
        const sessionLink = sessionItem.querySelector(".sidebar-session-link");
        const deleteForm = sessionItem.querySelector("[data-delete-session]");
        const sessionTitle = sessionItem.querySelector(".sidebar-session-title");
        if (sessionLink) {
          sessionLink.href = result.conversation_url;
          sessionLink.title = result.conversation_title;
        }
        if (sessionTitle) sessionTitle.textContent = result.conversation_title;
        if (deleteForm && result.delete_url) deleteForm.action = result.delete_url;
      }

      if (result.messages_html) {
        messageField.value = "";
        resizeComposer();
        lastMessage?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
      if (result.error) {
        showError(result.error);
      } else if (result.errors) {
        optimisticMessage.remove();
        messageField.value = submittedMessage;
        resizeComposer();
        const errors = Object.values(result.errors).flat().map((item) => item.message);
        showError(errors.join(" "));
      } else if (!response.ok) {
        showError(requestError?.dataset.networkError || "");
      }
    } catch {
      showError(requestError?.dataset.networkError || "");
    } finally {
      form.dataset.submitting = "false";
      form.removeAttribute("aria-busy");
      if (sendButton) sendButton.disabled = false;
    }
  });

  messageField?.addEventListener("input", resizeComposer);
  window.addEventListener("resize", resizeComposer);
  messageField?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    form.requestSubmit();
  });
  resizeComposer();
})();
