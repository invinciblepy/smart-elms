const API = {
  token() {
    return localStorage.getItem("elms_token");
  },
  user() {
    try {
      return JSON.parse(localStorage.getItem("elms_user") || "null");
    } catch {
      return null;
    }
  },
  setSession(token, user) {
    localStorage.setItem("elms_token", token);
    localStorage.setItem("elms_user", JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem("elms_token");
    localStorage.removeItem("elms_user");
  },
  async request(path, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
    }
    if (this.token()) headers.Authorization = `Bearer ${this.token()}`;
    const res = await fetch(path, { ...options, headers });
    const text = await res.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { error: text || "Unexpected response" };
    }
    if (res.status === 401) {
      this.clear();
      if (!location.pathname.startsWith("/register") && location.pathname !== "/") {
        location.href = "/";
      }
    }
    if (!res.ok) {
      const err = new Error(data.error || `Request failed (${res.status})`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  },
  async download(path, filename) {
    const headers = {};
    if (this.token()) headers.Authorization = `Bearer ${this.token()}`;
    const res = await fetch(path, { headers });
    if (!res.ok) throw new Error("Download failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "download";
    a.click();
    URL.revokeObjectURL(url);
  },
  get(path) {
    return this.request(path);
  },
  post(path, body) {
    return this.request(path, { method: "POST", body: JSON.stringify(body) });
  },
  put(path, body) {
    return this.request(path, { method: "PUT", body: JSON.stringify(body) });
  },
  del(path) {
    return this.request(path, { method: "DELETE" });
  },
};

function qs(name) {
  return new URLSearchParams(location.search).get(name);
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
}

function progressClass(p) {
  if (p >= 80) return "blue";
  if (p >= 65) return "green";
  if (p >= 50) return "orange";
  return "red";
}

function statusClass(label) {
  if (label === "Excellent") return "status-good";
  if (label === "On track") return "status-on";
  if (label === "Needs attention") return "status-warn";
  return "status-bad";
}

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function showError(el, msg) {
  if (!el) return;
  el.hidden = !msg;
  el.textContent = msg || "";
}
