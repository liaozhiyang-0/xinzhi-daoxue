const { $, api, setTheme } = XinzhiUI;

let mode = new URLSearchParams(location.search).get("mode") === "register" ? "register" : "login";

function nextPath() {
  const value = new URLSearchParams(location.search).get("next");
  return value && value.startsWith("/") ? value : "/student";
}

function updateMode() {
  const registering = mode === "register";
  $("#auth-title").textContent = registering ? "注册账号" : "登录账号";
  $("#auth-description").textContent = registering ? "注册后即可保存你的学习记录。" : "使用登录名和密码继续学习。";
  $("#auth-submit").textContent = registering ? "注册并开始" : "登录";
  $("[data-register-only]").hidden = !registering;
  $("[data-auth-mode=login]").classList.toggle("active", !registering);
  $("[data-auth-mode=register]").classList.toggle("active", registering);
  $("input[name=password]").minLength = registering ? 12 : 1;
}

window.addEventListener("DOMContentLoaded", () => {
  setTheme(localStorage.getItem("xinzhi_theme") || "system");
  updateMode();
  $("[data-auth-mode=login]").addEventListener("click", () => { mode = "login"; updateMode(); });
  $("[data-auth-mode=register]").addEventListener("click", () => { mode = "register"; updateMode(); });
  $("#guest-entry").addEventListener("click", async () => {
    $("#login-error").textContent = "正在进入游客模式…";
    try { await api("/api/v1/auth/guest", { method: "POST" }); window.location.assign(nextPath()); }
    catch (error) { $("#login-error").textContent = error.message; }
  });
  $("#login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form).entries());
    $("#login-error").textContent = mode === "register" ? "正在创建账号…" : "正在登录…";
    try {
      const endpoint = mode === "register" ? "/api/v1/auth/register" : "/api/v1/auth/login";
      await api(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const account = await api("/api/v1/auth/me");
      window.location.assign(account.role === "admin" && nextPath() === "/student" ? "/admin" : nextPath());
    } catch (error) { $("#login-error").textContent = error.message; }
  });
});
