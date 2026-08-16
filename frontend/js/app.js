document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  const role = document.body.dataset.role;
  if (role) renderLayout();

  const loaders = {
    login: initLogin,
    register: initRegister,
    dashboard: role === "instructor" ? loadInstructorDashboard : loadStudentDashboard,
    courses: loadStudentCourses,
    course: loadStudentCourse,
    module: loadModule,
    assignments: loadStudentAssignments,
    submit: loadSubmit,
    quizzes: loadStudentQuizzes,
    quiz: loadTakeQuiz,
    grades: loadGrades,
    progress: loadStudentProgress,
    support: () => {},
    forgot: initForgot,
    confirm: loadConfirm,
    classes: loadInstructorClasses,
    class: loadInstructorClass,
    assignment: loadInstructorAssignment,
    students: loadInstructorStudents,
    student: loadInstructorStudent,
    milestones: loadMilestones,
    alerts: loadAlerts,
    reports: loadReports,
  };
  const fn = loaders[page];
  if (fn) fn();
});

function initLogin() {
  if (API.user() && API.token()) {
    location.href = API.user().role === "instructor" ? "/instructor/dashboard" : "/student/dashboard";
    return;
  }
  const form = document.getElementById("loginForm");
  const err = document.getElementById("formError");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showError(err, "");
    const email = form.email.value.trim();
    const password = form.password.value;
    if (!email.includes("@")) return showError(err, "Enter a valid email address");
    if (password.length < 8) return showError(err, "Password must be at least 8 characters");
    try {
      const data = await API.post("/api/auth/login", {
        email,
        password,
        remember: form.remember && form.remember.checked,
      });
      API.setSession(data.access_token, data.user);
      location.href = data.user.role === "instructor" ? "/instructor/dashboard" : "/student/dashboard";
    } catch (ex) {
      showError(err, ex.message);
    }
  });
}

function initRegister() {
  const form = document.getElementById("registerForm");
  const err = document.getElementById("formError");
  const roleInput = document.getElementById("roleInput");
  document.querySelectorAll(".role-toggle button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".role-toggle button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      roleInput.value = btn.dataset.role;
    });
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showError(err, "");
    const full_name = form.full_name.value.trim();
    const email = form.email.value.trim();
    const password = form.password.value;
    if (full_name.length < 2) return showError(err, "Please enter your full name");
    if (!email.includes("@")) return showError(err, "Enter a valid email address");
    if (password.length < 8) return showError(err, "Password must be at least 8 characters");
    try {
      const data = await API.post("/api/auth/register", {
        full_name,
        email,
        password,
        role: roleInput.value,
      });
      API.setSession(data.access_token, data.user);
      location.href = data.user.role === "instructor" ? "/instructor/dashboard" : "/student/dashboard";
    } catch (ex) {
      showError(err, ex.message);
    }
  });
}

async function loadStudentDashboard() {
  const data = await API.get("/api/analytics/dashboard/student");
  document.getElementById("statCourses").textContent = data.stats.courses_enrolled;
  document.getElementById("statProgress").textContent = data.stats.avg_progress + "%";
  document.getElementById("statDue").textContent = data.stats.assignments_due;
  document.getElementById("statActive").textContent = data.stats.days_active;
  const banner = document.getElementById("aiBanner");
  if (data.ai_banner) {
    banner.hidden = false;
    banner.innerHTML = `<div>💡</div><div><strong>${escapeHtml(data.ai_banner.title)}</strong><p>${escapeHtml(data.ai_banner.message)}</p><p><a href="/student/support">View academic support</a></p></div>`;
  }
  const dueList = document.getElementById("dueList");
  if (dueList) {
    dueList.innerHTML =
      (data.due_assignments || [])
        .map(
          (a) => `<a class="row-card" href="/student/submit?id=${a.assignment_id}">
            <div class="grow"><h4>${escapeHtml(a.title)}</h4><div class="meta">${escapeHtml(a.course_title)} · due in ${a.days} day${a.days === 1 ? "" : "s"}</div></div>
            <span class="status-warn">Due soon</span>
          </a>`
        )
        .join("") || `<p class="empty">No assignments due in the next 7 days.</p>`;
  }
  const grid = document.getElementById("courseGrid");
  grid.innerHTML = (data.courses || [])
    .map((c) => {
      const cls = progressClass(c.progress_percent || 0);
      return `<article class="card">
        <h3><a href="/student/course?id=${c.course_id}">${escapeHtml(c.title)}</a></h3>
        <div class="${statusClass(c.status_label)}">${escapeHtml(c.status_label)}</div>
        <div class="progress ${cls}" style="margin-top:12px"><span style="width:${c.progress_percent || 0}%"></span></div>
        <div class="meta" style="margin-top:8px">${c.progress_percent || 0}%</div>
      </article>`;
    })
    .join("") || `<p class="empty">You are not enrolled in any courses yet.</p>`;
  const search = document.querySelector(".search");
  if (search) {
    search.addEventListener("input", () => {
      const q = search.value.trim().toLowerCase();
      grid.querySelectorAll("article.card").forEach((card) => {
        const title = (card.querySelector("h3") || {}).textContent || "";
        card.style.display = title.toLowerCase().includes(q) ? "" : "none";
      });
    });
  }
}

