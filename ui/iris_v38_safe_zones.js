(() => {
  const qs = (s, r=document) => r.querySelector(s);
  const qsa = (s, r=document) => Array.from(r.querySelectorAll(s));
  const txt = el => ((el?.textContent || '').replace(/\s+/g,' ').trim());
  const low = el => txt(el).toLowerCase();
  const clamp = (v,min,max) => Math.max(min, Math.min(max, v));

  const state = {
    scene: localStorage.getItem('iris_v38_scene') || 'libre',
    mode: localStorage.getItem('iris_v38_mode') || 'autopilot',
    x: 0,
    y: 0,
    tx: 0,
    ty: 0,
    facing: 1,
    currentSite: '',
    bubbleTimer: null,
    moveIndex: 0,
    lastRetarget: 0,
    pausedUntil: 0
  };

  function intersects(a,b){
    return !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom);
  }

  function headingMatch(label){
    return qsa('h1,h2,h3,h4,strong,button,a,div').find(el => low(el) === label.toLowerCase() || low(el).includes(label.toLowerCase()));
  }

  function sectionRect(label){
    const head = qsa('h1,h2,h3,h4,strong').find(el => low(el).includes(label.toLowerCase()));
    const host = head?.closest('section,article,aside,div');
    return host?.getBoundingClientRect() || null;
  }

  function mainBounds(){
    const sidebar = qsa('aside,nav,div').find(el => {
      const r = el.getBoundingClientRect();
      return r.left < 30 && r.width > 170 && r.height > innerHeight * .5;
    });
    const sideW = sidebar ? sidebar.getBoundingClientRect().width : 290;
    return {
      left: sideW + 26,
      top: 92,
      right: innerWidth - 26,
      bottom: innerHeight - 26
    };
  }

  function alphaFromBg(bg){
    if (!bg || bg === 'transparent') return 0;
    const m = bg.match(/rgba?\(([^)]+)\)/i);
    if (!m) return 0;
    const parts = m[1].split(',').map(s => s.trim());
    if (parts.length === 4) return parseFloat(parts[3]) || 0;
    if (parts.length === 3) return 1;
    return 0;
  }

  function collectObstacles(){
    const list = [];
    const b = mainBounds();

    qsa('section,article,aside,div').forEach(el => {
      if (!el || el.id === 'iris-v38-layer' || el.id === 'iris-v37-layer' || el.id === 'iris-v36-layer') return;
      if (el.closest('#iris-v38-layer')) return;

      const r = el.getBoundingClientRect();
      if (r.width < 180 || r.height < 70) return;
      if (r.right < b.left || r.left > b.right || r.bottom < b.top || r.top > b.bottom) return;

      const st = getComputedStyle(el);
      const radius = parseFloat(st.borderRadius) || 0;
      const border = (parseFloat(st.borderTopWidth)||0) + (parseFloat(st.borderLeftWidth)||0);
      const shadow = st.boxShadow && st.boxShadow !== 'none';
      const alpha = alphaFromBg(st.backgroundColor);
      const t = txt(el);

      if (r.width > innerWidth * .85 && r.height > innerHeight * .78) return;
      if (!t || t.length < 4) return;
      if (!(radius > 12 || border > 0 || shadow || alpha > .05)) return;

      list.push({
        left: r.left + 8,
        top: r.top + 8,
        right: r.right - 8,
        bottom: r.bottom - 8
      });
    });

    const dock = qs('.iris-v37-chat-dock');
    if (dock) {
      const r = dock.getBoundingClientRect();
      list.push({ left:r.left-8, top:r.top-8, right:r.right+8, bottom:r.bottom+8 });
    }

    return list.slice(0, 160);
  }

  function createPet(){
    if (qs('#iris-v38-layer')) return;
    const layer = document.createElement('div');
    layer.id = 'iris-v38-layer';
    layer.innerHTML = `
      <div id="iris-v38-pet" class="idle">
        <div class="shadow"></div>
        <div class="tail"></div>
        <div class="body"></div>
        <div class="belly"></div>
        <div class="head"></div>
        <div class="ear l"></div>
        <div class="ear r"></div>
        <div class="visor"></div>
        <div class="eye l"></div>
        <div class="eye r"></div>
        <div class="nose"></div>
        <div class="mouth"></div>
        <div class="paw fl"></div>
        <div class="paw fr"></div>
        <div class="paw bl"></div>
        <div class="paw br"></div>
        <div class="antenna"></div>
        <div class="spark"></div>
      </div>
      <div id="iris-v38-bubble"></div>
    `;
    document.body.appendChild(layer);
  }

  function pet(){ return qs('#iris-v38-pet'); }
  function bubble(){ return qs('#iris-v38-bubble'); }

  function setPose(name){
    const p = pet();
    if (!p) return;
    p.className = name;
  }

  function showBubble(message, ms=1100){
    const b = bubble();
    if (!b) return;
    b.textContent = message;
    b.classList.add('show');
    clearTimeout(state.bubbleTimer);
    state.bubbleTimer = setTimeout(() => b.classList.remove('show'), ms);
  }

  function placeBubble(){
    const p = pet();
    const b = bubble();
    if (!p || !b) return;
    const r = p.getBoundingClientRect();
    b.style.left = `${r.left - 2}px`;
    b.style.top = `${r.top - 34}px`;
  }

  function panelRect(){
    return qs('.iris-v37-chat-dock')?.getBoundingClientRect() || null;
  }

  function safeCandidates(anchor){
    const b = mainBounds();
    const obstacles = collectObstacles();
    const out = [];
    const ax = anchor ? (anchor.left + anchor.right) / 2 : (b.left + b.right) / 2;
    const ay = anchor ? (anchor.top + anchor.bottom) / 2 : (b.top + b.bottom) / 2;

    for (let y = b.top + 26; y < b.bottom - 94; y += 66) {
      for (let x = b.left + 26; x < b.right - 86; x += 66) {
        const pr = { left:x, top:y, right:x+76, bottom:y+88 };
        if (pr.right > b.right - 8 || pr.bottom > b.bottom - 8) continue;
        if (obstacles.some(o => intersects(pr, o))) continue;

        const cx = x + 38;
        const cy = y + 44;

        let minObs = 9999;
        for (const o of obstacles) {
          const ox = clamp(cx, o.left, o.right);
          const oy = clamp(cy, o.top, o.bottom);
          minObs = Math.min(minObs, Math.hypot(cx - ox, cy - oy));
        }

        const edgeDist = Math.min(cx - b.left, b.right - cx, cy - b.top, b.bottom - cy);
        const anchorDist = Math.hypot(cx - ax, cy - ay);
        const rightBias = ((cx - b.left) / (b.right - b.left)) * 18;
        const score = minObs - (edgeDist * 0.15) - (anchorDist * 0.08) + rightBias;

        out.push({ x, y, score });
      }
    }

    return out.sort((a,b) => b.score - a.score).slice(0, 20);
  }

  function sceneAnchor(){
    if (state.scene === 'dock') return panelRect();
    if (state.scene === 'recherche') return sectionRect('watch radar');
    if (state.scene === 'travail') return sectionRect('agents live') || sectionRect('modes système');
    if (state.scene === 'bureau') return sectionRect('deep log');
    if (state.scene === 'repos') return sectionRect('service mesh') || sectionRect('deep log');
    return sectionRect('watch radar') || sectionRect('agents live') || sectionRect('deep log');
  }

  function nextTarget(force=false){
    const b = mainBounds();
    const chat = panelRect();

    if (state.scene === 'dock' && chat) {
      return { x: chat.left - 88, y: Math.max(b.top + 20, chat.top - 18), pose:'peek' };
    }

    if (state.scene === 'repos') {
      return { x: b.right - 116, y: b.bottom - 120, pose:'sleep' };
    }

    const pool = safeCandidates(sceneAnchor());
    if (!pool.length) {
      return { x: b.right - 116, y: b.bottom - 120, pose:'idle' };
    }

    if (force) {
      state.moveIndex = (state.moveIndex + 1) % pool.length;
    } else {
      state.moveIndex = Math.min(state.moveIndex, pool.length - 1);
    }

    const pick = pool[state.moveIndex % pool.length];
    let pose = 'idle';
    if (state.scene === 'travail') pose = 'peek';
    if (state.scene === 'recherche') pose = 'peek';
    if (state.scene === 'bureau') pose = 'idle';
    if (state.scene === 'libre') pose = 'walk';

    return { x: pick.x, y: pick.y, pose };
  }

  function animate(){
    const p = pet();
    if (!p) return requestAnimationFrame(animate);

    const now = Date.now();
    const frozen = now < state.pausedUntil;
    const dx = state.tx - state.x;
    const dy = state.ty - state.y;
    const dist = Math.hypot(dx, dy);

    if (!frozen && dist > 1.2) {
      const speed = Math.max(1.2, Math.min(4.2, dist * 0.06));
      state.x += dx / dist * speed;
      state.y += dy / dist * speed;
      if (Math.abs(dx) > 0.5) state.facing = dx >= 0 ? 1 : -1;
      if (!/sleep|peek/.test(p.className)) setPose('walk');
    } else if (!/sleep|peek/.test(p.className) && dist <= 1.2) {
      setPose(state.scene === 'libre' ? 'idle' : p.className);
    }

    const bounce = dist > 1.2 ? Math.abs(Math.sin(Date.now() * 0.018)) * 4 : Math.abs(Math.sin(Date.now() * 0.006)) * 1.5;
    p.style.transform = `translate(${state.x}px, ${state.y - bounce}px) scaleX(${state.facing})`;

    if (Math.random() < 0.0022) {
      p.classList.add('blink');
      setTimeout(() => p.classList.remove('blink'), 160);
    }

    placeBubble();
    requestAnimationFrame(animate);
  }

  function bindMouse(){
    window.addEventListener('mousemove', (e) => {
      const cx = state.x + 38;
      const cy = state.y + 44;
      const d = Math.hypot(e.clientX - cx, e.clientY - cy);
      if (d < 86) {
        setPose('peek');
        state.pausedUntil = Date.now() + 800;
        showBubble('oui ?', 800);
      }
    });
  }

  function bindButtons(){
    [
      ['libre','libre'],
      ['bureau','bureau'],
      ['travail','travail'],
      ['recherche','recherche'],
      ['repos','repos'],
      ['dock chat','dock']
    ].forEach(([needle, value]) => {
      const btn = headingMatch(needle);
      if (btn && !btn.dataset.v38scene) {
        btn.dataset.v38scene = '1';
        btn.addEventListener('click', () => {
          state.scene = value;
          localStorage.setItem('iris_v38_scene', value);
          const t = nextTarget(true);
          state.tx = t.x;
          state.ty = t.y;
          setPose(t.pose);
        });
      }
    });

    [
      ['off','OFF'],
      ['travail','travail'],
      ['veille légère','light'],
      ['autopilot','autopilot'],
      ['normal','normal'],
      ['on','ON']
    ].forEach(([needle, value]) => {
      const btn = headingMatch(needle);
      if (btn && !btn.dataset.v38mode) {
        btn.dataset.v38mode = '1';
        btn.addEventListener('click', () => {
          state.mode = value;
          localStorage.setItem('iris_v38_mode', value);
          if (value === 'OFF') state.scene = 'repos';
          if (value === 'travail') state.scene = 'travail';
          if (value === 'light') state.scene = 'recherche';
          const t = nextTarget(true);
          state.tx = t.x;
          state.ty = t.y;
          setPose(t.pose);
        });
      }
    });
  }

  function cleanSignals(){
    qsa('div,p,span,pre').forEach(el => {
      const t = txt(el);
      if (/ModuleNotFoundError: No module named 'requests'/.test(t)) el.textContent = 'n/a';
      if (/^"services_ok":\s*\d+/.test(t)) el.textContent = 'STATE_OK';
    });
  }

  async function refreshState(){
    try{
      const r = await fetch('/api/state', { cache:'no-store' });
      if (!r.ok) return;
      const data = await r.json();
      const s = data.summary || data;
      state.currentSite = s.watch_current || '';
    }catch(e){}
  }

  function initPos(){
    const b = mainBounds();
    state.x = b.right - 110;
    state.y = b.bottom - 118;
    state.tx = state.x;
    state.ty = state.y;
  }

  function init(){
    createPet();
    initPos();
    bindButtons();
    bindMouse();
    cleanSignals();
    refreshState();

    const t = nextTarget(true);
    state.tx = t.x;
    state.ty = t.y;
    setPose(t.pose);

    animate();

    setInterval(() => {
      bindButtons();
      cleanSignals();
    }, 2800);

    setInterval(() => {
      refreshState();
      const t2 = nextTarget(true);
      state.tx = t2.x;
      state.ty = t2.y;
      if (state.scene === 'repos') setPose('sleep');
      else if (state.scene === 'dock') setPose('peek');
      else if (!/peek/.test(pet()?.className || '')) setPose(t2.pose);
    }, 6800);

    window.addEventListener('resize', () => {
      const t3 = nextTarget(true);
      state.tx = t3.x;
      state.ty = t3.y;
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
