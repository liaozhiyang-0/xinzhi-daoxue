(() => {
  "use strict";

  const cache = new Map();
  const statusLabels = {
    ready: "正常", running: "运行中", success: "成功", completed: "完成",
    partial: "部分完成", degraded: "降级运行", planned: "开发中", mock: "开发模拟",
    failed: "失败", disabled: "已停用", not_configured: "未配置", unknown: "未知",
    ok: "正常", healthy: "正常", configured: "已配置", published: "已发布",
  };
  const nav = [
    { group: "学习", items: [
      { id: "workspace", href: "/workspace", label: "智能任务工作台", short: "学" },
    ] },
    { group: "开发与调试", items: [
      { id: "execution", href: "/debug/execution", label: "执行调试", short: "执" },
      { id: "agents", href: "/debug/agents", label: "Agent 管理", short: "A" },
      { id: "system", href: "/system", label: "系统状态", short: "S" },
    ] },
    { group: "演示", items: [
      { id: "demo", href: "/demo", label: "演示中心", short: "演" },
    ] },
  ];

  const $ = (selector, root = document) => root.querySelector(selector);
  const all = (selector, root = document) => [...root.querySelectorAll(selector)];
  const el = (tag, attrs = {}, children = []) => {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([key, value]) => {
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value ?? "";
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
      else if (value !== false && value != null) node.setAttribute(key, value === true ? "" : String(value));
    });
    const list = Array.isArray(children) ? children : [children];
    list.filter((item) => item != null).forEach((item) => node.append(item.nodeType ? item : document.createTextNode(String(item))));
    return node;
  };

  async function api(path, options = {}, ttlMs = 0) {
    const key = `${options.method || "GET"}:${path}`;
    const cached = cache.get(key);
    if (ttlMs && cached && Date.now() - cached.at < ttlMs) return cached.data;
    const response = await fetch(path, options);
    const text = await response.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch { data = { detail: text }; }
    if (!response.ok) throw new Error(data.error?.message || data.detail || `HTTP ${response.status}`);
    if (ttlMs) cache.set(key, { at: Date.now(), data });
    return data;
  }

  function normalizeStatus(value) {
    const raw = String(value || "unknown").toLowerCase();
    if (["available", "enabled", "passed", "valid"].includes(raw)) return "ready";
    if (["error", "unavailable", "invalid", "cancelled"].includes(raw)) return "failed";
    return statusLabels[raw] ? raw : "unknown";
  }

  function badge(value, label) {
    const status = normalizeStatus(value);
    return el("span", { class: `status-badge status-${status}`, text: label || statusLabels[status], "data-status": status });
  }

  function preferredTheme() {
    return localStorage.getItem("xinzhi_theme") || "system";
  }

  function applyTheme(theme = preferredTheme()) {
    const resolved = theme === "system" ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : theme;
    document.documentElement.dataset.theme = resolved;
    document.documentElement.dataset.themePreference = theme;
    all("[data-theme-choice]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme)));
  }

  function setTheme(theme) {
    localStorage.setItem("xinzhi_theme", theme);
    applyTheme(theme);
  }

  function shellNav(page, audience = "developer") {
    const wrapper = el("div", { class: "sidebar-inner" });
    wrapper.append(el("a", { class: "brand-lockup", href: "/", "aria-label": "返回芯智导学首页" }, [
      el("span", { class: "brand-mark", text: "芯" }),
      el("span", { class: "brand-copy" }, [el("strong", { text: "芯智导学" }), el("small", { text: "电子信息课程群智能学习平台" })]),
    ]));
    const menu = el("nav", { class: "sidebar-nav", "aria-label": "主导航" });
    const sections = audience === "student" ? nav.filter((section) => section.group === "学习") : nav;
    sections.forEach((section) => {
      const group = el("div", { class: "nav-group" });
      group.append(el("p", { class: "nav-group-label", text: section.group }));
      section.items.forEach((item) => {
        group.append(el("a", {
          class: `nav-link${page === item.id ? " active" : ""}`, href: item.href,
          "aria-current": page === item.id ? "page" : null, title: item.label,
        }, [el("span", { class: "nav-icon", text: item.short }), el("span", { class: "nav-label", text: item.label })]));
      });
      menu.append(group);
    });
    wrapper.append(menu);
    const footer = el("div", { class: "sidebar-footer" });
    if (audience !== "student") {
      footer.append(el("div", { class: "environment-row" }, [
        el("span", { class: "environment-copy", text: "Development" }),
        el("span", { id: "global-health", class: "status-dot", title: "正在检查本地 API" }),
      ]));
    }
    const theme = el("div", { class: "theme-switcher", role: "group", "aria-label": "主题" });
    [["light", "浅色"], ["dark", "深色"], ["system", "跟随系统"]].forEach(([value, label]) => {
      theme.append(el("button", { type: "button", text: label, "data-theme-choice": value, onclick: () => setTheme(value) }));
    });
    footer.append(theme);
    footer.append(el("button", { type: "button", class: "sidebar-collapse", text: "收起侧栏", onclick: toggleSidebar }));
    wrapper.append(footer);
    return wrapper;
  }

  function toggleSidebar() {
    document.body.classList.toggle("sidebar-collapsed");
    localStorage.setItem("xinzhi_sidebar_collapsed", String(document.body.classList.contains("sidebar-collapsed")));
  }

  function initShell({ page, title, description = "", context = "", audience = "developer" }) {
    const sidebar = $("#app-sidebar");
    const topbar = $("#app-topbar");
    if (sidebar) sidebar.replaceChildren(shellNav(page, audience));
    if (topbar) {
      const menuButton = el("button", { class: "mobile-menu-button", type: "button", text: "菜单", "aria-label": "打开导航", onclick: () => document.body.classList.toggle("drawer-open") });
      const heading = el("div", { class: "topbar-title" }, [el("strong", { text: title }), el("span", { text: description })]);
      const right = el("div", { class: "topbar-actions" });
      if (context) right.append(el("span", { class: "topbar-context", text: context }));
      if (new URLSearchParams(location.search).get("presentation") === "1") {
        document.body.classList.add("presentation-mode");
        right.append(el("a", { class: "button secondary", href: location.pathname, text: "退出演示模式" }));
      }
      topbar.replaceChildren(menuButton, heading, right);
    }
    if (localStorage.getItem("xinzhi_sidebar_collapsed") === "true") document.body.classList.add("sidebar-collapsed");
    applyTheme();
    matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => { if (preferredTheme() === "system") applyTheme("system"); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") document.body.classList.remove("drawer-open"); });
    api("/api/v1/health", {}, 10000).then((data) => {
      const dot = $("#global-health"); if (dot) { dot.classList.add(data.status === "ok" ? "ready" : "degraded"); dot.title = data.status === "ok" ? "本地 API 正常" : "本地 API 降级"; }
    }).catch(() => { const dot = $("#global-health"); if (dot) { dot.classList.add("failed"); dot.title = "无法连接本地 API"; } });
  }

  const mathSymbols = Object.freeze({
    alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", varepsilon: "ϵ",
    zeta: "ζ", eta: "η", theta: "θ", vartheta: "ϑ", iota: "ι", kappa: "κ",
    lambda: "λ", mu: "μ", nu: "ν", xi: "ξ", omicron: "ο", pi: "π", varpi: "ϖ",
    rho: "ρ", varrho: "ϱ", sigma: "σ", varsigma: "ς", tau: "τ", upsilon: "υ",
    phi: "φ", varphi: "ϕ", chi: "χ", psi: "ψ", omega: "ω",
    Gamma: "Γ", Delta: "Δ", Theta: "Θ", Lambda: "Λ", Xi: "Ξ", Pi: "Π",
    Sigma: "Σ", Upsilon: "Υ", Phi: "Φ", Psi: "Ψ", Omega: "Ω",
    cdot: "·", times: "×", div: "÷", pm: "±", mp: "∓", le: "≤", leq: "≤",
    ge: "≥", geq: "≥", ne: "≠", neq: "≠", approx: "≈", equiv: "≡", propto: "∝",
    to: "→", rightarrow: "→", Rightarrow: "⇒", leftarrow: "←", Leftrightarrow: "⇔",
    iff: "⇔", infty: "∞", partial: "∂", nabla: "∇", sum: "∑", prod: "∏",
    int: "∫", iint: "∬", iiint: "∭", oint: "∮", degree: "°", angle: "∠",
    parallel: "∥", perp: "⊥", therefore: "∴", because: "∵", ell: "ℓ", hbar: "ℏ",
    ldots: "…", cdots: "⋯", vdots: "⋮", ddots: "⋱", ohm: "Ω",
  });
  const mathOperators = new Set([
    "sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan",
    "sinh", "cosh", "tanh", "ln", "log", "exp", "lim", "max", "min", "det",
  ]);
  const mathSpaces = Object.freeze({ ",": " ", ";": " ", ":": " ", quad: " ", qquad: "  ", "!": "" });

  function appendMathExpression(target, state, stopAtBrace = false, oneToken = false) {
    let tokens = 0;
    while (state.index < state.source.length) {
      if (stopAtBrace && state.source[state.index] === "}") { state.index += 1; break; }
      appendMathToken(target, state);
      tokens += 1;
      if (oneToken && tokens === 1) break;
    }
  }

  function mathArgument(state, className = "") {
    while (/\s/.test(state.source[state.index] || "")) state.index += 1;
    const node = el("span", { class: className || null });
    if (state.source[state.index] === "{") {
      state.index += 1;
      appendMathExpression(node, state, true);
    } else {
      appendMathExpression(node, state, false, true);
    }
    return node;
  }

  function rawMathArgument(state) {
    while (/\s/.test(state.source[state.index] || "")) state.index += 1;
    if (state.source[state.index] !== "{") return "";
    state.index += 1;
    const start = state.index;
    let depth = 1;
    while (state.index < state.source.length && depth > 0) {
      const value = state.source[state.index];
      if (value === "{") depth += 1;
      if (value === "}") depth -= 1;
      state.index += 1;
    }
    return state.source.slice(start, Math.max(start, state.index - 1));
  }

  function appendMathCommand(target, state) {
    state.index += 1;
    if (state.source[state.index] === "\\") {
      state.index += 1;
      target.append(el("br", { class: "math-line-break" }));
      return;
    }
    const commandStart = state.index;
    while (/[A-Za-z]/.test(state.source[state.index] || "")) state.index += 1;
    let command = state.source.slice(commandStart, state.index);
    if (!command) {
      command = state.source[state.index] || "";
      state.index += command ? 1 : 0;
    }
    if (Object.hasOwn(mathSymbols, command)) {
      target.append(document.createTextNode(mathSymbols[command]));
      return;
    }
    if (Object.hasOwn(mathSpaces, command)) {
      target.append(document.createTextNode(mathSpaces[command]));
      return;
    }
    if (mathOperators.has(command)) {
      target.append(el("span", { class: "math-operator", text: command }));
      return;
    }
    if (["left", "right"].includes(command)) return;
    if (["begin", "end"].includes(command)) { rawMathArgument(state); return; }
    if (command === "frac" || command === "dfrac" || command === "tfrac") {
      const numerator = mathArgument(state, "math-numerator");
      const denominator = mathArgument(state, "math-denominator");
      target.append(el("span", { class: "math-fraction" }, [numerator, denominator]));
      return;
    }
    if (command === "sqrt") {
      let rootIndex = "";
      if (state.source[state.index] === "[") {
        const end = state.source.indexOf("]", state.index + 1);
        if (end !== -1) { rootIndex = state.source.slice(state.index + 1, end); state.index = end + 1; }
      }
      const radicand = mathArgument(state, "math-radicand");
      target.append(el("span", { class: "math-root" }, [
        rootIndex ? el("sup", { class: "math-root-index", text: rootIndex }) : null,
        el("span", { class: "math-root-sign", text: "√" }), radicand,
      ]));
      return;
    }
    const wrappers = {
      text: "math-text", textrm: "math-roman", mathrm: "math-roman", mathbf: "math-bold",
      mathit: "math-italic", operatorname: "math-operator", boxed: "math-boxed",
      overline: "math-overline", underline: "math-underline", vec: "math-vector",
      hat: "math-hat", bar: "math-overline",
    };
    if (Object.hasOwn(wrappers, command)) {
      target.append(mathArgument(state, wrappers[command]));
      return;
    }
    if (["displaystyle", "textstyle", "scriptstyle", "limits", "nolimits"].includes(command)) return;
    if (["{", "}", "$", "%", "#", "_", "&"].includes(command)) {
      target.append(document.createTextNode(command));
      return;
    }
    target.append(el("span", { class: "math-unknown-command", text: command }));
  }

  function appendMathToken(target, state) {
    const value = state.source[state.index];
    if (value === "\\") { appendMathCommand(target, state); return; }
    if (value === "{") { state.index += 1; appendMathExpression(target, state, true); return; }
    if (value === "^" || value === "_") {
      state.index += 1;
      const argument = mathArgument(state, value === "^" ? "math-superscript" : "math-subscript");
      const wrapper = el(value === "^" ? "sup" : "sub");
      wrapper.append(...argument.childNodes);
      target.append(wrapper);
      return;
    }
    if (value === "~") { state.index += 1; target.append(document.createTextNode(" ")); return; }
    if (value === "&") { state.index += 1; target.append(document.createTextNode(" ")); return; }
    if (/\s/.test(value || "")) {
      while (/\s/.test(state.source[state.index] || "")) state.index += 1;
      target.append(document.createTextNode(" "));
      return;
    }
    state.index += 1;
    target.append(document.createTextNode(value || ""));
  }

  function renderLatex(source, display = false) {
    const latex = String(source || "").trim();
    const outer = el(display ? "div" : "span", {
      class: `math-expression ${display ? "math-display" : "math-inline"}`,
      role: "img", "aria-label": latex || "空公式", title: latex,
    });
    const fallback = () => {
      outer.classList.add("math-render-error");
      outer.dataset.latexFallback = "true";
      outer.replaceChildren(el("code", { class: "math-latex-fallback", text: latex || "空公式" }));
    };
    const dangerous = /\\(?:input|include|write|openout|read|usepackage|documentclass|newcommand|def|href)\b/;
    if (!latex || dangerous.test(latex) || !window.katex?.render) {
      fallback();
      return outer;
    }
    try {
      window.katex.render(latex, outer, {
        displayMode: display,
        throwOnError: true,
        strict: "warn",
        trust: false,
        output: "htmlAndMathml",
        maxExpand: 1000,
        maxSize: 20,
      });
    } catch (_error) {
      fallback();
    }
    return outer;
  }

  function findInlineMathEnd(text, start, delimiter) {
    let index = start;
    while (index < text.length) {
      const found = text.indexOf(delimiter, index);
      if (found === -1) return -1;
      let slashes = 0;
      for (let cursor = found - 1; cursor >= 0 && text[cursor] === "\\"; cursor -= 1) slashes += 1;
      if (slashes % 2 === 0) return found;
      index = found + delimiter.length;
    }
    return -1;
  }

  function appendRichInline(node, source) {
    const text = String(source || "");
    let plain = "";
    const flush = () => { if (plain) { node.append(document.createTextNode(plain)); plain = ""; } };
    for (let index = 0; index < text.length;) {
      if (text[index] === "`") {
        const end = text.indexOf("`", index + 1);
        if (end !== -1) {
          flush();
          node.append(el("code", { text: text.slice(index + 1, end) }));
          index = end + 1;
          continue;
        }
      }
      const citation = text.slice(index).match(/^\[(S\d+)\]/);
      if (citation) {
        flush();
        node.append(el("button", { type: "button", class: "citation-link", text: citation[1], "data-evidence-ref": citation[1], "aria-label": `查看证据 ${citation[1]}` }));
        index += citation[0].length;
        continue;
      }
      if (text.startsWith("\\(", index)) {
        const end = findInlineMathEnd(text, index + 2, "\\)");
        if (end !== -1) {
          flush(); node.append(renderLatex(text.slice(index + 2, end))); index = end + 2; continue;
        }
      }
      if (text[index] === "$" && text[index + 1] !== "$" && text[index - 1] !== "\\") {
        const end = findInlineMathEnd(text, index + 1, "$");
        if (end !== -1) {
          flush(); node.append(renderLatex(text.slice(index + 1, end))); index = end + 1; continue;
        }
      }
      if (text.startsWith("\\$", index)) { plain += "$"; index += 2; continue; }
      plain += text[index]; index += 1;
    }
    flush();
    return node;
  }

  function splitTableRow(line) {
    const value = String(line || "").trim().replace(/^\|/, "").replace(/\|$/, "");
    return value.split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, "|"));
  }

  function renderTable(lines) {
    const table = el("table", { class: "markdown-table" });
    const head = el("thead"); const body = el("tbody");
    const headers = splitTableRow(lines[0]);
    head.append(el("tr", {}, headers.map((cell) => appendRichInline(el("th"), cell))));
    lines.slice(2).forEach((line) => {
      body.append(el("tr", {}, splitTableRow(line).map((cell) => appendRichInline(el("td"), cell))));
    });
    table.append(head, body);
    return el("div", { class: "table-wrap" }, table);
  }

  function renderMarkdown(target, source) {
    target.replaceChildren();
    const lines = String(source || "").replace(/\r/g, "").split("\n");
    let code = null; let list = null;
    const flushList = () => { if (list) { target.append(list); list = null; } };
    for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
      const line = lines[lineIndex];
      if (line.trim().startsWith("```")) { flushList(); if (code) { target.append(code); code = null; } else code = el("pre", { class: "code-block" }, el("code")); continue; }
      if (code) { code.firstChild.append(document.createTextNode(`${line}\n`)); continue; }
      if (!line.trim()) { flushList(); continue; }
      const trimmed = line.trim();
      const blockStart = trimmed.startsWith("$$") ? "$$" : trimmed.startsWith("\\[") ? "\\[" : "";
      if (blockStart) {
        flushList();
        const blockEnd = blockStart === "$$" ? "$$" : "\\]";
        let formula = trimmed.slice(blockStart.length);
        const sameLineEnd = formula.indexOf(blockEnd);
        if (sameLineEnd !== -1) formula = formula.slice(0, sameLineEnd);
        else {
          const formulaLines = [formula];
          while (lineIndex + 1 < lines.length) {
            lineIndex += 1;
            const next = lines[lineIndex];
            const end = next.indexOf(blockEnd);
            if (end !== -1) { formulaLines.push(next.slice(0, end)); break; }
            formulaLines.push(next);
          }
          formula = formulaLines.join("\n");
        }
        target.append(renderLatex(formula, true));
        continue;
      }
      if (line.includes("|") && lineIndex + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[lineIndex + 1])) {
        flushList();
        const tableLines = [line, lines[lineIndex + 1]];
        lineIndex += 2;
        while (lineIndex < lines.length && lines[lineIndex].includes("|")) {
          tableLines.push(lines[lineIndex]);
          lineIndex += 1;
        }
        lineIndex -= 1;
        target.append(renderTable(tableLines));
        continue;
      }
      const heading = line.match(/^(#{1,4})\s+(.+)$/);
      if (heading) { flushList(); target.append(appendRichInline(el(`h${Math.min(heading[1].length + 1, 5)}`), heading[2])); continue; }
      const item = line.match(/^[-*]\s+(.+)$/);
      if (item) { if (!list) list = el("ul"); list.append(appendRichInline(el("li"), item[1])); continue; }
      flushList();
      if (line.startsWith("> ")) target.append(appendRichInline(el("blockquote"), line.slice(2)));
      else target.append(appendRichInline(el("p"), line));
    }
    flushList(); if (code) target.append(code);
  }

  function renderJson(target, value) { target.textContent = JSON.stringify(value ?? {}, null, 2); }
  function toast(message, status = "ready") {
    const region = $("#toast-region") || document.body;
    const item = el("div", { class: `toast toast-${normalizeStatus(status)}`, role: "status", text: message });
    region.append(item); setTimeout(() => item.remove(), 3600);
  }
  function initTabs(root = document) {
    all("[data-tab-target]", root).forEach((button) => button.addEventListener("click", () => {
      const group = button.closest("[data-tabs]") || root;
      all("[data-tab-target]", group).forEach((item) => item.classList.toggle("active", item === button));
      all("[data-tab-panel]", group).forEach((panel) => { panel.hidden = panel.dataset.tabPanel !== button.dataset.tabTarget; });
    }));
  }

  window.XinzhiUI = { $, all, el, api, badge, initShell, initTabs, renderJson, renderLatex, renderMarkdown, statusLabels, toast, setTheme, applyTheme };
})();
