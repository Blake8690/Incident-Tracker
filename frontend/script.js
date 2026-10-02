const API_URL = "https://indicent-tracker-com.onrender.com";

const root = document.documentElement;
const motionOK = !matchMedia("(prefers-reduced-motion: reduce)").matches;
const canHover = matchMedia("(hover: hover)").matches;
root.classList.add("js");
if (motionOK) root.classList.add("motion");

// Väck Render-servern direkt, så att registreringen går snabbt sen
fetch(`${API_URL}/`).catch(() => {});

// ---------- Tema ----------
const themeBtn = document.getElementById("theme-toggle");
const setTheme = t => {
  root.dataset.theme = t;
  if (themeBtn) themeBtn.textContent = t === "light" ? "☾" : "☀";
};
try { setTheme(localStorage.getItem("theme") || "dark"); } catch { setTheme("dark"); }
themeBtn?.addEventListener("click", () => {
  const next = root.dataset.theme === "light" ? "dark" : "light";
  setTheme(next);
  try { localStorage.setItem("theme", next); } catch {}
});

// ---------- Laddningsskärm ----------
const loaderDone = new Promise(resolve => {
  const loader = document.getElementById("loader");
  if (!loader) return resolve();
  root.classList.add("loading");
  const min = new Promise(r => setTimeout(r, motionOK ? 900 : 0));
  const loaded = new Promise(r => document.readyState === "complete" ? r() : addEventListener("load", r));
  const max = new Promise(r => setTimeout(r, 3000));
  Promise.race([Promise.all([min, loaded, document.fonts.ready]), max]).then(() => {
    loader.classList.add("done");
    root.classList.remove("loading");
    setTimeout(resolve, motionOK ? 250 : 0);
    setTimeout(() => loader.remove(), 800);
  });
});

const yearEl = document.getElementById("year");
if (yearEl) yearEl.textContent = new Date().getFullYear();

// ---------- Navigering ----------
const nav = document.getElementById("nav");
const onScroll = () => nav?.classList.toggle("scrolled", scrollY > 30);
addEventListener("scroll", onScroll, { passive: true });
onScroll();

const burger = document.getElementById("burger");
const navLinks = document.getElementById("navLinks");
burger?.addEventListener("click", () => {
  const open = navLinks.classList.toggle("open");
  burger.setAttribute("aria-expanded", open);
});
navLinks?.querySelectorAll("a, button").forEach(a => a.addEventListener("click", () => {
  navLinks.classList.remove("open");
  burger.setAttribute("aria-expanded", false);
}));

// ---------- Löpband ----------
const marquee = document.getElementById("marquee");
if (marquee && typeof KOMMUNER !== "undefined") {
  const pick = [...KOMMUNER].sort(() => Math.random() - 0.5).slice(0, 40);
  const html = pick.map(k => `<span>${k}</span>`).join("");
  marquee.innerHTML = html + html; // dubbelt för sömlös loop
}

// ---------- Scroll-animationer ----------
const reveal = new IntersectionObserver(entries => entries.forEach(e => {
  if (e.isIntersecting) { e.target.classList.add("visible"); reveal.unobserve(e.target); }
}), { threshold: 0.15 });
document.querySelectorAll(".reveal").forEach(el => reveal.observe(el));

if (motionOK) {
  // Rubriker fälls upp ord för ord
  document.querySelectorAll("main h1, main h2").forEach(h => {
    let i = 0;
    const walker = document.createTreeWalker(h, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {
      const frag = document.createDocumentFragment();
      node.textContent.split(/(\s+)/).forEach(part => {
        if (!part) return;
        if (/^\s+$/.test(part)) return frag.append(part);
        const w = document.createElement("span");
        w.className = "word";
        const inner = document.createElement("span");
        inner.style.setProperty("--i", i++);
        inner.textContent = part;
        w.append(inner);
        frag.append(w);
      });
      node.replaceWith(frag);
    });
  });

  // Kort fälls upp i 3D när de scrollas in
  const items = [...document.querySelectorAll("[data-3d]")];
  const docTop = el => { let t = 0; for (; el; el = el.offsetParent) t += el.offsetTop; return t; };
  let tops = [], ticking = false;
  const update = () => {
    ticking = false;
    items.forEach((el, n) => {
      const p = Math.min(Math.max((innerHeight - (tops[n] - scrollY)) / (innerHeight * 0.55), 0), 1);
      el.style.setProperty("--p", p.toFixed(3));
    });
  };
  const measure = () => { tops = items.map(docTop); update(); };
  addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
  addEventListener("resize", measure);
  addEventListener("load", measure);
  measure();

  if (canHover) {
    // Korten lutar efter muspekaren
    document.querySelectorAll(".tilt").forEach(card => {
      card.addEventListener("mousemove", e => {
        const r = card.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - 0.5;
        const y = (e.clientY - r.top) / r.height - 0.5;
        card.style.transform = `perspective(1100px) rotateX(${(-y * 6).toFixed(2)}deg) rotateY(${(x * 8).toFixed(2)}deg)`;
      });
      card.addEventListener("mouseleave", () => card.style.transform = "");
    });
    // Primärknappar dras mot muspekaren
    document.querySelectorAll(".btn-primary, .hero .btn-ghost").forEach(btn => {
      btn.addEventListener("mousemove", e => {
        const r = btn.getBoundingClientRect();
        btn.style.transform = `translate(${((e.clientX - r.left - r.width / 2) * 0.18).toFixed(1)}px, ${((e.clientY - r.top - r.height / 2) * 0.3).toFixed(1)}px)`;
      });
      btn.addEventListener("mouseleave", () => btn.style.transform = "");
    });
  }
}