function initForgot() {
  const form = document.getElementById("forgotForm");
  const err = document.getElementById("formError");
  const ok = document.getElementById("formOk");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showError(err, "");
    ok.hidden = true;
    try {
      const data = await API.post("/api/auth/forgot-password", { email: form.email.value.trim() });
      ok.hidden = false;
      ok.textContent = data.message;
    } catch (ex) {
      showError(err, ex.message);
    }
  });
}

async function loadConfirm() {
  const id = qs("id");
  const el = document.getElementById("confirmMeta");
  if (!id) {
    el.textContent = "No assignment was specified.";
    return;
  }
  try {
    const data = await API.get(`/api/assignments/${id}`);
    const a = data.assignment;
    const sub = a.submission;
    el.textContent = sub
      ? `${a.title} was submitted on ${fmtDate(sub.submitted_at)}${sub.file_path ? " with a file" : ""}.`
      : `${a.title} confirmation is waiting.`;
    document.getElementById("backLink").href = `/student/submit?id=${id}`;
  } catch (ex) {
    el.textContent = ex.message;
  }
}

async function loadStudentCourses() {
  const data = await API.get("/api/courses");
  const enrolled = data.courses.filter((c) => c.enrolled);
  const available = data.courses.filter((c) => !c.enrolled);
  document.getElementById("enrolledGrid").innerHTML =
    enrolled
      .map(
        (c) => `<article class="card">
      <h3><a href="/student/course?id=${c.course_id}">${escapeHtml(c.title)}</a></h3>
      <p class="meta">${escapeHtml(c.instructor || "")} · ${c.module_count} modules · ${c.progress_percent}%</p>
      <p class="small muted">${escapeHtml(c.description || "")}</p>
    </article>`
      )
      .join("") || `<p class="empty">No enrolled courses.</p>`;
  document.getElementById("availableGrid").innerHTML =
    available
      .map(
        (c) => `<article class="card">
      <h3>${escapeHtml(c.title)}</h3>
      <p class="meta">${escapeHtml(c.instructor || "")}</p>
      <p class="small muted">${escapeHtml(c.description || "")}</p>
      <button class="btn" data-enroll="${c.course_id}">Enrol</button>
    </article>`
      )
      .join("") || `<p class="empty">No other courses available.</p>`;
  document.getElementById("availableGrid").addEventListener("click", async (e) => {
    const id = e.target.dataset.enroll;
    if (!id) return;
    try {
      await API.post(`/api/courses/${id}/enroll`, {});
      location.reload();
    } catch (ex) {
      alert(ex.message);
    }
  });
  const search = document.getElementById("courseSearch");
  if (search) {
    search.addEventListener("input", () => {
      const q = search.value.trim().toLowerCase();
      document.querySelectorAll("#enrolledGrid article.card, #availableGrid article.card").forEach((card) => {
        const title = (card.querySelector("h3") || {}).textContent || "";
        card.style.display = title.toLowerCase().includes(q) ? "" : "none";
      });
    });
  }
}

async function loadStudentCourse() {
  const id = qs("id");
  if (!id) return;
  const [data, assigns] = await Promise.all([
    API.get(`/api/courses/${id}/modules`),
    API.get(`/api/courses/${id}/assignments`),
  ]);
  document.getElementById("crumb").textContent = `My Courses / ${data.course.title}`;
  document.getElementById("courseTitle").textContent = data.course.title;
  document.getElementById("courseMeta").textContent = `Instructor: ${data.course.instructor}  ·  ${data.modules.length} modules  ·  Progress ${data.progress_percent}%`;
  document.getElementById("courseBar").style.width = `${data.progress_percent}%`;
  document.getElementById("moduleList").innerHTML = data.modules
    .map((m, i) => {
      const done = m.status === "Completed";
      const n = String(i + 1).padStart(2, "0");
      return `<a class="row-card" href="/student/module?id=${m.module_id}">
        <div class="idx ${done ? "done" : ""}">${n}</div>
        <div class="grow"><h4>${escapeHtml(m.title)}</h4></div>
        <span class="${done ? "status-on" : "muted"}">${done ? "Completed" : m.status || "Not started"}</span>
      </a>`;
    })
    .join("");
  const assignBox = document.getElementById("assignmentList");
  if (assignBox) {
    assignBox.innerHTML =
      (assigns.assignments || [])
        .map((a) => {
          const sub = a.submission;
          const status = sub ? (sub.score != null ? `Scored ${sub.score}` : "Submitted") : "Open";
          return `<a class="row-card" href="/student/submit?id=${a.assignment_id}">
            <div class="grow"><h4>${escapeHtml(a.title)}</h4><div class="meta">Due ${fmtDate(a.due_date)}</div></div>
            <span class="${sub ? "status-on" : "muted"}">${status}</span>
          </a>`;
        })
        .join("") || `<p class="empty">No assignments for this course yet.</p>`;
  }
}

