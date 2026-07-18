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
      { id: "student", href: "/student", label: "智能问答与解题", short: "学" },
    ] },
    { group: "开发与调试", items: [
      { id: "rag", href: "/debug/rag", label: "RAG 调试", short: "R" },
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

  function shellNav(page) {
    const wrapper = el("div", { class: "sidebar-inner" });
    wrapper.append(el("a", { class: "brand-lockup", href: "/", "aria-label": "返回芯智导学首页" }, [
      el("span", { class: "brand-mark", text: "芯" }),
      el("span", { class: "brand-copy" }, [el("strong", { text: "芯智导学" }), el("small", { text: "电子信息课程群智能学习平台" })]),
    ]));
    const menu = el("nav", { class: "sidebar-nav", "aria-label": "主导航" });
    nav.forEach((section) => {
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
    footer.append(el("div", { class: "environment-row" }, [
      el("span", { class: "environment-copy", text: "Development" }),
      el("span", { id: "global-health", class: "status-dot", title: "正在检查本地 API" }),
    ]));
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

  function initShell({ page, title, description = "", context = "" }) {
    const sidebar = $("#app-sidebar");
    const topbar = $("#app-topbar");
    if (sidebar) sidebar.replaceChildren(shellNav(page));
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

  function renderMarkdown(target, source) {
    target.replaceChildren();
    const lines = String(source || "").replace(/\r/g, "").split("\n");
    let code = null; let list = null;
    const flushList = () => { if (list) { target.append(list); list = null; } };
    lines.forEach((line) => {
      if (line.trim().startsWith("```")) { flushList(); if (code) { target.append(code); code = null; } else code = el("pre", { class: "code-block" }, el("code")); return; }
      if (code) { code.firstChild.append(document.createTextNode(`${line}\n`)); return; }
      if (!line.trim()) { flushList(); return; }
      const heading = line.match(/^(#{1,4})\s+(.+)$/);
      if (heading) { flushList(); target.append(el(`h${Math.min(heading[1].length + 1, 5)}`, { text: heading[2] })); return; }
      const item = line.match(/^[-*]\s+(.+)$/);
      if (item) { if (!list) list = el("ul"); list.append(el("li", { text: item[1] })); return; }
      flushList();
      if (line.startsWith("> ")) target.append(el("blockquote", { text: line.slice(2) }));
      else target.append(el("p", { text: line }));
    });
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

  window.XinzhiUI = { $, all, el, api, badge, initShell, initTabs, renderJson, renderMarkdown, statusLabels, toast, setTheme, applyTheme };
})();