// Siffror räknar upp, rubriker spelas upp när de syns
const countUp = el => {
  const end = +el.textContent, start = performance.now();
  if (!motionOK || !end) return;
  const tick = now => {
    const t = Math.min((now - start) / 1400, 1);
    el.textContent = Math.round(end * (1 - Math.pow(1 - t, 3)));
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
};
const inView = new IntersectionObserver(entries => entries.forEach(e => {
  if (!e.isIntersecting) return;
  if (e.target.hasAttribute("data-count")) countUp(e.target);
  else e.target.classList.add("in");
  inView.unobserve(e.target);
}), { threshold: 0.3 });
loaderDone.then(() => document.querySelectorAll("main h1, main h2, [data-count]").forEach(el => inView.observe(el)));

// ---------- FAQ ----------
document.querySelectorAll(".faq-item").forEach(item => {
  const q = item.querySelector(".faq-q"), a = item.querySelector(".faq-a");
  q.addEventListener("click", () => {
    const open = item.classList.toggle("open");
    q.setAttribute("aria-expanded", open);
    a.style.maxHeight = open ? a.scrollHeight + "px" : "0";
  });
});

// ---------- Tider ----------
const TIDER = Array.from({ length: 48 }, (_, i) => `${String(Math.floor(i / 2)).padStart(2, "0")}:${i % 2 ? "30" : "00"}`);
function fillTimes(select, value = "21:00") {
  select.innerHTML = TIDER.map(t => `<option${t === value ? " selected" : ""}>${t}</option>`).join("");
}
function fillKommuner(datalist) {
  datalist.innerHTML = KOMMUNER.map(k => `<option value="${k}">`).join("");
}
// Matcha oavsett skiftläge, så att "malmö" blir "Malmö"
const normKommun = v => KOMMUNER.find(k => k.toLowerCase() === v.trim().toLowerCase());

// Klockan i exempelkortet
const clockDemo = document.getElementById("clockDemo");
let clockIdx = TIDER.indexOf("21:00");
document.querySelectorAll("[data-clock]").forEach(b => b.addEventListener("click", () => {
  clockIdx = (clockIdx + +b.dataset.clock + TIDER.length) % TIDER.length;
  clockDemo.textContent = TIDER[clockIdx];
}));

// ---------- Modaler ----------
let lastFocus = null;
function openModal(modal) {
  lastFocus = document.activeElement;
  modal.hidden = false;
  requestAnimationFrame(() => modal.classList.add("open"));
  document.body.style.overflow = "hidden";
  setTimeout(() => modal.querySelector("input:not([type=radio]), select, button.btn")?.focus(), 50);
}
function closeModal(modal) {
  modal.classList.remove("open");
  document.body.style.overflow = "";
  setTimeout(() => { modal.hidden = true; }, 300);
  lastFocus?.focus?.();
}
document.querySelectorAll(".modal").forEach(m => {
  m.addEventListener("click", e => { if (e.target === m || e.target.closest("[data-close]")) closeModal(m); });
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape") document.querySelectorAll(".modal.open").forEach(closeModal);
});

// ---------- Registrering i steg ----------
const signupModal = document.getElementById("signupModal");
if (signupModal) {
  const form = document.getElementById("signupForm");
  const steps = [...form.querySelectorAll(".form-step")];
  const labels = [...signupModal.querySelectorAll(".progress-labels li")];
  const back = document.getElementById("formBack");
  const next = document.getElementById("formNext");
  const err = document.getElementById("formError");
  const kommunIn = document.getElementById("kommun");
  const timeRow = document.getElementById("timeRow");
  const timeSel = document.getElementById("digestTime");
  let current = 0;

  fillKommuner(document.getElementById("kommun-list"));
  fillTimes(timeSel);

  const mode = () => form.querySelector("input[name=mode]:checked").value;
  const syncMode = () => { timeRow.hidden = mode() !== "digest"; };
  form.querySelectorAll("input[name=mode]").forEach(r => r.addEventListener("change", syncMode));

  form.querySelectorAll("[data-kommun]").forEach(chip => chip.addEventListener("click", () => {
    kommunIn.value = chip.textContent.trim();
    form.querySelectorAll("[data-kommun]").forEach(c => c.classList.toggle("active", c === chip));
    go(1);
  }));

  function go(i) {
    steps[i].classList.remove("flip-next", "flip-prev");
    if (i !== current && motionOK) { void steps[i].offsetWidth; steps[i].classList.add(i > current ? "flip-next" : "flip-prev"); }
    current = i;
    steps.forEach((s, n) => s.hidden = n !== i);
    labels.forEach((l, n) => l.classList.toggle("active", n <= i));
    document.getElementById("progressFill").style.width = ((i + 1) / steps.length * 100) + "%";
    back.hidden = i === 0;
    next.innerHTML = i === steps.length - 1 ? "Aktivera bevakning →" : "Nästa →";
    err.textContent = "";
    const f = steps[i].querySelector("input:not([type=radio]), input[type=radio]:checked");
    if (signupModal.classList.contains("open")) setTimeout(() => f?.focus(), 60);
  }

  function fail(msg, el) { err.textContent = msg; el?.focus(); return false; }
  function validate(i) {
    if (i === 0) {
      const k = normKommun(kommunIn.value);
      if (!k) return fail("Välj en kommun från listan.", kommunIn);
      kommunIn.value = k;
    }
    if (i === 2) {
      const name = document.getElementById("name"), email = document.getElementById("email");
      if (!name.value.trim()) return fail("Fyll i ditt namn.", name);
      if (!/^\S+@\S+\.\S+$/.test(email.value.trim())) return fail("Kontrollera e-postadressen.", email);
    }
    return true;
  }

  document.querySelectorAll("[data-open-form]").forEach(btn => btn.addEventListener("click", e => {
    e.preventDefault();
    if (btn.dataset.mode) {
      form.querySelector(`input[name=mode][value=${btn.dataset.mode}]`).checked = true;
      syncMode();
    }
    if (!form.hidden) go(0);
    openModal(signupModal);
  }));

  back.addEventListener("click", () => go(current - 1));

  form.addEventListener("submit", async e => {
    e.preventDefault();
    if (!validate(current)) return;
    if (current < steps.length - 1) return go(current + 1);

    const payload = {
      name: document.getElementById("name").value.trim(),
      email: document.getElementById("email").value.trim().toLowerCase(),
      kommun: kommunIn.value,
      delivery_mode: mode(),
      digest_time: timeSel.value,
    };
    next.disabled = back.disabled = true;
    next.textContent = "Aktiverar…";
    try {
      const res = await fetch(`${API_URL}/api/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Något gick fel. Försök igen.");
      form.hidden = true;
      signupModal.querySelector(".modal-head").hidden = true;
      document.getElementById("doneText").textContent = payload.delivery_mode === "digest"
        ? `Du får en sammanfattning för ${payload.kommun} varje dag kl. ${payload.digest_time}. Ett bekräftelsemejl är på väg.`
        : `Du får ett mejl så fort något händer i ${payload.kommun}. Ett bekräftelsemejl är på väg.`;
      document.getElementById("formDone").hidden = false;
    } catch (ex) {
      err.textContent = ex.message === "Failed to fetch" ? "Kunde inte nå servern. Försök igen om en stund." : ex.message;
    } finally {
      next.disabled = back.disabled = false;
      if (!form.hidden) next.innerHTML = "Aktivera bevakning →";
    }
  });

  go(0);
}

// ---------- Be om hanteringslänk ----------
const manageModal = document.getElementById("manageModal");
if (manageModal) {
  const form = document.getElementById("manageForm");
  document.querySelectorAll("[data-open-manage]").forEach(b => b.addEventListener("click", e => {
    e.preventDefault();
    openModal(manageModal);
  }));
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const email = document.getElementById("manageEmail");
    const err = document.getElementById("manageError");
    if (!/^\S+@\S+\.\S+$/.test(email.value.trim())) { err.textContent = "Kontrollera e-postadressen."; return email.focus(); }
    const btn = form.querySelector("button");
    btn.disabled = true;
    try {
      const res = await fetch(`${API_URL}/api/manage-link`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.value.trim().toLowerCase() }),
      });
      if (!res.ok) throw new Error();
      form.hidden = true;
      document.getElementById("manageDone").hidden = false;
    } catch {
      err.textContent = "Kunde inte nå servern. Försök igen om en stund.";
    } finally {
      btn.disabled = false;
    }
  });
}
