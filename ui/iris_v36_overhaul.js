(() => {
  const qs = (s, r=document) => r.querySelector(s);
  const qsa = (s, r=document) => Array.from(r.querySelectorAll(s));
  const text = el => ((el?.textContent || '').replace(/\s+/g,' ').trim());
  const lower = el => text(el).toLowerCase();

  const state = {
    scene: localStorage.getItem('iris_v36_scene') || 'libre',
    mode: localStorage.getItem('iris_v36_mode') || 'autopilot',
    x: 0,
    y: 0,
    tx: 0,
    ty: 0,
    lastMoveAt: 0,
    moving: false,
    facing: 1,
    currentSite: '',
    chatCollapsed: localStorage.getItem('iris_v36_chat_collapsed') === '1',
    mouseX: window.innerWidth * .7,
    mouseY: window.innerHeight * .6,
    siteWatchMissingRequests: false
  };

  function findButton(label){
    return qsa('button,a').find(el => lower(el).includes(label.toLowerCase()));
  }

  function findHeadingBox(needle){
    const heads = qsa('h1,h2,h3,h4,strong');
    const h = heads.find(el => lower(el).includes(needle.toLowerCase()));
    const box = h?.closest('section,article,div,aside');
    return box?.getBoundingClientRect() || null;
  }

  function createPet(){
    if (qs('#iris-v36-layer')) return;
    const layer = document.createElement('div');
    layer.id = 'iris-v36-layer';
    layer.innerHTML = `
      <div id="iris-v36-pet" class="walk show-badge">
        <div class="badge">IRIS</div>
        <div class="iris-v36-wrap">
          <div class="shadow"></div>
          <div class="tail"></div>
          <div class="ear left"></div>
          <div class="ear right"></div>
          <div class="antenna"></div>
          <div class="head"></div>
          <div class="face"></div>
          <div class="eye left"></div>
          <div class="eye right"></div>
          <div class="eye-shine left"></div>
          <div class="eye-shine right"></div>
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

  function pet(){
    return qs('#iris-v36-pet');
  }

  function setPetMode(mode, badge='IRIS'){
    const p = pet();
    if (!p) return;
    p.className = mode + ' show-badge';
    const b = qs('.badge', p);
    if (b) b.textContent = badge;
  }

  function hideOldMascots(){
    qsa('img,svg,canvas,div').forEach(el => {
      const name = `${el.id||''} ${typeof el.className === 'string' ? el.className : ''}`;
      const style = getComputedStyle(el);
      if (
        el !== pet() &&
        /companion|mascot|pet|orb/i.test(name) &&
        style.position === 'fixed'
      ) {
        el.style.opacity = '0';
        el.style.pointerEvents = 'none';
      }
    });
  }

  function findChatPanel(){
    const headings = qsa('h1,h2,h3,h4,strong').filter(el => lower(el).includes('parler à iris'));
    for (const h of headings) {
      const box = h.closest('section,article,div,aside');
      if (box) return box;
    }
    return null;
  }

  function createChatHeader(panel){
    if (qs('.iris-v36-chat-head', panel)) return;
    const head = document.createElement('div');
    head.className = 'iris-v36-chat-head';
    head.innerHTML = `
      <strong>Parler à IRIS</strong>
      <div class="iris-v36-head-right">
        <button class="iris-v36-mini-btn" type="button" title="Parler">🎙</button>
        <button class="iris-v36-mini-btn iris-v36-toggle" type="button" title="Réduire">—</button>
      </div>
    `;
    panel.prepend(head);
  }

  function dockChat(){
    const panel = findChatPanel();
    if (!panel) return;
    panel.classList.add('iris-v36-chat-dock');
    createChatHeader(panel);

    if (state.chatCollapsed) panel.classList.add('iris-v36-collapsed');
    else panel.classList.remove('iris-v36-collapsed');

    const toggle = qs('.iris-v36-toggle', panel);
    if (toggle && !toggle.dataset.bound36) {
      toggle.dataset.bound36 = '1';
      toggle.addEventListener('click', () => {
        state.chatCollapsed = !state.chatCollapsed;
        localStorage.setItem('iris_v36_chat_collapsed', state.chatCollapsed ? '1' : '0');
        panel.classList.toggle('iris-v36-collapsed', state.chatCollapsed);
      });
    }

    const topTalkBtn = qsa('button').find(el => lower(el) === 'parler à iris');
    if (topTalkBtn && !topTalkBtn.dataset.bound36) {
      topTalkBtn.dataset.bound36 = '1';
      topTalkBtn.addEventListener('click', () => {
        state.chatCollapsed = false;
        localStorage.setItem('iris_v36_chat_collapsed', '0');
        panel.classList.remove('iris-v36-collapsed');
      });
    }
  }

  function markActiveButtons(){
    qsa('.iris-v36-mode-active,.iris-v36-scene-active').forEach(el => {
      el.classList.remove('iris-v36-mode-active','iris-v36-scene-active');
    });

    const modeMap = [
      ['on','ON'],
      ['off','OFF'],
      ['normal','normal'],
      ['travail','travail'],
      ['veille légère','light'],
      ['autopilot','autopilot']
    ];
    modeMap.forEach(([needle,val]) => {
      const btn = findButton(needle);
      if (btn && state.mode === val) btn.classList.add('iris-v36-mode-active');
    });

    const sceneMap = [
      ['libre','libre'],
      ['bureau','bureau'],
      ['travail','travail'],
      ['recherche','recherche'],
      ['repos','repos'],
      ['dock chat','dock']
    ];
    sceneMap.forEach(([needle,val]) => {
      const btn = findButton(needle);
      if (btn && state.scene === val) btn.classList.add('iris-v36-scene-active');
    });
  }

  function bindModeButtons(){
    [
      ['on','ON'],
      ['off','OFF'],
      ['normal','normal'],
      ['travail','travail'],
      ['veille légère','light'],
      ['autopilot','autopilot']
    ].forEach(([needle,val]) => {
      const btn = findButton(needle);
      if (btn && !btn.dataset.mode36) {
        btn.dataset.mode36 = '1';
        btn.addEventListener('click', () => {
          state.mode = val;
          localStorage.setItem('iris_v36_mode', val);
          markActiveButtons();
          if (val === 'OFF') setPetMode('sleep', 'repos');
          else if (val === 'travail') setPetMode('work', 'travail');
          else if (val === 'light') setPetMode('research', 'veille');
          else setPetMode('walk', 'IRIS');
        });
      }
    });
  }

  function bindSceneButtons(){
    [
      ['libre','libre'],
      ['bureau','bureau'],
      ['travail','travail'],
      ['recherche','recherche'],
      ['repos','repos'],
      ['dock chat','dock']
    ].forEach(([needle,val]) => {
      const btn = findButton(needle);
      if (btn && !btn.dataset.scene36) {
        btn.dataset.scene36 = '1';
        btn.addEventListener('click', () => {
          state.scene = val;
          localStorage.setItem('iris_v36_scene', val);
          markActiveButtons();
          pickTarget(true);
        });
      }
    });
  }

  function cleanupCards(){
    const cards = qsa('section,article,div').filter(el => {
      const t = lower(el);
      return t.includes('watchdog') || t.includes('site watch') || t.includes('agent observe');
    });

    cards.forEach(card => {
      const t = text(card);
      if (/Site Watch/i.test(t) && /ModuleNotFoundError: No module named 'requests'/i.test(t)) {
        state.siteWatchMissingRequests = true;
        const nodes = qsa('*', card).filter(n => /ModuleNotFoundError: No module named 'requests'/i.test(text(n)));
        nodes.forEach(n => n.textContent = 'n/a');
      }
      if (/Agent Observe/i.test(t)) {
        const nodes = qsa('*', card).filter(n => /^"services_ok":\s*\d+/i.test(text(n)));
        nodes.forEach(n => n.textContent = 'STATE_OK');
      }
    });
  }

  function bounds(){
    const w = window.innerWidth;
    const h = window.innerHeight;
    const sidebar = qsa('aside,nav,section,div').find(el => {
      const r = el.getBoundingClientRect();
      return r.left < 40 && r.width > 180 && r.height > h * .5;
    });
    const sidebarW = sidebar ? sidebar.getBoundingClientRect().width : 280;

    const chat = findChatPanel();
    const chatRect = chat?.getBoundingClientRect();

    let left = sidebarW + 40;
    let top = 110;
    let right = w - 90;
    let bottom = h - 90;

    if (chatRect && !state.chatCollapsed && state.scene !== 'dock') {
      right = Math.min(right, chatRect.left - 40);
    }

    return {left, top, right, bottom};
  }

  function random(min,max){
    return min + Math.random() * (max - min);
  }

  function computeTarget(){
    const b = bounds();
    const chat = findChatPanel();
    const chatRect = chat?.getBoundingClientRect();

    if (state.scene === 'dock' && chatRect) {
      return {x: chatRect.left + 40, y: chatRect.top - 128, mode:'wave', badge:'chat'};
    }

    if (state.scene === 'repos') {
      return {
        x: (b.left + b.right) * .5,
        y: b.bottom - 20,
        mode:'sleep',
        badge:'repos'
      };
    }

    if (state.scene === 'travail') {
      const zone = findHeadingBox('agents live') || findHeadingBox('modes système');
      if (zone) {
        return {
          x: Math.min(zone.right - 150, b.right - 10),
          y: zone.top + 20,
          mode:'work',
          badge:'travail'
        };
      }
    }

    if (state.scene === 'recherche') {
      const zone = findHeadingBox('watch radar') || findHeadingBox('veille active') || findHeadingBox('timeline');
      if (zone) {
        return {
          x: Math.min(zone.right - 150, b.right - 10),
          y: zone.top + 16,
          mode:'research',
          badge:'scan'
        };
      }
    }

    if (state.scene === 'bureau') {
      return {
        x: b.left + 40,
        y: b.bottom - 18,
        mode:'work',
        badge:'bureau'
      };
    }

    const d = Math.hypot(state.mouseX - state.x, state.mouseY - state.y);
    if (d < 110) {
      return {
        x: Math.max(b.left, Math.min(b.right, state.mouseX + 44)),
        y: Math.max(b.top, Math.min(b.bottom, state.mouseY - 16)),
        mode:'wave',
        badge:'hey'
      };
    }

    return {
      x: random(b.left, b.right),
      y: random(b.top + 40, b.bottom),
      mode:'walk',
      badge: state.mode === 'light' ? 'veille' : 'IRIS'
    };
  }

  function pickTarget(force=false){
    const now = performance.now();
    if (!force && now - state.lastMoveAt < 1800) return;
    const t = computeTarget();
    state.tx = t.x;
    state.ty = t.y;
    state.lastMoveAt = now;
    setPetMode(t.mode, t.badge);
  }

  function animate(){
    const p = pet();
    if (!p) return requestAnimationFrame(animate);

    const dx = state.tx - state.x;
    const dy = state.ty - state.y;
    const dist = Math.hypot(dx, dy);

    if (dist > 2) {
      state.moving = true;
      const speed = Math.max(1.5, Math.min(4.6, dist * 0.055));
      state.x += dx / dist * speed;
      state.y += dy / dist * speed;
      if (dx !== 0) state.facing = dx >= 0 ? 1 : -1;
      if (!/sleep|work|research|wave/.test(p.className)) setPetMode('walk', 'IRIS');
    } else {
      state.moving = false;
      if (state.scene === 'libre' && Math.random() < 0.008) pickTarget(true);
    }

    const t = performance.now() * 0.01;
    const hop = state.moving ? Math.abs(Math.sin(t * 1.7)) * 8 : Math.abs(Math.sin(t * .7)) * 2;
    p.style.transform = `translate(${state.x}px, ${state.y - hop}px) scaleX(${state.facing})`;

    if (Math.random() < 0.003) {
      p.classList.add('blink');
      setTimeout(() => p.classList.remove('blink'), 180);
    }

    requestAnimationFrame(animate);
  }

  function bindMouse(){
    window.addEventListener('mousemove', (e) => {
      state.mouseX = e.clientX;
      state.mouseY = e.clientY;
      const d = Math.hypot(state.mouseX - state.x, state.mouseY - state.y);
      if (state.scene === 'libre' && d < 120) {
        setPetMode('wave', 'coucou');
        setTimeout(() => {
          if (state.scene === 'libre') setPetMode('walk', 'IRIS');
        }, 900);
      }
    });
  }

  async function fetchJson(url){
    const res = await fetch(url, {cache:'no-store'});
    if (!res.ok) throw new Error(`${res.status}`);
    return await res.json();
  }

  async function refreshData(){
    try {
      const s = await fetchJson('/api/state');
      const summary = s.summary || s;
      state.mode = summary.mode || state.mode;
      state.currentSite = summary.watch_current || '';
      localStorage.setItem('iris_v36_mode', state.mode);
      markActiveButtons();
    } catch(_) {}
    try {
      const wr = await fetchJson('/api/watch-radar');
      state.currentSite = wr.current_site || wr.watch?.current_site || state.currentSite || '';
    } catch(_) {}
  }

  function speak(textToSpeak){
    if (!window.speechSynthesis) return;
    try {
      const u = new SpeechSynthesisUtterance(textToSpeak);
      u.lang = 'fr-FR';
      u.rate = 1.02;
      u.pitch = 1.02;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    } catch(_) {}
  }

  function bindLocalChat(){
    const panel = findChatPanel();
    if (!panel) return;

    const input = qs('input,textarea', panel);
    const allButtons = qsa('button', panel);
    const sendBtn = allButtons[allButtons.length - 1];
    const micBtn = allButtons.find(b => /🎙|mic|voice|parler/i.test(text(b) + ' ' + (b.title||''))) || allButtons[allButtons.length - 2];

    let answerNode = qsa('div,p', panel).find(el => /salut|je peux|prêt/i.test(text(el)));
    if (!answerNode) {
      answerNode = document.createElement('div');
      answerNode.style.margin = '10px 0 14px';
      answerNode.style.padding = '14px 16px';
      answerNode.style.borderRadius = '18px';
      answerNode.style.background = 'rgba(255,255,255,.04)';
      answerNode.textContent = 'Salut. Je suis IRIS.';
      panel.appendChild(answerNode);
    }

    function answer(q){
      const msg = (q || '').trim();
      const l = msg.toLowerCase();
      let res = 'Je suis là.';

      if (!msg) return;

      if (l.includes('que fais') || l.includes('quoi fais')) {
        res = state.currentSite ? `Je surveille actuellement ${state.currentSite}.` : 'Je surveille les agents et la veille.';
      } else if (l.includes('résume') && l.includes('veille')) {
        res = state.currentSite ? `Veille active sur ${state.currentSite}.` : 'La veille est active.';
      } else if (l.includes('mode travail')) {
        findButton('travail')?.click();
        res = 'Je passe en mode travail.';
      } else if (l.includes('mode veille')) {
        findButton('veille légère')?.click();
        res = 'Je passe en veille légère.';
      } else if (l.includes('autopilot')) {
        findButton('autopilot')?.click();
        res = 'Je repasse en autopilot.';
      } else if (l.includes('ouvre obsidian')) {
        findButton('ouvrir obsidian')?.click();
        res = 'J’ouvre Obsidian.';
      } else if (l.includes('ouvre webui')) {
        findButton('ouvrir webui')?.click();
        res = 'J’ouvre WebUI.';
      } else if (l.includes('ouvre n8n')) {
        findButton('ouvrir n8n')?.click();
        res = 'J’ouvre n8n.';
      } else if (l.includes('bonjour') || l.includes('salut')) {
        res = 'Salut. Je suis IRIS. Prêt pour la suite.';
      }

      answerNode.textContent = res;
      setPetMode('wave', 'parle');
      setTimeout(() => {
        if (state.scene === 'recherche') setPetMode('research', 'scan');
        else if (state.scene === 'travail') setPetMode('work', 'travail');
        else if (state.scene === 'repos') setPetMode('sleep', 'repos');
        else setPetMode('walk', 'IRIS');
      }, 1200);

      speak(res);
    }

    if (sendBtn && input && !sendBtn.dataset.iris36send) {
      sendBtn.dataset.iris36send = '1';
      sendBtn.addEventListener('click', () => answer(input.value));
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          answer(input.value);
        }
      });
    }

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (micBtn && input && SR && !micBtn.dataset.iris36mic) {
      micBtn.dataset.iris36mic = '1';
      const rec = new SR();
      rec.lang = 'fr-FR';
      rec.interimResults = false;
      rec.maxAlternatives = 1;

      micBtn.addEventListener('click', () => {
        try {
          rec.start();
          setPetMode('wave', 'écoute');
        } catch(_) {}
      });
      rec.onresult = (ev) => {
        const transcript = ev.results?.[0]?.[0]?.transcript || '';
        input.value = transcript;
        answer(transcript);
      };
      rec.onend = () => {
        if (state.scene === 'libre') setPetMode('walk', 'IRIS');
      };
    }
  }

  function initPosition(){
    const b = bounds();
    state.x = Math.min(b.right, Math.max(b.left, window.innerWidth - 240));
    state.y = Math.min(b.bottom, Math.max(b.top, window.innerHeight - 220));
    state.tx = state.x;
    state.ty = state.y;
  }

  function init(){
    createPet();
    initPosition();
    dockChat();
    bindModeButtons();
    bindSceneButtons();
    markActiveButtons();
    bindMouse();
    cleanupCards();
    bindLocalChat();
    hideOldMascots();
    refreshData();
    pickTarget(true);
    animate();

    setInterval(() => {
      dockChat();
      bindModeButtons();
      bindSceneButtons();
      bindLocalChat();
      cleanupCards();
      markActiveButtons();
    }, 2500);

    setInterval(() => {
      refreshData();
      if (state.scene === 'libre') pickTarget(true);
      else pickTarget(false);
    }, 5000);

    window.addEventListener('resize', () => {
      pickTarget(true);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