async function loadModule() {
  const id = qs("id");
  const data = await API.get(`/api/modules/${id}`);
  document.getElementById("crumb").innerHTML = `<a href="/student/course?id=${data.course.course_id}">${escapeHtml(data.course.title)}</a> / ${escapeHtml(data.module.title)}`;
  document.getElementById("moduleTitle").textContent = data.module.title;
  document.getElementById("moduleBody").textContent = data.module.content || "No notes have been published for this module yet.";
  document.getElementById("moduleStatus").textContent = `${data.module.status || "Not started"} · ${data.module.time_spent_minutes || 0} min recorded`;
  try {
    await API.post(`/api/modules/${id}/access`, { minutes: 1 });
  } catch {
    /* ignore */
  }
  const btn = document.getElementById("completeBtn");
  if (data.module.status === "Completed") {
    btn.textContent = "Completed";
    btn.disabled = true;
  }
  btn.addEventListener("click", async () => {
    await API.post(`/api/modules/${id}/complete`, {});
    location.href = `/student/course?id=${data.course.course_id}`;
  });
}

async function loadStudentAssignments() {
  const data = await API.get("/api/student/assignments");
  document.getElementById("assignmentList").innerHTML =
    data.assignments
      .map((a) => {
        const sub = a.submission;
        const status = sub ? (sub.score != null ? `Scored ${sub.score}/${a.max_score}` : "Submitted") : a.is_overdue ? "Overdue" : "Not submitted";
        const cls = sub ? "status-on" : a.is_overdue ? "status-bad" : "status-warn";
        return `<a class="row-card" href="/student/submit?id=${a.assignment_id}">
          <div class="grow">
            <h4>${escapeHtml(a.title)}</h4>
            <div class="meta">${escapeHtml(a.course_title)} · Due ${fmtDate(a.due_date)}</div>
          </div>
          <span class="${cls}">${status}</span>
        </a>`;
      })
      .join("") || `<p class="empty">No assignments yet.</p>`;
}

async function loadSubmit() {
  const id = qs("id");
  const data = await API.get(`/api/assignments/${id}`);
  const a = data.assignment;
  document.getElementById("crumb").textContent = `${a.course_title} / ${a.title}`;
  document.getElementById("assignTitle").textContent = `Submit ${a.title}`;
  document.getElementById("assignDesc").textContent = a.description || "Complete the required tasks for this assignment and submit your work before the deadline.";
  document.getElementById("assignMeta").textContent = `Due: ${fmtDate(a.due_date)}  ·  Max score: ${a.max_score}`;
  if (a.submission) {
    document.getElementById("existing").hidden = false;
    document.getElementById("existing").textContent = `Already submitted on ${fmtDate(a.submission.submitted_at)}${a.submission.score != null ? ` · Score ${a.submission.score}` : ""}. You can resubmit below.`;
  }
  const zone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  zone.addEventListener("click", () => fileInput.click());
  zone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("drag");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag");
    fileInput.files = e.dataTransfer.files;
    zone.querySelector("span").textContent = fileInput.files[0]?.name || "File selected";
  });
  fileInput.addEventListener("change", () => {
    zone.querySelector("span").textContent = fileInput.files[0]?.name || "Drag and drop your file here, or click to select";
  });
  const form = document.getElementById("submitForm");
  const err = document.getElementById("formError");
  const ok = document.getElementById("formOk");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showError(err, "");
    ok.hidden = true;
    const file = fileInput.files[0];
    if (file) {
      if (!/\.(pdf|docx|txt)$/i.test(file.name)) {
        return showError(err, "Only PDF, DOCX or TXT files are allowed");
      }
      if (file.size > 10 * 1024 * 1024) {
        return showError(err, "File exceeds the 10 MB limit");
      }
    }
    const fd = new FormData();
    fd.append("comment", form.comment.value);
    if (file) fd.append("file", file);
    try {
      await API.request(`/api/assignments/${id}/submit`, { method: "POST", body: fd });
      location.href = `/student/confirm?id=${id}`;
    } catch (ex) {
      showError(err, ex.message);
    }
  });
}

async function loadStudentQuizzes() {
  const data = await API.get("/api/student/quizzes");
  document.getElementById("quizList").innerHTML =
    data.quizzes
      .map((q) => {
        const status = q.attempt ? `Score ${q.attempt.score}%` : "Not attempted";
        return `<a class="row-card" href="/student/quiz?id=${q.quiz_id}">
          <div class="grow">
            <h4>${escapeHtml(q.title)}</h4>
            <div class="meta">${escapeHtml(q.course_title)} · ${q.question_count} questions</div>
          </div>
          <span class="${q.attempt ? "status-on" : "muted"}">${status}</span>
        </a>`;
      })
      .join("") || `<p class="empty">No quizzes yet.</p>`;
}

