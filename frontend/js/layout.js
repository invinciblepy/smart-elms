const STUDENT_NAV = [
  ["dashboard", "Dashboard", "/student/dashboard", "Home"],
  ["courses", "My Courses", "/student/courses", "Courses"],
  ["assignments", "Assignments", "/student/assignments", "Tasks"],
  ["quizzes", "Quizzes", "/student/quizzes", "Quiz"],
  ["grades", "Grades", "/student/grades", "Grades"],
  ["progress", "Progress", "/student/progress", "Progress"],
  ["support", "Support", "/student/support", "Help"],
];

const INSTRUCTOR_NAV = [
  ["dashboard", "Dashboard", "/instructor/dashboard", "Home"],
  ["classes", "My Classes", "/instructor/classes", "Classes"],
  ["milestones", "Milestones", "/instructor/milestones", "Goals"],
  ["alerts", "Alerts", "/instructor/alerts", "Alerts"],
  ["reports", "Reports", "/instructor/reports", "Reports"],
  ["students", "Students", "/instructor/students", "Students"],
];

function requireRole(role) {
  const user = API.user();
  if (!API.token() || !user) {
    location.href = "/";
    return null;
  }
  if (role && user.role !== role) {
    location.href = user.role === "instructor" ? "/instructor/dashboard" : "/student/dashboard";
    return null;
  }
  return user;
}

function initials(name) {
  return (name || "?")
    .split(" ")
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}

function renderLayout() {
  const role = document.body.dataset.role;
  const page = document.body.dataset.page;
  const user = requireRole(role);
  if (!user) return null;

  const nav = role === "instructor" ? INSTRUCTOR_NAV : STUDENT_NAV;
  const sidebar = document.getElementById("sidebar");
  if (!document.querySelector(".skip-link")) {
    const skip = document.createElement("a");
    skip.href = "#content";
    skip.className = "skip-link";
    skip.textContent = "Skip to content";
    document.body.prepend(skip);
  }
  const main = document.querySelector("main.content");
  if (main && !main.id) main.id = "content";
  if (sidebar) {
    sidebar.innerHTML = `
      <div class="brand">Smart ELMS</div>
      <nav class="nav" aria-label="Primary">
        ${nav
          .map(
            ([id, label, href, short]) =>
              `<a href="${href}" class="${page === id ? "active" : ""}"${page === id ? ' aria-current="page"' : ""}><span class="nav-label">${label}</span><span class="nav-short">${short || label}</span></a>`
          )
          .join("")}
      </nav>
      <div class="sidebar-user">
        <div class="avatar ${role === "instructor" ? "green" : ""}">${escapeHtml(initials(user.full_name))}</div>
        <div>
          <strong>${escapeHtml(user.full_name)}</strong>
          <span>${role === "instructor" ? "Instructor" : "Student"}</span>
        </div>
      </div>
      <a class="logout-link" href="#" id="logoutLink">Sign out</a>
    `;
    const out = document.getElementById("logoutLink");
    if (out) {
      out.addEventListener("click", async (e) => {
        e.preventDefault();
        await signOut();
      });
    }
  }
  const topbar = document.querySelector(".topbar");
  if (topbar && !document.getElementById("topLogout")) {
    const btn = document.createElement("button");
    btn.id = "topLogout";
    btn.className = "btn btn-ghost top-logout";
    btn.type = "button";
    btn.textContent = "Sign out";
    btn.addEventListener("click", signOut);
    topbar.appendChild(btn);
  }
  return user;
}

async function signOut() {
  try {
    await API.post("/api/auth/logout", {});
  } catch {
    /* still leave */
  }
  API.clear();
  location.href = "/";
}
