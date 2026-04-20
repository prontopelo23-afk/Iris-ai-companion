(() => {
  const state = {
    x: 0,
    y: 0,
    tx: 0,
    ty: 0,
    mouseX: window.innerWidth * 0.5,
    mouseY: window.innerHeight * 0.5,
    mode: "autopilot",
    scene: "libre",
    power: "on",
    servicesOk: 5,
    servicesTotal: 5,
    lastPick: 0,
    bubbleUntil: 0,
    bubbleText: "",
    wobbleSeed: Math.random() * 1000,
  };

  const PALETTES = {
    normal:    { core: "#7dd3fc", halo: "#22d3ee", ring: "#67e8f9", accent: "#cffafe" },
    travail:   { core: "#a78bfa", halo: "#8b5cf6", ring: "#c4b5fd", accent: "#ede9fe" },
    veille:    { core: "#60a5fa", halo: "#0ea5e9", ring: "#7dd3fc", accent: "#dbeafe" },
    autopilot: { core: "#fbbf24", halo: "#fb7185", ring: "#fdba74", accent: "#fef3c7" },
    off:       { core: "#fb7185", halo: "#ef4444", ring: "#f9a8d4", accent: "#ffe4e6" },
    alert:     { core: "#fb7185", halo: "#f97316", ring: "#fdba74", accent: "#fff7ed" },
  };

  const BUBBLES = {
    normal: ["ok", "mode normal", "je veille"],
    travail: ["travail", "focus", "je traite"],
    veille: ["veille", "je surveille", "signal"],
    autopilot: ["autopilot", "je pilote", "scan live"],
    off: ["pause", "mode off"],
    alert: ["attention", "alerte", "point chaud"],
  };

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const dist = (ax, ay, bx, by) => Math.hypot(ax - bx, ay - by);

  function visible(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.display !== "none" && s.visibility !== "hidden" && parseFloat(s.opacity || "1") > 0.01;
  }

  function clean(t) {
    return (t || "").replace(/\s+/g, " ").trim();
  }

  function allText() {
    return clean(document.body?.innerText || "").toLowerCase();
  }

  function root() {
    return document.getElementById("iris-v41-orb-root");
  }

  function canvasEl() {
    return document.getElementById("iris-v41-orb-canvas");
  }

  function bubbleEl() {
    return document.getElementById("iris-v41-bubble");
  }

  function badgeEl() {
    return document.getElementById("iris-v41-badge");
  }

  function findDock() {
    const candidates = [...document.querySelectorAll("button, a, div, section, aside")]
      .filter(visible)
      .filter(el => /parler à iris/i.test(clean(el.textContent || "")));
    if (!candidates.length) return null;
    let best = null;
    let bestScore = Infinity;
    for (const el of candidates) {
      const r = el.getBoundingClientRect();
      const score = Math.abs(window.innerWidth - r.right) + Math.abs(window.innerHeight - r.bottom) + Math.abs(r.width - 220);
      if (score < bestScore) {
        bestScore = score;
        best = el;
      }
    }
    return best;
  }

  function findTopHeroBox() {
    const headers = [...document.querySelectorAll("h1, h2, .hero, section, article")]
      .filter(visible)
      .filter(el => /iris/i.test(clean(el.textContent || "")));
    if (!headers.length) return null;
    return headers[0].getBoundingClientRect();
  }

  function removeOldMascots() {
    document.documentElement.id = "iris-v41-no-robot";
    const selectors = [
      "#iris-pet", ".iris-pet", "#pet", ".pet",
      "#mascot", ".mascot", "#iris-mascot", ".iris-mascot",
      "#robot", ".robot", ".companion-pet", "#companion-pet",
      ".companion-avatar", "#companion-avatar",
      "[data-role='pet']", "[data-role='mascot']"
    ];
    selectors.forEach(sel => {
      document.querySelectorAll(sel).forEach(el => {
        if (el && !el.closest("#iris-v41-orb-root")) {
          el.style.display = "none";
          el.style.opacity = "0";
          el.style.visibility = "hidden";
          el.setAttribute("aria-hidden", "true");
        }
      });
    });
  }

  function detectMode() {
    const text = allText();
    if (/\bmode autopilot\b/.test(text)) return "autopilot";
    if (/\bmode travail\b/.test(text)) return "travail";
    if (/\bmode veille légère\b/.test(text)) return "veille";
    if (/\bmode normal\b/.test(text)) return "normal";
    if (/\bpower off\b/.test(text)) return "off";
    return state.mode || "autopilot";
  }

  function detectPower() {
    const text = allText();
    if (/\bpower on\b/.test(text)) return "on";
    if (/\bpower off\b/.test(text)) return "off";
    return state.power || "on";
  }

  function detectServices() {
    const text = clean(document.body?.innerText || "");
    const m = text.match(/(\d+)\s*\/\s*(\d+)\s*services/i);
    if (m) {
      state.servicesOk = Number(m[1]);
      state.servicesTotal = Number(m[2]);
      return;
    }
    state.servicesOk = 5;
    state.servicesTotal = 5;
  }

  function detectScene() {
    const dock = findDock();
    if (dock) {
      const wrap = dock.closest("section, article, div");
      const t = clean((wrap?.textContent || dock.textContent || "")).toLowerCase();
      const m = t.match(/scène\s*:\s*([a-zàéèêîïôûùç -]+)/i);
      if (m) {
        const s = m[1].toLowerCase();
        if (s.includes("dock")) return "dock";
        if (s.includes("bureau")) return "bureau";
        if (s.includes("travail")) return "travail";
        if (s.includes("recherche")) return "recherche";
        if (s.includes("repos")) return "repos";
        if (s.includes("libre")) return "libre";
      }
    }
    return state.scene || "libre";
  }

  function paletteName() {
    if (state.power === "off") return "off";
    if (state.servicesOk < state.servicesTotal) return "alert";
    if (state.mode === "travail") return "travail";
    if (state.mode === "veille") return "veille";
    if (state.mode === "normal") return "normal";
    return "autopilot";
  }

  function setVars() {
    const p = PALETTES[paletteName()] || PALETTES.autopilot;
    document.documentElement.style.setProperty("--iris-v41-core", p.core);
    document.documentElement.style.setProperty("--iris-v41-halo", p.halo);
    document.documentElement.style.setProperty("--iris-v41-ring", p.ring);
    document.documentElement.style.setProperty("--iris-v41-accent", p.accent);
    const badge = badgeEl();
    if (badge) badge.textContent = paletteName();
  }

  function say(text, ms = 1800) {
    state.bubbleText = text;
    state.bubbleUntil = performance.now() + ms;
    const bubble = bubbleEl();
    if (!bubble) return;
    bubble.textContent = text;
    bubble.classList.add("show");
  }

  function maybeSayMood() {
    const set = BUBBLES[paletteName()] || BUBBLES.autopilot;
    const pick = set[Math.floor(Math.random() * set.length)];
    say(pick, 1200);
  }

  function createOrb() {
    if (root()) return;
    const el = document.createElement("div");
    el.id = "iris-v41-orb-root";
    el.className = "iris-v41-soft-focus";
    el.innerHTML = `
      <div id="iris-v41-bubble"></div>
      <canvas id="iris-v41-orb-canvas" width="190" height="190"></canvas>
      <div id="iris-v41-badge" class="iris-v41-badge">autopilot</div>
    `;
    document.body.appendChild(el);
  }

  function bounds() {
    const leftNav = 350;
    const rightGap = 30;
    const topGap = 110;
    const bottomGap = 60;
    return {
      minX: leftNav,
      maxX: window.innerWidth - 190 - rightGap,
      minY: topGap,
      maxY: window.innerHeight - 190 - bottomGap
    };
  }

  function pickTarget(force = false) {
    const now = performance.now();
    if (!force && now - state.lastPick < 2200) return;
    state.lastPick = now;

    const b = bounds();
    let x = state.tx || (window.innerWidth * 0.58);
    let y = state.ty || (window.innerHeight * 0.36);

    const dock = findDock();
    const hero = findTopHeroBox();

    if (state.scene === "dock" && dock) {
      const r = dock.getBoundingClientRect();
      x = clamp(r.left - 110, b.minX, b.maxX);
      y = clamp(r.top - 110, b.minY, b.maxY);
    } else if (state.scene === "bureau") {
      x = clamp(window.innerWidth * 0.78, b.minX, b.maxX);
      y = clamp(window.innerHeight * 0.20, b.minY, b.maxY);
    } else if (state.scene === "travail") {
      x = clamp(window.innerWidth * 0.68, b.minX, b.maxX);
      y = clamp(window.innerHeight * 0.34, b.minY, b.maxY);
    } else if (state.scene === "recherche") {
      x = clamp(window.innerWidth * 0.77, b.minX, b.maxX);
      y = clamp(window.innerHeight * 0.46, b.minY, b.maxY);
    } else if (state.scene === "repos") {
      x = clamp(window.innerWidth * 0.70, b.minX, b.maxX);
      y = clamp(window.innerHeight * 0.74, b.minY, b.maxY);
    } else {
      const zone = Math.random();
      if (hero && zone < 0.30) {
        x = clamp(hero.left + hero.width * (0.40 + Math.random() * 0.34), b.minX, b.maxX);
        y = clamp(hero.top + hero.height * (0.30 + Math.random() * 0.56), b.minY, b.maxY);
      } else if (dock && zone < 0.55) {
        const r = dock.getBoundingClientRect();
        x = clamp(r.left - 150 - Math.random() * 60, b.minX, b.maxX);
        y = clamp(r.top - 60 - Math.random() * 90, b.minY, b.maxY);
      } else {
        x = b.minX + Math.random() * (b.maxX - b.minX);
        y = b.minY + Math.random() * (b.maxY - b.minY);
      }
    }

    state.tx = x;
    state.ty = y;
  }

  function bindSceneButtons() {
    [...document.querySelectorAll("button, a, div")].forEach(el => {
      if (el.dataset.irisV41SceneBound) return;
      const t = clean(el.textContent || "").toLowerCase();
      if (!["libre", "bureau", "travail", "recherche", "repos", "dock chat"].includes(t)) return;
      el.dataset.irisV41SceneBound = "1";
      el.addEventListener("click", () => {
        if (t === "dock chat") state.scene = "dock";
        else state.scene = t;
        pickTarget(true);
        say(t === "dock chat" ? "dock chat" : t, 1200);
      });
    });
  }

  function bindModeButtons() {
    [...document.querySelectorAll("button, a, div")].forEach(el => {
      if (el.dataset.irisV41ModeBound) return;
      const t = clean(el.textContent || "").toLowerCase();
      if (!["on", "off", "normal", "travail", "veille légère", "autopilot"].includes(t)) return;
      el.dataset.irisV41ModeBound = "1";
      el.addEventListener("click", () => {
        if (t === "on" || t === "off") state.power = t;
        else if (t === "veille légère") state.mode = "veille";
        else state.mode = t;
        setVars();
        maybeSayMood();
      });
    });
  }

  function bindMouse() {
    window.addEventListener("mousemove", e => {
      state.mouseX = e.clientX;
      state.mouseY = e.clientY;
      const centerX = state.x + 95;
      const centerY = state.y + 95;
      const d = dist(centerX, centerY, state.mouseX, state.mouseY);
      if (d < 150) {
        const dx = centerX - state.mouseX || 1;
        const dy = centerY - state.mouseY || 1;
        const mag = Math.hypot(dx, dy) || 1;
        state.tx = clamp(state.x + (dx / mag) * 120, bounds().minX, bounds().maxX);
        state.ty = clamp(state.y + (dy / mag) * 120, bounds().minY, bounds().maxY);
        if (performance.now() > state.bubbleUntil - 500) say("oui ?", 900);
      }
    }, { passive: true });

    window.addEventListener("resize", () => pickTarget(true), { passive: true });
    window.addEventListener("scroll", () => {
      if (state.scene !== "libre") pickTarget(true);
    }, { passive: true });
  }

  function refreshData() {
    state.mode = detectMode();
    state.power = detectPower();
    state.scene = detectScene();
    detectServices();
    setVars();
    const dock = findDock();
    const r = root();
    if (r) r.classList.toggle("iris-v41-docked", !!dock && state.scene === "dock");
  }

  function draw() {
    const canvas = canvasEl();
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    const size = canvas.clientWidth || 190;
    if (canvas.width !== Math.round(size * dpr)) {
      canvas.width = Math.round(size * dpr);
      canvas.height = Math.round(size * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size, size);

    const p = PALETTES[paletteName()] || PALETTES.autopilot;
    const t = performance.now() * 0.001;
    const cx = size * 0.5;
    const cy = size * 0.5;
    const pulse = 1 + Math.sin(t * (paletteName() === "alert" ? 5.2 : 2.4)) * 0.035;
    const outerR = size * 0.24 * pulse;
    const innerR = size * 0.13 * (1 + Math.sin(t * 3.2) * 0.04);

    const halo = ctx.createRadialGradient(cx, cy, 8, cx, cy, size * 0.44);
    halo.addColorStop(0, hexToRgba(p.halo, 0.42));
    halo.addColorStop(0.45, hexToRgba(p.halo, 0.12));
    halo.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(cx, cy, size * 0.42, 0, Math.PI * 2);
    ctx.fill();

    for (let i = 0; i < 2; i++) {
      const rr = outerR + i * 14 + Math.sin(t * 1.7 + i) * 2.2;
      ctx.strokeStyle = hexToRgba(p.ring, i === 0 ? 0.30 : 0.14);
      ctx.lineWidth = i === 0 ? 2.4 : 1.2;
      ctx.beginPath();
      ctx.arc(cx, cy, rr, t * 0.5 + i, t * 0.5 + i + Math.PI * 1.65);
      ctx.stroke();
    }

    const core = ctx.createRadialGradient(cx - 10, cy - 12, 4, cx, cy, innerR * 2.4);
    core.addColorStop(0, hexToRgba(p.accent, 0.96));
    core.addColorStop(0.36, hexToRgba(p.core, 0.94));
    core.addColorStop(0.72, hexToRgba(p.halo, 0.52));
    core.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = hexToRgba(p.accent, 0.55);
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(cx, cy, innerR * 1.7, t * 0.8, t * 0.8 + Math.PI * 1.35);
    ctx.stroke();

    const orbiters = 7;
    for (let i = 0; i < orbiters; i++) {
      const a = t * (0.7 + i * 0.04) + i * (Math.PI * 2 / orbiters);
      const rr = outerR + 14 + Math.sin(t * 1.7 + i) * 5;
      const px = cx + Math.cos(a) * rr;
      const py = cy + Math.sin(a) * rr * 0.82;
      const pr = 2 + ((i % 3) * 0.8);
      ctx.fillStyle = hexToRgba(i % 2 ? p.accent : p.ring, 0.88);
      ctx.beginPath();
      ctx.arc(px, py, pr, 0, Math.PI * 2);
      ctx.fill();
    }

    for (let i = 0; i < 14; i++) {
      const a = t * 0.9 + i * 0.47 + state.wobbleSeed;
      const rr = outerR * 0.4 + (i % 4) * 2;
      const px = cx + Math.cos(a) * rr;
      const py = cy + Math.sin(a * 1.2) * rr;
      ctx.fillStyle = hexToRgba(p.accent, 0.16);
      ctx.beginPath();
      ctx.arc(px, py, 1.2, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function hexToRgba(hex, alpha) {
    const h = hex.replace("#", "");
    const n = parseInt(h.length === 3 ? h.split("").map(c => c + c).join("") : h, 16);
    const r = (n >> 16) & 255;
    const g = (n >> 8) & 255;
    const b = n & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function animate() {
    const now = performance.now();

    if (now - state.lastPick > 6500 || dist(state.x, state.y, state.tx, state.ty) < 10) {
      pickTarget();
    }

    state.x += (state.tx - state.x) * 0.026;
    state.y += (state.ty - state.y) * 0.026;

    const bobX = Math.sin(now * 0.0013 + state.wobbleSeed) * 3.0;
    const bobY = Math.cos(now * 0.0017 + state.wobbleSeed) * 4.0;

    const r = root();
    if (r) {
      r.style.left = `${Math.round(state.x + bobX)}px`;
      r.style.top = `${Math.round(state.y + bobY)}px`;
    }

    const bubble = bubbleEl();
    if (bubble) {
      if (now < state.bubbleUntil) bubble.classList.add("show");
      else bubble.classList.remove("show");
    }

    draw();
    requestAnimationFrame(animate);
  }

  function init() {
    createOrb();
    removeOldMascots();
    bindSceneButtons();
    bindModeButtons();
    bindMouse();
    refreshData();
    pickTarget(true);

    const b = bounds();
    state.x = clamp(window.innerWidth * 0.52, b.minX, b.maxX);
    state.y = clamp(window.innerHeight * 0.36, b.minY, b.maxY);
    state.tx = state.x;
    state.ty = state.y;

    maybeSayMood();

    setInterval(() => {
      removeOldMascots();
      bindSceneButtons();
      bindModeButtons();
      refreshData();
    }, 2500);

    setInterval(() => {
      if (state.scene === "libre") pickTarget();
    }, 5000);

    animate();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