async function loadTakeQuiz() {
  const id = qs("id");
  const data = await API.get(`/api/quizzes/${id}`);
  const q = data.quiz;
  document.getElementById("quizTitle").textContent = q.title;
  document.getElementById("quizMeta").textContent = `${q.course_title} · ${q.question_count} questions`;
  if (q.attempt) {
    document.getElementById("quizResult").hidden = false;
    document.getElementById("quizResult").textContent = `Previous best / latest score: ${q.attempt.score}%. You can try again.`;
  }
  const box = document.getElementById("questions");
  box.innerHTML = q.questions
    .map(
      (item, i) => `<div class="quiz-q card">
      <strong>Q${i + 1}. ${escapeHtml(item.prompt)}</strong>
      ${["A", "B", "C", "D"]
        .map(
          (k) => `<label class="opt"><input type="radio" name="q${item.question_id}" value="${k}"> ${k}. ${escapeHtml(item["option_" + k.toLowerCase()])}</label>`
        )
        .join("")}
    </div>`
    )
    .join("");
  document.getElementById("quizForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const answers = {};
    q.questions.forEach((item) => {
      const picked = document.querySelector(`input[name="q${item.question_id}"]:checked`);
      if (picked) answers[item.question_id] = picked.value;
    });
    if (Object.keys(answers).length < q.questions.length) {
      alert("Please answer every question before submitting.");
      return;
    }
    try {
      const res = await API.post(`/api/quizzes/${id}/attempt`, { answers });
      document.getElementById("quizResult").hidden = false;
      document.getElementById("quizResult").textContent = `You scored ${res.attempt.score}% (${res.correct}/${res.total} correct).`;
    } catch (ex) {
      alert(ex.message);
    }
  });
}

async function loadGrades() {
  const data = await API.get("/api/student/grades");
  const body = document.getElementById("gradeBody");
  const rows = [
    ...data.assignments.map(
      (s) => `<tr><td>${escapeHtml(s.assignment_title)}</td><td>Assignment</td><td>${s.score != null ? s.score : "Pending"}</td><td>${fmtDate(s.submitted_at)}</td></tr>`
    ),
    ...data.quizzes.map(
      (s) => `<tr><td>${escapeHtml(s.quiz_title)}</td><td>Quiz</td><td>${s.score}</td><td>${fmtDate(s.attempted_at)}</td></tr>`
    ),
  ];
  body.innerHTML = rows.join("") || `<tr><td colspan="4" class="empty">No graded work yet.</td></tr>`;
}

async function loadStudentProgress() {
  const dash = await API.get("/api/analytics/dashboard/student");
  document.getElementById("avgProgress").textContent = dash.stats.avg_progress + "%";
  document.getElementById("predBox").textContent = dash.prediction
    ? `AI risk level: ${dash.prediction.risk_level} (${Math.round(dash.prediction.probability * 100)}% probability)`
    : "No prediction stored yet.";
  document.getElementById("progressList").innerHTML = dash.courses
    .map((c) => {
      const cls = progressClass(c.progress_percent || 0);
      return `<div class="card"><h3>${escapeHtml(c.title)}</h3>
        <div class="${statusClass(c.status_label)}">${escapeHtml(c.status_label)}</div>
        <div class="progress ${cls}" style="margin-top:12px"><span style="width:${c.progress_percent}%"></span></div>
        <div class="meta">${c.progress_percent}%</div></div>`;
    })
    .join("");
}

async function loadInstructorDashboard() {
  const data = await API.get("/api/analytics/dashboard/instructor");
  document.getElementById("statStudents").textContent = data.stats.total_students;
  document.getElementById("statEngage").textContent = data.stats.avg_engagement + "%";
  document.getElementById("statRisk").textContent = data.stats.at_risk_students;
  document.getElementById("statDue").textContent = data.stats.assignments_due;
  const alertBox = document.getElementById("deadlineAlerts");
  if (alertBox) {
    alertBox.innerHTML =
      (data.deadline_alerts || [])
        .map((a) => `<div class="card"><strong>${escapeHtml(a.title)}</strong><p class="muted">${escapeHtml(a.detail)}</p></div>`)
        .join("") || `<p class="empty">No deadline alerts.</p>`;
  }
  const perfBox = document.getElementById("performanceAlerts");
  if (perfBox) {
    perfBox.innerHTML =
      (data.performance_alerts || [])
        .map(
          (a) => `<a class="row-card" href="/instructor/student?id=${a.student_id}">
            <div class="grow"><h4>${escapeHtml(a.title)}</h4><div class="meta">${escapeHtml(a.detail)}</div></div>
            <span class="badge high">Red</span>
          </a>`
        )
        .join("") || `<p class="empty">No performance alerts.</p>`;
  }
  await fillChartGrid("dashCharts", false);
  document.getElementById("attentionList").innerHTML =
    data.students_needing_attention
      .map((s) => {
        const level = (s.risk_level || "Low").toLowerCase();
        return `<div class="row-card">
          <div class="avatar ${level === "high" ? "" : level === "medium" ? "purple" : "green"}">${escapeHtml(initials(s.full_name))}</div>
          <div class="grow">
            <h4>${escapeHtml(s.full_name)}</h4>
            <div class="meta">${escapeHtml(s.course)}</div>
          </div>
          <div class="muted small">Last active: ${s.days_since_login} day${s.days_since_login === 1 ? "" : "s"} ago</div>
          <span class="badge ${level}">${escapeHtml(s.risk_level)}</span>
          <a href="/instructor/student?id=${s.student_id}">View profile →</a>
        </div>`;
      })
      .join("") || `<p class="empty">No students need attention right now.</p>`;
}

