
(() => {
  const qs = (s, r=document) => r.querySelector(s);
  const qsa = (s, r=document) => Array.from(r.querySelectorAll(s));
  const txt = el => (el?.textContent || "").trim().toLowerCase();
  const byText = (needle, root=document) =>
    qsa("button, a, div, span", root).find(el => txt(el).includes(needle.toLowerCase()));

  const state = {
    scene: localStorage.getItem("iris_v35_scene") || "libre",
    mode: "autopilot",
    currentSite: "",
    mouseX: window.innerWidth - 120,
    mouseY: window.innerHeight - 120,
    x: window.innerWidth - 220,
    y: window.innerHeight - 240,
    tx: window.innerWidth - 220,
    ty: window.innerHeight - 240,
    lastBlink: 0,
    chatOpen: true,
    listening: false
  };

  function createPet(){
    if (qs("#iris-v35-layer")) return;
    const layer = document.createElement("div");
    layer.id = "iris-v35-layer";
    layer.innerHTML = `
      <div id="iris-v35-pet" class="walking">
        <div class="state-badge">IRIS</div>
        <div class="pet-wrap">
          <div class="shadow"></div>
          <div class="antenna"></div>
          <div class="head"></div>
          <div class="visor"></div>
          <div class="eye left"></div>
          <div class="eye right"></div>
          <div class="blush left"></div>
          <div class="blush right"></div>
          <div class="mouth"></div>
          <div class="body"></div>
          <div class="belly"></div>
          <div class="arm left"><div class="hand"></div></div>
          <div class="arm right"><div class="hand"></div></div>
          <div class="leg left"><div class="foot"></div></div>
          <div class="leg right"><div class="foot"></div></div>
        </div>
      </div>
    `;
    document.body.appendChild(layer);
  }

  function setBadge(text){
    const b = qs("#iris-v35-pet .state-badge");
    if (b) b.textContent = text;
  }

  function petEl(){ return qs("#iris-v35-pet"); }

  function findZoneByHeading(textNeedle){
    const headings = qsa("h1,h2,h3,h4,.title");
    const h = headings.find(x => txt(x).includes(textNeedle));
    if (!h) return null;
    const box = h.closest("section, article, div, aside") || h.parentElement;
    return box?.getBoundingClientRect() || null;
  }

  function computeTarget(){
    const w = window.innerWidth, h = window.innerHeight;
    const chat = qs(".iris-v35-chat-dock");
    const chatBox = chat?.getBoundingClientRect();
    const reserve = {
      right: chatBox ? Math.max(0, w - chatBox.left + 26) : 30,
      bottom: chatBox ? Math.max(0, h - chatBox.top + 18) : 34
    };

    const rand = (a,b) => a + Math.random() * (b-a);

    if (state.scene === "dock" && chatBox) {
      return {x: Math.max(26, chatBox.left - 100), y: Math.max(100, chatBox.top - 8), mood:"talking", badge:"chat"};
    }
    if (state.scene === "repos") {
      return {x: w * 0.58, y: h - 185, mood:"sleeping", badge:"repos"};
    }
    if (state.scene === "travail") {
      const zone = findZoneByHeading("agents live") || findZoneByHeading("modes système");
      if (zone) return {x: Math.min(zone.right - 120, w - reserve.right - 40), y: zone.top + 32, mood:"working", badge:"travail"};
      return {x: w * 0.64, y: 250, mood:"working", badge:"travail"};
    }
    if (state.scene === "recherche") {
      const zone = findZoneByHeading("watch radar") || findZoneByHeading("veille active") || findZoneByHeading("service mesh");
      if (zone) return {x: Math.min(zone.right - 124, w - reserve.right - 40), y: zone.top + 42, mood:"researching", badge:"recherche"};
      return {x: w * 0.65, y: h * 0.42, mood:"researching", badge:"scan"};
    }
    if (state.scene === "bureau") {
      return {x: 220, y: h - 190, mood:"working", badge:"bureau"};
    }

    const mx = state.mouseX, my = state.mouseY;
    const near = Math.hypot(state.x - mx, state.y - my) < 110;
    if (near) {
      return {
        x: Math.min(w - reserve.right - 100, Math.max(160, mx + 42)),
        y: Math.min(h - reserve.bottom - 120, Math.max(90, my - 28)),
        mood:"hovering", badge:"coucou"
      };
    }
    return {
      x: rand(170, Math.max(190, w - reserve.right - 120)),
      y: rand(110, Math.max(140, h - reserve.bottom - 150)),
      mood:"walking", badge:"libre"
    };
  }

  function applyMood(mood, badge){
    const pet = petEl();
    if (!pet) return;
    pet.className = mood || "walking";
    setBadge(badge || "IRIS");
  }

  function tick(){
    const pet = petEl();
    if (!pet) return requestAnimationFrame(tick);
    if (Math.hypot(state.tx - state.x, state.ty - state.y) < 12 || Math.random() < 0.003) {
      const t = computeTarget();
      state.tx = t.x; state.ty = t.y;
      applyMood(t.mood, t.badge);
    }
    const dx = state.tx - state.x;
    const dy = state.ty - state.y;
    const dist = Math.hypot(dx, dy);
    if (dist > 1) {
      const speed = Math.max(1.3, Math.min(4.2, dist * 0.06));
      state.x += dx / dist * speed;
      state.y += dy / dist * speed;
      pet.style.left = `${state.x}px`;
      pet.style.top = `${state.y}px`;
      pet.style.transform = `scaleX(${dx < 0 ? -1 : 1})`;
    }
    const now = performance.now();
    if (now - state.lastBlink > 2600 + Math.random() * 2800) {
      pet.classList.add("blink");
      state.lastBlink = now;
      setTimeout(() => pet.classList.remove("blink"), 220);
    }
    requestAnimationFrame(tick);
  }

  function findExistingChat(){
    const candidates = qsa("section, article, div").filter(el => {
      const t = txt(el);
      return t.includes("parler à iris") || t.includes("écris à iris");
    });
    return candidates.sort((a,b) => (a.textContent.length - b.textContent.length))[0] || null;
  }

  function compactChat(){
    const chat = findExistingChat();
    if (!chat) return;
    chat.classList.add("iris-v35-chat-dock");
  }

  function installSceneBindings(){
    const sceneMap = [
      ["libre", "libre"],
      ["bureau", "bureau"],
      ["travail", "travail"],
      ["recherche", "recherche"],
      ["repos", "repos"],
      ["dock chat", "dock"]
    ];
    sceneMap.forEach(([needle, scene]) => {
      const btn = byText(needle);
      if (btn && !btn.dataset.irisV35Bound) {
        btn.dataset.irisV35Bound = "1";
        btn.addEventListener("click", () => {
          state.scene = scene;
          localStorage.setItem("iris_v35_scene", scene);
          const t = computeTarget();
          state.tx = t.x; state.ty = t.y;
          applyMood(t.mood, t.badge);
        });
      }
    });
  }

  function installModeBindings(){
    const modes = ["on","off","normal","travail","veille légère","autopilot"];
    modes.forEach(m => {
      const btn = byText(m);
      if (btn && !btn.dataset.irisModeBound) {
        btn.dataset.irisModeBound = "1";
        btn.addEventListener("click", () => {
          state.mode = m.includes("veille") ? "light" : (m === "on" || m === "off" ? m.toUpperCase() : m);
          const pet = petEl();
          pet?.classList.remove("sleeping","working","researching","talking","hovering");
          if (m === "travail") pet?.classList.add("working");
          if (m.includes("veille")) pet?.classList.add("researching");
          if (m === "off") pet?.classList.add("sleeping");
        });
      }
    });
  }

  async function fetchJSON(url){
    const r = await fetch(url, {cache:"no-store"});
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  }

  async function refreshState(){
    try {
      const data = await fetchJSON("/api/state");
      state.mode = data?.summary?.mode || data?.mode || state.mode;
      state.currentSite = data?.summary?.watch_current || data?.watch_current || "";
    } catch(_) {}
    try {
      const wr = await fetchJSON("/api/watch-radar");
      state.currentSite = wr?.current_site || wr?.watch?.current_site || state.currentSite || "";
    } catch(_) {}
  }

  function bindMouse(){
    window.addEventListener("mousemove", (e) => {
      state.mouseX = e.clientX;
      state.mouseY = e.clientY;
      const pet = petEl();
      if (!pet) return;
      const d = Math.hypot(state.x - state.mouseX, state.y - state.mouseY);
      if (d < 110 && state.scene === "libre") {
        pet.classList.add("hovering");
        setBadge("hey");
        clearTimeout(window.__irisHoverTo);
        window.__irisHoverTo = setTimeout(() => {
          if (state.scene === "libre") pet.classList.remove("hovering");
        }, 900);
      }
    });
  }

  function hookChatLocalAssistant(){
    const panels = qsa("section, article, div").filter(el => txt(el).includes("parler à iris"));
    const panel = panels[0];
    if (!panel) return;
    const input = qsa("input, textarea", panel).find(Boolean) || qsa("input, textarea").find(el => (el.placeholder||"").toLowerCase().includes("iris"));
    const sendBtn = qsa("button", panel).slice(-1)[0];
    const micBtn = qsa("button", panel).slice(-2)[0];
    const bubbles = qsa("p,div", panel);
    let answer = bubbles.find(el => txt(el).includes("salut")) || null;

    const speak = (text) => {
      if (!window.speechSynthesis) return;
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "fr-FR";
      u.rate = 1.0;
      window.speechSynthesis.speak(u);
    };

    const respond = (q) => {
      const qq = (q || "").toLowerCase();
      let res = "Je suis là.";
      if (qq.includes("que fais") || qq.includes("quoi fais")) {
        res = state.currentSite ? `Je surveille actuellement ${state.currentSite}.` : "Je surveille les agents et la veille en cours.";
      } else if (qq.includes("résume") && qq.includes("veille")) {
        res = state.currentSite ? `Veille active : ${state.currentSite}.` : "La veille est active.";
      } else if (qq.includes("mode travail")) {
        byText("travail")?.click();
        res = "Je passe en mode travail.";
      } else if (qq.includes("mode veille")) {
        byText("veille légère")?.click();
        res = "Je passe en veille légère.";
      } else if (qq.includes("autopilot")) {
        byText("autopilot")?.click();
        res = "Je passe en autopilot.";
      } else if (qq.includes("ouvre obsidian")) {
        byText("ouvrir obsidian")?.click();
        res = "J'ouvre Obsidian.";
      } else if (qq.includes("bonjour") || qq.includes("salut")) {
        res = "Salut. Je suis IRIS. Prêt pour la suite.";
      }
      if (answer) answer.textContent = res;
      speak(res);
      const pet = petEl();
      pet?.classList.add("talking");
      setBadge("parle");
      setTimeout(() => pet?.classList.remove("talking"), 1600);
    };

    if (sendBtn && input && !sendBtn.dataset.irisLocalChat) {
      sendBtn.dataset.irisLocalChat = "1";
      sendBtn.addEventListener("click", () => respond(input.value));
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          respond(input.value);
        }
      });
    }

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (micBtn && input && SR && !micBtn.dataset.irisMicBound) {
      micBtn.dataset.irisMicBound = "1";
      const rec = new SR();
      rec.lang = "fr-FR";
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      micBtn.addEventListener("click", () => {
        state.listening = true;
        petEl()?.classList.add("listening");
        setBadge("j'écoute");
        try { rec.start(); } catch(_) {}
      });
      rec.onresult = (ev) => {
        const text = ev.results?.[0]?.[0]?.transcript || "";
        input.value = text;
        respond(text);
      };
      rec.onend = () => {
        state.listening = false;
        petEl()?.classList.remove("listening");
      };
    }
  }

  function hideOldFloatingMascot(){
    qsa("img, svg, canvas, div").forEach(el => {
      const t = (el.className || "") + " " + (el.id || "");
      const style = getComputedStyle(el);
      if (/companion|pet|mascot|orb/i.test(t) && style.position === "fixed" && el !== qs("#iris-v35-pet")) {
        el.style.opacity = "0";
        el.style.pointerEvents = "none";
      }
    });
  }

  function init(){
    createPet();
    compactChat();
    installSceneBindings();
    installModeBindings();
    bindMouse();
    hookChatLocalAssistant();
    hideOldFloatingMascot();
    refreshState();
    setInterval(refreshState, 18000);
    setInterval(installSceneBindings, 2500);
    setInterval(compactChat, 3000);
    const t = computeTarget();
    state.tx = t.x; state.ty = t.y;
    state.x = t.x; state.y = t.y;
    const pet = petEl();
    pet.style.left = `${state.x}px`;
    pet.style.top = `${state.y}px`;
    applyMood(t.mood, t.badge);
    tick();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
