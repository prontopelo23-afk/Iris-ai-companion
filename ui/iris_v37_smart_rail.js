(() => {
  const qs = (s, r=document) => r.querySelector(s);
  const qsa = (s, r=document) => Array.from(r.querySelectorAll(s));
  const txt = el => ((el?.textContent || '').replace(/\s+/g,' ').trim());
  const low = el => txt(el).toLowerCase();

  const state = {
    scene: localStorage.getItem('iris_v37_scene') || 'libre',
    mode: localStorage.getItem('iris_v37_mode') || 'autopilot',
    x: 0,
    y: 0,
    tx: 0,
    ty: 0,
    facing: 1,
    anchorIndex: 0,
    currentSite: '',
    chatOpen: false,
    mouseX: innerWidth * 0.7,
    mouseY: innerHeight * 0.6,
    bubbleTimer: null
  };

  function findButton(label){
    return qsa('button,a').find(el => low(el) === label.toLowerCase() || low(el).includes(label.toLowerCase()));
  }

  function headingRect(name){
    const h = qsa('h1,h2,h3,h4,strong,div').find(el => low(el) === name.toLowerCase() || low(el).includes(name.toLowerCase()));
    return h?.getBoundingClientRect() || null;
  }

  function sectionRect(name){
    const h = qsa('h1,h2,h3,h4,strong').find(el => low(el).includes(name.toLowerCase()));
    return h?.closest('section,article,div,aside')?.getBoundingClientRect() || null;
  }

  function clamp(v, min, max){
    return Math.max(min, Math.min(max, v));
  }

  function removeLegacy(){
    qs('#iris-v36-layer')?.remove();
    qsa('[id*="v36"]').forEach(el => {
      if (el.id !== 'iris-v37-layer') el.remove();
    });
  }

  function createPet(){
    if (qs('#iris-v37-layer')) return;
    const layer = document.createElement('div');
    layer.id = 'iris-v37-layer';
    layer.innerHTML = `
      <div id="iris-v37-pet" class="walk">
        <div class="w">
          <div class="shadow"></div>
          <div class="tail"></div>
          <div class="ear l"></div>
          <div class="ear r"></div>
          <div class="antenna"></div>
          <div class="head"></div>
          <div class="visor"></div>
          <div class="eye l"></div>
          <div class="eye r"></div>
          <div class="mouth"></div>
          <div class="body"></div>
          <div class="belly"></div>
          <div class="arm l"><div class="hand"></div></div>
          <div class="arm r"><div class="hand"></div></div>
          <div class="leg l"><div class="foot"></div></div>
          <div class="leg r"><div class="foot"></div></div>
        </div>
      </div>
      <div id="iris-v37-bubble"></div>
    `;
    document.body.appendChild(layer);
  }

  function pet(){ return qs('#iris-v37-pet'); }
  function bubble(){ return qs('#iris-v37-bubble'); }

  function setPose(pose){
    const p = pet();
    if (!p) return;
    p.className = pose;
  }

  function showBubble(message, ms=1500){
    const b = bubble();
    if (!b) return;
    b.textContent = message;
    b.classList.add('show');
    clearTimeout(state.bubbleTimer);
    state.bubbleTimer = setTimeout(() => b.classList.remove('show'), ms);
  }

  function chatPanel(){
    const h = qsa('h1,h2,h3,h4,strong').find(el => low(el).includes('parler à iris'));
    return h?.closest('section,article,div,aside') || null;
  }

  function dockChat(){
    const panel = chatPanel();
    if (!panel) return;
    panel.classList.add('iris-v37-chat-dock');
    panel.classList.toggle('iris-v37-open', state.chatOpen);

    if (!qs('.iris-v37-chat-head', panel)) {
      const head = document.createElement('div');
      head.className = 'iris-v37-chat-head';
      head.innerHTML = `
        <strong>Parler à IRIS</strong>
        <div class="iris-v37-chat-right">
          <button class="iris-v37-mini-btn iris-v37-mic" type="button">🎙</button>
          <button class="iris-v37-mini-btn iris-v37-toggle" type="button">—</button>
        </div>
      `;
      panel.prepend(head);
    }

    const toggle = qs('.iris-v37-toggle', panel);
    if (toggle && !toggle.dataset.bound37) {
      toggle.dataset.bound37 = '1';
      toggle.addEventListener('click', () => {
        state.chatOpen = !state.chatOpen;
        panel.classList.toggle('iris-v37-open', state.chatOpen);
      });
    }

    const topBtn = findButton('parler à iris');
    if (topBtn && !topBtn.dataset.bound37) {
      topBtn.dataset.bound37 = '1';
      topBtn.addEventListener('click', () => {
        state.chatOpen = true;
        panel.classList.add('iris-v37-open');
      });
    }
  }

  function bounds(){
    const sidebar = qsa('aside,nav,section,div').find(el => {
      const r = el.getBoundingClientRect();
      return r.left < 40 && r.width > 180 && r.height > innerHeight * .5;
    });
    const side = sidebar ? sidebar.getBoundingClientRect().width : 290;
    return {
      left: side + 24,
      top: 90,
      right: innerWidth - 26,
      bottom: innerHeight - 18
    };
  }

  function railPoints(){
    const b = bounds();
    const hero = sectionRect('mission control') || sectionRect('iris v3 companion');
    const agents = sectionRect('agents live');
    const watch = sectionRect('watch radar');
    const time = sectionRect('timeline');
    const mesh = sectionRect('service mesh');
    const deep = sectionRect('deep log');
    const panel = chatPanel();
    const chat = panel?.getBoundingClientRect();

    const pts = [];

    function add(x,y,pose='walk'){
      pts.push({
        x: clamp(x, b.left + 10, b.right - 100),
        y: clamp(y, b.top + 10, b.bottom - 94),
        pose
      });
    }

    if (hero) {
      add(hero.right - 120, hero.top + 18, 'wave');
      add(hero.right - 120, hero.bottom - 92, 'sit');
    }
    if (agents) {
      add(agents.right - 118, agents.top + 22, 'sit');
      add(agents.right - 118, agents.bottom - 96, 'sit');
    }
    if (watch) {
      add(watch.left + 36, watch.bottom - 88, 'sit');
      add(watch.right - 118, watch.top + 24, 'research');
    }
    if (time) {
      add(time.right - 118, time.bottom - 90, 'sit');
    }
    if (mesh) {
      add(mesh.right - 118, mesh.top + 28, 'sit');
    }
    if (deep) {
      add(deep.right - 118, deep.top + 24, 'sit');
    }

    add(b.right - 116, b.top + 24, 'wave');
    add(b.right - 116, b.bottom - 170, 'sit');

    if (chat) {
      add(chat.left - 102, chat.top - 42, 'sit');
    }

    return pts;
  }

  function computeTarget(force=false){
    const b = bounds();
    const chat = chatPanel()?.getBoundingClientRect();
    const watch = sectionRect('watch radar');
    const agents = sectionRect('agents live');

    if (state.scene === 'dock' && chat) {
      return {x: chat.left + 18, y: chat.top - 12, pose:'wave'};
    }
    if (state.scene === 'repos') {
      return {x: b.right - 140, y: b.bottom - 138, pose:'sleep'};
    }
    if (state.scene === 'travail' && agents) {
      return {x: agents.right - 118, y: agents.top + 22, pose:'work'};
    }
    if (state.scene === 'recherche' && watch) {
      return {x: watch.right - 118, y: watch.top + 22, pose:'research'};
    }
    if (state.scene === 'bureau') {
      return {x: b.left + 30, y: b.bottom - 140, pose:'work'};
    }

    const rails = railPoints();
    if (!rails.length) {
      return {x:b.right - 120, y:b.bottom - 150, pose:'sit'};
    }

    state.anchorIndex = (state.anchorIndex + 1) % rails.length;
    return rails[state.anchorIndex];
  }

  function placeBubble(){
    const p = pet();
    const b = bubble();
    if (!p || !b) return;
    const r = p.getBoundingClientRect();
    b.style.left = `${r.left - 2}px`;
    b.style.top = `${r.top - 34}px`;
  }

  function animate(){
    const p = pet();
    if (!p) return requestAnimationFrame(animate);

    const dx = state.tx - state.x;
    const dy = state.ty - state.y;
    const dist = Math.hypot(dx, dy);

    if (dist > 1.5) {
      const speed = Math.max(1.3, Math.min(3.8, dist * 0.06));
      state.x += dx / dist * speed;
      state.y += dy / dist * speed;
      if (Math.abs(dx) > 0.3) state.facing = dx >= 0 ? 1 : -1;
      if (!/sleep|work|research|wave/.test(p.className)) setPose('walk');
    }

    const hop = dist > 1.5 ? Math.abs(Math.sin(Date.now() * 0.018)) * 5 : Math.abs(Math.sin(Date.now() * 0.006)) * 1.4;
    p.style.transform = `translate(${state.x}px, ${state.y - hop}px) scaleX(${state.facing})`;

    if (Math.random() < 0.0024) {
      p.classList.add('blink');
      setTimeout(() => p.classList.remove('blink'), 160);
    }

    placeBubble();
    requestAnimationFrame(animate);
  }

  function goToNext(force=false){
    const t = computeTarget(force);
    state.tx = t.x;
    state.ty = t.y;
    setPose(t.pose || 'walk');
  }

  function bindMouse(){
    window.addEventListener('mousemove', (e) => {
      state.mouseX = e.clientX;
      state.mouseY = e.clientY;
      const d = Math.hypot(e.clientX - state.x, e.clientY - state.y);
      if (d < 90) {
        setPose('wave');
        showBubble('Oui ?', 900);
      }
    });
  }

  function markActive(){
    qsa('.iris-v36-mode-active,.iris-v36-scene-active').forEach(el => {
      el.classList.remove('iris-v36-mode-active','iris-v36-scene-active');
    });
  }

  function bindModes(){
    [
      ['on','ON'],
      ['off','OFF'],
      ['normal','normal'],
      ['travail','travail'],
      ['veille légère','light'],
      ['autopilot','autopilot']
    ].forEach(([needle,val]) => {
      const btn = findButton(needle);
      if (btn && !btn.dataset.mode37) {
        btn.dataset.mode37 = '1';
        btn.addEventListener('click', () => {
          state.mode = val;
          localStorage.setItem('iris_v37_mode', val);
          if (val === 'OFF') {
            state.scene = 'repos';
            setPose('sleep');
          } else if (val === 'travail') {
            state.scene = 'travail';
            setPose('work');
          } else if (val === 'light') {
            state.scene = 'recherche';
            setPose('research');
          } else if (state.scene === 'repos') {
            state.scene = 'libre';
          }
          goToNext(true);
        });
      }
    });
  }

  function bindScenes(){
    [
      ['libre','libre'],
      ['bureau','bureau'],
      ['travail','travail'],
      ['recherche','recherche'],
      ['repos','repos'],
      ['dock chat','dock']
    ].forEach(([needle,val]) => {
      const btn = findButton(needle);
      if (btn && !btn.dataset.scene37) {
        btn.dataset.scene37 = '1';
        btn.addEventListener('click', () => {
          state.scene = val;
          localStorage.setItem('iris_v37_scene', val);
          if (val === 'repos') setPose('sleep');
          else if (val === 'travail') setPose('work');
          else if (val === 'recherche') setPose('research');
          else setPose('walk');
          goToNext(true);
        });
      }
    });
  }

  async function refreshState(){
    try {
      const res = await fetch('/api/state', {cache:'no-store'});
      if (!res.ok) return;
      const data = await res.json();
      const s = data.summary || data;
      state.currentSite = s.watch_current || '';
    } catch(e) {}
  }

  function cleanSignals(){
    qsa('section,article,div').forEach(el => {
      const t = txt(el);
      if (/ModuleNotFoundError: No module named 'requests'/.test(t)) {
        qsa('*', el).forEach(n => {
          if (/ModuleNotFoundError: No module named 'requests'/.test(txt(n))) n.textContent = 'n/a';
        });
      }
      if (/^"services_ok":\s*\d+/.test(t)) {
        qsa('*', el).forEach(n => {
          if (/^"services_ok":\s*\d+/.test(txt(n))) n.textContent = 'STATE_OK';
        });
      }
    });
  }

  function bindLocalAssistant(){
    const panel = chatPanel();
    if (!panel) return;
    const input = qs('input,textarea', panel);
    const sendBtn = qsa('button', panel).slice(-1)[0];
    const micBtn = qs('.iris-v37-mic', panel);

    let answerNode = qsa('div,p', panel).find(el => /salut|je suis iris|prêt/i.test(txt(el)));
    if (!answerNode) {
      answerNode = document.createElement('div');
      answerNode.style.margin = '10px 0 14px';
      answerNode.style.padding = '12px 14px';
      answerNode.style.borderRadius = '16px';
      answerNode.style.background = 'rgba(255,255,255,.04)';
      answerNode.textContent = 'Salut. Je suis IRIS.';
      panel.appendChild(answerNode);
    }

    const speak = msg => {
      if (!window.speechSynthesis) return;
      try{
        const u = new SpeechSynthesisUtterance(msg);
        u.lang = 'fr-FR';
        u.rate = 1.02;
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(u);
      }catch(e){}
    };

    function answer(msg){
      const q = (msg || '').trim();
      if (!q) return;
      const l = q.toLowerCase();
      let res = 'Je suis là.';

      if (l.includes('que fais') || l.includes('quoi fais')) {
        res = state.currentSite ? `Je surveille actuellement ${state.currentSite}.` : 'Je surveille les agents.';
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
      } else if (l.includes('salut') || l.includes('bonjour')) {
        res = 'Salut. Je suis IRIS. Prêt.';
      }

      answerNode.textContent = res;
      showBubble('ok', 700);
      setPose('wave');
      setTimeout(() => goToNext(true), 900);
      speak(res);
    }

    if (sendBtn && input && !sendBtn.dataset.send37) {
      sendBtn.dataset.send37 = '1';
      sendBtn.addEventListener('click', () => answer(input.value));
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          answer(input.value);
        }
      });
    }

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (micBtn && input && SR && !micBtn.dataset.mic37) {
      micBtn.dataset.mic37 = '1';
      const rec = new SR();
      rec.lang = 'fr-FR';
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      micBtn.addEventListener('click', () => {
        try {
          rec.start();
          showBubble('j’écoute', 1200);
          setPose('wave');
          state.chatOpen = true;
          panel.classList.add('iris-v37-open');
        } catch(e) {}
      });
      rec.onresult = ev => {
        const transcript = ev.results?.[0]?.[0]?.transcript || '';
        input.value = transcript;
        answer(transcript);
      };
    }
  }

  function initPos(){
    const b = bounds();
    state.x = b.right - 120;
    state.y = b.bottom - 130;
    state.tx = state.x;
    state.ty = state.y;
  }

  function init(){
    removeLegacy();
    createPet();
    initPos();
    dockChat();
    bindModes();
    bindScenes();
    bindMouse();
    bindLocalAssistant();
    cleanSignals();
    refreshState();
    markActive();
    goToNext(true);
    animate();

    setInterval(() => {
      dockChat();
      bindModes();
      bindScenes();
      bindLocalAssistant();
      cleanSignals();
    }, 2500);

    setInterval(() => {
      refreshState();
      if (state.scene === 'libre') goToNext(true);
      else goToNext(false);
    }, 6500);

    addEventListener('resize', () => goToNext(true));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