async function loadInstructorClasses() {
  const data = await API.get("/api/courses");
  document.getElementById("classGrid").innerHTML =
    data.courses
      .map(
        (c) => `<article class="card">
      <h3><a href="/instructor/class?id=${c.course_id}">${escapeHtml(c.title)}</a></h3>
      <p class="meta">${c.enrolled_count} students · ${c.module_count} modules · ${c.assignment_count} assignments</p>
      <p class="small muted">${escapeHtml(c.description || "")}</p>
    </article>`
      )
      .join("") || `<p class="empty">No classes yet.</p>`;
  document.getElementById("createCourse").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    try {
      await API.post("/api/courses", { title: form.title.value, description: form.description.value });
      location.reload();
    } catch (ex) {
      alert(ex.message);
    }
  });
}

async function loadInstructorClass() {
  const id = qs("id");
  const [courseWrap, modules, assignments, quizzes, roster] = await Promise.all([
    API.get(`/api/courses/${id}`),
    API.get(`/api/courses/${id}/modules`),
    API.get(`/api/courses/${id}/assignments`),
    API.get(`/api/courses/${id}/quizzes`),
    API.get(`/api/instructor/classes/${id}/roster`),
  ]);
  document.getElementById("classTitle").textContent = courseWrap.course.title;
  document.getElementById("classMeta").textContent = courseWrap.course.description || "";
  document.getElementById("moduleList").innerHTML = modules.modules
    .map(
      (m) => `<div class="row-card">
        <div class="grow"><h4>${escapeHtml(m.title)}</h4></div>
        <button class="btn btn-ghost" type="button" data-del-module="${m.module_id}">Delete</button>
      </div>`
    )
    .join("");
  document.getElementById("moduleList").addEventListener("click", async (e) => {
    const mid = e.target.dataset.delModule;
    if (!mid) return;
    if (!confirm("Delete this module?")) return;
    try {
      await API.del(`/api/modules/${mid}`);
      location.reload();
    } catch (ex) {
      alert(ex.message);
    }
  });
  document.getElementById("assignmentList").innerHTML = assignments.assignments
    .map(
      (a) => `<a class="row-card" href="/instructor/assignment?id=${a.assignment_id}">
        <div class="grow"><h4>${escapeHtml(a.title)}</h4><div class="meta">Due ${fmtDate(a.due_date)} · ${a.submission_count} submissions</div></div>
        <span>Grade →</span>
      </a>`
    )
    .join("");
  document.getElementById("quizList").innerHTML = quizzes.quizzes
    .map((q) => `<div class="row-card"><div class="grow"><h4>${escapeHtml(q.title)}</h4><div class="meta">${q.attempt_count} attempts</div></div></div>`)
    .join("");
  const qbox = document.getElementById("quizQuestions");
  const addQ = document.getElementById("addQuestionBtn");
  function addQuestionRow() {
    const n = qbox.children.length + 1;
    const wrap = document.createElement("div");
    wrap.className = "quiz-q card";
    wrap.innerHTML = `<strong>Question ${n}</strong>
      <div class="field"><label for="q${n}prompt">Prompt</label><input id="q${n}prompt" name="prompt" required></div>
      <div class="grid-2">
        <div class="field"><label for="q${n}a">A</label><input id="q${n}a" name="option_a" required></div>
        <div class="field"><label for="q${n}b">B</label><input id="q${n}b" name="option_b" required></div>
        <div class="field"><label for="q${n}c">C</label><input id="q${n}c" name="option_c" required></div>
        <div class="field"><label for="q${n}d">D</label><input id="q${n}d" name="option_d" required></div>
      </div>
      <div class="field"><label for="q${n}ok">Correct</label>
        <select id="q${n}ok" name="correct_option"><option>A</option><option>B</option><option>C</option><option>D</option></select>
      </div>`;
    qbox.appendChild(wrap);
  }
  if (addQ && qbox && qbox.children.length === 0) addQuestionRow();
  if (addQ) addQ.addEventListener("click", addQuestionRow);
  document.getElementById("addQuiz").addEventListener("submit", async (e) => {
    e.preventDefault();
    const questions = [...qbox.querySelectorAll(".quiz-q")].map((row) => ({
      prompt: row.querySelector("[name=prompt]").value,
      option_a: row.querySelector("[name=option_a]").value,
      option_b: row.querySelector("[name=option_b]").value,
      option_c: row.querySelector("[name=option_c]").value,
      option_d: row.querySelector("[name=option_d]").value,
      correct_option: row.querySelector("[name=correct_option]").value,
    }));
    try {
      await API.post(`/api/courses/${id}/quizzes`, { title: e.target.title.value, questions });
      location.reload();
    } catch (ex) {
      alert(ex.message);
    }
  });
  document.getElementById("roster").innerHTML = roster.students
    .map(
      (s) => `<tr>
      <td><a href="/instructor/student?id=${s.student_id}">${escapeHtml(s.full_name)}</a></td>
      <td>${s.progress_percent}%</td>
      <td><span class="badge ${(s.risk_level || "Low").toLowerCase()}">${escapeHtml(s.risk_level)}</span></td>
      <td>${s.days_since_login}d</td>
    </tr>`
    )
    .join("");

  document.getElementById("addModule").addEventListener("submit", async (e) => {
    e.preventDefault();
    await API.post(`/api/courses/${id}/modules`, { title: e.target.title.value, content: e.target.content.value });
    location.reload();
  });
  document.getElementById("addAssignment").addEventListener("submit", async (e) => {
    e.preventDefault();
    await API.post(`/api/courses/${id}/assignments`, {
      title: e.target.title.value,
      description: e.target.description.value,
      due_date: e.target.due_date.value ? new Date(e.target.due_date.value).toISOString() : null,
    });
    location.reload();
  });
}

