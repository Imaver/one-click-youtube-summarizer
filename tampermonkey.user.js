// ==UserScript==
// @name         YouTube Claude Summarizer
// @namespace    http://tampermonkey.net/
// @version      1.1
// @description  One-click YouTube video summarization via Claude Code
// @match        https://www.youtube.com/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function () {
  "use strict";

  const BUTTON_CLASS = "ytsum-summarize-btn";
  const POLL_INTERVAL_MS = 500;
  const MAX_POLL_ATTEMPTS = 30;

  function createButton() {
    // Build a button that matches YouTube's native action button style
    const ytBtn = document.createElement("yt-button-view-model");
    ytBtn.className = "ytd-menu-renderer";

    const btnVM = document.createElement("button-view-model");
    btnVM.className =
      "ytSpecButtonViewModelHost style-scope ytd-menu-renderer";

    const btn = document.createElement("button");
    btn.className =
      "yt-spec-button-shape-next yt-spec-button-shape-next--tonal " +
      "yt-spec-button-shape-next--mono yt-spec-button-shape-next--size-m " +
      BUTTON_CLASS;
    btn.setAttribute("aria-label", "Summarize with Claude");

    // Icon (clipboard/document icon, 24x24 Material Design)
    const iconDiv = document.createElement("div");
    iconDiv.setAttribute("aria-hidden", "true");
    iconDiv.className = "yt-spec-button-shape-next__icon";
    iconDiv.style.cssText = "width:24px;height:24px";

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("height", "24");
    svg.setAttribute("width", "24");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("focusable", "false");
    svg.setAttribute("aria-hidden", "true");
    svg.style.cssText =
      "pointer-events:none;display:inherit;width:100%;height:100%;fill:currentcolor";

    const path = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "path"
    );
    // Clipboard/summarize icon
    path.setAttribute(
      "d",
      "M19 3h-4.18C14.4 1.84 13.3 1 12 1s-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7-1c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm-2 14H7v-2h3v2zm5-4H7v-2h8v2zm2-4H7V6h10v2z"
    );
    svg.appendChild(path);
    iconDiv.appendChild(svg);

    // Label
    const labelDiv = document.createElement("div");
    labelDiv.className =
      "yt-spec-button-shape-next--button-text-content";
    labelDiv.style.cssText = "margin-left:6px;white-space:nowrap";
    labelDiv.textContent = "Summarize";

    // Touch feedback (matches YouTube native buttons)
    const feedback = document.createElement("yt-touch-feedback-shape");
    feedback.className =
      "yt-spec-touch-feedback-shape yt-spec-touch-feedback-shape--touch-response";
    feedback.setAttribute("aria-hidden", "true");
    const stroke = document.createElement("div");
    stroke.className = "yt-spec-touch-feedback-shape__stroke";
    const fill = document.createElement("div");
    fill.className = "yt-spec-touch-feedback-shape__fill";
    feedback.append(stroke, fill);

    btn.append(iconDiv, labelDiv, feedback);
    btn.style.cssText = "display:inline-flex;align-items:center;cursor:pointer";

    btn.addEventListener("click", () => {
      const url = encodeURIComponent(window.location.href);
      window.location.href = "ytsum://" + url;
    });

    btnVM.appendChild(btn);
    ytBtn.appendChild(btnVM);

    // Wrapper div for spacing + tooltip
    const wrapper = document.createElement("div");
    wrapper.style.cssText = "display:inline-block;margin-left:8px";

    const tooltip = document.createElement("tp-yt-paper-tooltip");
    tooltip.setAttribute("offset", "8");
    tooltip.setAttribute("role", "tooltip");
    const tooltipText = document.createElement("div");
    tooltipText.className = "style-scope tp-yt-paper-tooltip";
    tooltipText.textContent = "Summarize with Claude";
    tooltip.appendChild(tooltipText);

    wrapper.append(ytBtn, tooltip);
    return wrapper;
  }

  function injectButton() {
    if (!location.pathname.startsWith("/watch") && !location.pathname.startsWith("/shorts")) return;

    let attempts = 0;
    const poller = setInterval(() => {
      if (++attempts > MAX_POLL_ATTEMPTS) {
        clearInterval(poller);
        return;
      }

      const menu = document.querySelector(
        "ytd-watch-metadata ytd-menu-renderer, #menu-container ytd-menu-renderer"
      );
      if (!menu) return;

      clearInterval(poller);

      // Don't inject twice
      if (menu.querySelector("." + BUTTON_CLASS)) return;

      const btn = createButton();
      const insertIdx = Math.max(menu.children.length - 1, 0);
      menu.insertBefore(btn, menu.children[insertIdx]);
    }, POLL_INTERVAL_MS);
  }

  // YouTube SPA navigation
  window.addEventListener("yt-navigate-finish", injectButton);

  // Initial injection
  injectButton();
})();
