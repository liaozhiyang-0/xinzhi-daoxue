import { useEffect, useState } from "react";
import { useAuth } from "./AuthContext.js";

const groups = [
  { label: "学习", items: [{ href: "/workspace", label: "智能任务工作台", short: "学" }] },
  { label: "教学", items: [{ href: "/teacher", label: "教师工作台", short: "教" }] },
  { label: "管理", items: [{ href: "/admin", label: "管理总览", short: "管" }] },
  { label: "调试", items: [
    { href: "/system", label: "系统状态", short: "系" },
    { href: "/debug/agents", label: "Agent 管理", short: "A" },
    { href: "/debug/execution", label: "执行追踪", short: "追" },
    { href: "/debug/rag", label: "RAG 调试", short: "R" },
  ] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { identity, signOut } = useAuth();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("xinzhi_sidebar_collapsed") === "true");
  const [theme, setTheme] = useState(() => localStorage.getItem("xinzhi_theme") || "system");

  useEffect(() => {
    document.body.classList.toggle("sidebar-collapsed", collapsed);
    localStorage.setItem("xinzhi_sidebar_collapsed", String(collapsed));
  }, [collapsed]);

  useEffect(() => {
    const resolved = theme === "system"
      ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
      : theme;
    document.documentElement.dataset.theme = resolved;
    document.documentElement.dataset.themePreference = theme;
    localStorage.setItem("xinzhi_theme", theme);
  }, [theme]);

  return (
    <>
      <aside className="app-sidebar" aria-label="主导航">
        <div className="sidebar-inner">
          <a className="brand-lockup" href="/" aria-label="返回芯智导学首页">
            <span className="brand-mark">芯</span>
            <span className="brand-copy"><strong>芯智导学</strong><small>电子信息课程群智能学习平台</small></span>
          </a>
          <nav className="sidebar-nav">
            {groups.map((group) => {
              const visible = group.label === "管理" && identity?.role !== "admin"
                ? false
                : group.label === "教学" && !["teacher", "admin"].includes(identity?.role || "")
                  ? false
                  : group.label === "调试" && !["teacher", "researcher", "operator", "admin"].includes(identity?.role || "")
                    ? false
                    : true;
              if (!visible) return null;
              return <div className="nav-group" key={group.label}>
                <p className="nav-group-label">{group.label}</p>
                {group.items.map((item) => <a className={`nav-link${location.pathname === item.href ? " active" : ""}`} href={item.href} key={item.href} aria-current={location.pathname === item.href ? "page" : undefined}>
                  <span className="nav-icon">{item.short}</span><span className="nav-label">{item.label}</span>
                </a>)}
              </div>;
            })}
          </nav>
          <div className="sidebar-footer">
            <div className="environment-row"><span className="environment-copy">Product</span><span className="status-dot ready" title="前端工作台已加载" /></div>
            <div className="theme-switcher" role="group" aria-label="主题">
              {([["light", "浅色"], ["dark", "深色"], ["system", "跟随系统"]] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={theme === value} onClick={() => setTheme(value)}>{label}</button>)}
            </div>
            <button className="sidebar-collapse" type="button" onClick={() => setCollapsed((value) => !value)}>{collapsed ? "展开侧栏" : "收起侧栏"}</button>
          </div>
        </div>
      </aside>
      <header className="app-topbar">
        <button className="mobile-menu-button" type="button" onClick={() => document.body.classList.toggle("drawer-open")}>菜单</button>
        <div className="topbar-title"><strong>智能任务工作台</strong></div>
        <div className="topbar-actions">
          {identity && <div className="identity-control" aria-label="当前身份"><span className="identity-label">{identity.displayName}{identity.guest ? " · 游客" : ` · ${identity.role}`}</span><button className="identity-link" type="button" onClick={() => void signOut()}>{identity.guest ? "登录保存" : "退出登录"}</button></div>}
        </div>
      </header>
      {children}
    </>
  );
}