async function loadInstructorStudents() {
  const data = await API.get("/api/instructor/students");
  const list = document.getElementById("studentList");
  list.innerHTML = data.students
    .map(
      (s) => `<a class="row-card" href="/instructor/student?id=${s.student_id}">
        <div class="avatar">${escapeHtml(initials(s.full_name))}</div>
        <div class="grow"><h4>${escapeHtml(s.full_name)}</h4><div class="meta">${escapeHtml((s.courses || []).join(", "))}</div></div>
        <span class="badge ${(s.risk_level || "Low").toLowerCase()}">${escapeHtml(s.risk_level)}</span>
      </a>`
    )
    .join("");
  const search = document.getElementById("studentSearch");
  if (search) {
    search.addEventListener("input", () => {
      const q = search.value.trim().toLowerCase();
      list.querySelectorAll("a.row-card").forEach((card) => {
        const name = (card.querySelector("h4") || {}).textContent || "";
        card.style.display = name.toLowerCase().includes(q) ? "" : "none";
      });
    });
  }
}

async function loadInstructorStudent() {
  const id = qs("id");
  const data = await API.get(`/api/analytics/students/${id}`);
  document.getElementById("studentName").textContent = data.student.full_name;
  document.getElementById("studentMeta").textContent = `${data.student.email} · Last login ${data.days_since_last_login} day(s) ago`;
  const pred = data.prediction;
  document.getElementById("risk").innerHTML = pred
    ? `<span class="badge ${(pred.risk_level || "Low").toLowerCase()}">${pred.risk_level}</span> · ${(pred.probability * 100).toFixed(0)}% probability`
    : "No prediction yet";
  document.getElementById("feat").innerHTML = Object.entries(data.features)
    .map(([k, v]) => `<div class="card"><div class="muted small">${k.replaceAll("_", " ")}</div><strong>${v}</strong></div>`)
    .join("");
  document.getElementById("courses").innerHTML = data.courses
    .map((c) => `<div class="card"><h3>${escapeHtml(c.title)}</h3><div class="progress ${progressClass(c.progress_percent)}"><span style="width:${c.progress_percent}%"></span></div><div class="meta">${c.progress_percent}% · ${c.status_label}</div></div>`)
    .join("");
  const subBody = document.getElementById("submissions");
  if (subBody) {
    subBody.innerHTML =
      (data.submissions || [])
        .map(
          (s) => `<tr><td>${escapeHtml(s.assignment_title)}</td><td>${s.score != null ? s.score : "Pending"}</td><td>${fmtDate(s.submitted_at)}</td></tr>`
        )
        .join("") || `<tr><td colspan="3" class="empty">No submissions yet.</td></tr>`;
  }
  const attBody = document.getElementById("attempts");
  if (attBody) {
    attBody.innerHTML =
      (data.quiz_attempts || [])
        .map(
          (s) => `<tr><td>${escapeHtml(s.quiz_title)}</td><td>${s.score}</td><td>${fmtDate(s.attempted_at)}</td></tr>`
        )
        .join("") || `<tr><td colspan="3" class="empty">No quiz attempts yet.</td></tr>`;
  }
  document.getElementById("refreshPred").addEventListener("click", async () => {
    await API.post(`/api/predict/refresh/${id}`, {});
    location.reload();
  });
}

function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function loadMilestones() {
  const data = await API.get("/api/milestones");
  const courses = await API.get("/api/courses");
  document.getElementById("courseSelect").innerHTML = courses.courses
    .map((c) => `<option value="${c.course_id}">${escapeHtml(c.title)}</option>`)
    .join("");
  document.getElementById("mileList").innerHTML = data.milestones
    .map(
      (m) => `<div class="card">
      <h3>${escapeHtml(m.title)}</h3>
      <p class="meta">${escapeHtml(m.course_title)} · ${m.completed}/${m.enrolled} students${m.due_date ? ` · Due ${fmtDate(m.due_date)}` : ""}</p>
      <p class="small muted">${escapeHtml(m.description || "")}</p>
      <div class="progress blue"><span style="width:${m.completion_rate}%"></span></div>
      <div class="meta">${m.completion_rate}% · ${escapeHtml(m.requirement_type || "")}</div>
      <div class="form-actions">
        <button class="btn btn-ghost" type="button" data-edit="${m.milestone_id}">Edit</button>
        <button class="btn btn-danger" type="button" data-del="${m.milestone_id}">Delete</button>
      </div>
    </div>`
    )
    .join("");
  async function fillRefSelect(courseId, type, selectEl, wrapEl, selected) {
    if (!selectEl || !wrapEl) return;
    if (type === "course_progress" || !type) {
      wrapEl.hidden = true;
      selectEl.innerHTML = "";
      return;
    }
    wrapEl.hidden = false;
    let items = [];
    if (type === "assignment_submit") {
      items = ((await API.get(`/api/courses/${courseId}/assignments`)).assignments || []).map((a) => [a.assignment_id, a.title]);
    } else if (type === "quiz_attempt") {
      items = ((await API.get(`/api/courses/${courseId}/quizzes`)).quizzes || []).map((q) => [q.quiz_id, q.title]);
    } else if (type === "module_access") {
      items = ((await API.get(`/api/courses/${courseId}/modules`)).modules || []).map((m) => [m.module_id, m.title]);
    }
    selectEl.innerHTML = `<option value="">Any item in this course</option>` + items.map(([rid, title]) => `<option value="${rid}"${String(rid) === String(selected || "") ? " selected" : ""}>${escapeHtml(title)}</option>`).join("");
  }
  const courseSelect = document.getElementById("courseSelect");
  const mileReq = document.getElementById("mileReq");
  const refreshAddRefs = () => fillRefSelect(courseSelect.value, mileReq.value, document.getElementById("mileRef"), document.getElementById("mileRefWrap"));
  if (courseSelect && mileReq) {
    courseSelect.addEventListener("change", refreshAddRefs);
    mileReq.addEventListener("change", refreshAddRefs);
    refreshAddRefs();
  }
  document.getElementById("addMile").addEventListener("submit", async (e) => {
    e.preventDefault();
    const refVal = e.target.requirement_ref_id ? e.target.requirement_ref_id.value : "";
    await API.post(`/api/courses/${e.target.course_id.value}/milestones`, {
      title: e.target.title.value,
      description: e.target.description.value,
      requirement_type: e.target.requirement_type.value,
      requirement_ref_id: refVal ? Number(refVal) : null,
      due_date: e.target.due_date.value ? new Date(e.target.due_date.value).toISOString() : null,
    });
    location.reload();
  });
  const editForm = document.getElementById("editMile");
  const cancelEdit = document.getElementById("cancelEdit");
  if (cancelEdit) {
    cancelEdit.addEventListener("click", () => {
      editForm.hidden = true;
    });
  }
  if (editForm) {
    editForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const mid = e.target.milestone_id.value;
      const refVal = e.target.requirement_ref_id ? e.target.requirement_ref_id.value : "";
      await API.put(`/api/milestones/${mid}`, {
        title: e.target.title.value,
        description: e.target.description.value,
        requirement_type: e.target.requirement_type.value,
        requirement_ref_id: refVal ? Number(refVal) : null,
        due_date: e.target.due_date.value ? new Date(e.target.due_date.value).toISOString() : null,
      });
      location.reload();
    });
  }
  document.getElementById("mileList").addEventListener("click", async (e) => {
    const del = e.target.dataset.del;
    const edit = e.target.dataset.edit;
    if (del) {
      if (!confirm("Delete this milestone?")) return;
      await API.del(`/api/milestones/${del}`);
      location.reload();
    }
    if (edit) {
      const row = data.milestones.find((m) => String(m.milestone_id) === String(edit));
      if (!row || !editForm) return;
      editForm.hidden = false;
      editForm.milestone_id.value = row.milestone_id;
      editForm.title.value = row.title || "";
      editForm.description.value = row.description || "";
      editForm.requirement_type.value = row.requirement_type || "course_progress";
      editForm.due_date.value = toLocalInput(row.due_date);
      editForm.dataset.courseId = row.course_id;
      await fillRefSelect(row.course_id, row.requirement_type, document.getElementById("editRef"), document.getElementById("editRefWrap"), row.requirement_ref_id);
      const editReq = document.getElementById("editReq");
      if (editReq && !editReq.dataset.bound) {
        editReq.dataset.bound = "1";
        editReq.addEventListener("change", () =>
          fillRefSelect(
            editForm.dataset.courseId,
            editReq.value,
            document.getElementById("editRef"),
            document.getElementById("editRefWrap")
          )
        );
      }
      editForm.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
}

async function loadInstructorAssignment() {
  const id = qs("id");
  const data = await API.get(`/api/assignments/${id}`);
  const a = data.assignment;
  document.getElementById("assignTitle").textContent = a.title;
  document.getElementById("assignMeta").textContent = `${a.course_title || ""} · Due ${fmtDate(a.due_date)} · Max ${a.max_score}`;
  const rows = a.submissions || [];
  document.getElementById("subBody").innerHTML =
    rows
      .map(
        (s) => `<tr>
        <td>${escapeHtml(s.student_name)}</td>
        <td>${fmtDate(s.submitted_at)}</td>
        <td>${escapeHtml(s.comment || "—")}</td>
        <td>${s.file_path ? `<button class="btn btn-ghost" type="button" data-file="${s.file_path}">Download</button>` : "None"}</td>
        <td>
          <form class="score-form" data-sub="${s.submission_id}">
            <label class="visually-hidden" for="score-${s.submission_id}">Score for ${escapeHtml(s.student_name)}</label>
            <input id="score-${s.submission_id}" type="number" name="score" min="0" max="${a.max_score}" value="${s.score != null ? s.score : ""}" style="width:72px">
            <button class="btn" type="submit">Save</button>
          </form>
        </td>
      </tr>`
      )
      .join("") || `<tr><td colspan="5" class="empty">No submissions yet.</td></tr>`;
  document.getElementById("subBody").addEventListener("click", async (e) => {
    const file = e.target.dataset.file;
    if (!file) return;
    try {
      await API.download(`/api/uploads/${file}`, file);
    } catch (ex) {
      alert(ex.message);
    }
  });
  document.getElementById("subBody").addEventListener("submit", async (e) => {
    const form = e.target.closest(".score-form");
    if (!form) return;
    e.preventDefault();
    try {
      await API.put(`/api/submissions/${form.dataset.sub}/score`, { score: Number(form.score.value) });
      location.reload();
    } catch (ex) {
      alert(ex.message);
    }
  });
}

async function loadAlerts() {
  const data = await API.get("/api/analytics/alerts");
  document.getElementById("deadlines").innerHTML =
    data.deadline_alerts
      .map((a) => `<div class="card"><strong>${escapeHtml(a.title)}</strong><p class="muted">${escapeHtml(a.detail)}</p></div>`)
      .join("") || `<p class="empty">No deadline alerts.</p>`;
  const perf = document.getElementById("performance");
  if (perf) {
    perf.innerHTML =
      (data.performance_alerts || [])
        .map(
          (a) => `<a class="row-card" href="/instructor/student?id=${a.student_id}">
            <div class="grow"><h4>${escapeHtml(a.title)}</h4><div class="meta">${escapeHtml(a.detail)}</div></div>
            <span class="badge high">Red</span>
          </a>`
        )
        .join("") || `<p class="empty">No performance alerts.</p>`;
  }
  document.getElementById("disengaged").innerHTML =
    data.disengaged
      .map(
        (s) => `<a class="row-card" href="/instructor/student?id=${s.student_id}">
        <div class="grow"><h4>${escapeHtml(s.full_name)}</h4><div class="meta">${s.days_since_login} days since login · ${s.time_spent_minutes} min on modules</div></div>
        <span class="badge ${(s.risk_level || "Low").toLowerCase()}">${escapeHtml(s.risk_level)}</span>
      </a>`
      )
      .join("") || `<p class="empty">No disengaged students flagged.</p>`;
}

async function fillChartGrid(elementId, extra = true) {
  const names = [
    ["completions", "Assignment completion"],
    ["score_trend", "Score trend"],
    ["heatmap", "Login heatmap"],
    ["histogram", "Score distribution"],
    ["milestones", "Milestone progress"],
  ];
  if (extra) {
    names.push(["coefficients", "Model coefficients"], ["tree", "Decision tree"]);
  }
  const grid = document.getElementById(elementId);
  if (!grid) return;
  const token = API.token();
  grid.innerHTML = names
    .map(
      ([key, title]) => `<figure class="card">
      <h3>${title}</h3>
      <img alt="${title}" src="/api/analytics/charts/${key}" data-auth="1">
    </figure>`
    )
    .join("");
  for (const img of grid.querySelectorAll("img")) {
    try {
      const res = await fetch(img.getAttribute("src"), { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error("missing");
      const blob = await res.blob();
      img.src = URL.createObjectURL(blob);
    } catch {
      img.replaceWith(Object.assign(document.createElement("p"), { className: "muted", textContent: "Chart not available yet." }));
    }
  }
}

async function loadReports() {
  await fillChartGrid("charts", true);
}
