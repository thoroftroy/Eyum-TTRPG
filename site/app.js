const THEME_KEY = 'eyum-theme';
const DEFAULTS = { text: '#ffffff', bg: '#000000' };

const els = {
  tree: document.getElementById('tree'),
  content: document.getElementById('content'),
  breadcrumbs: document.getElementById('breadcrumbs'),
  textColor: document.getElementById('textColor'),
  bgColor: document.getElementById('bgColor'),
  resetTheme: document.getElementById('resetTheme'),
  sidebar: document.getElementById('sidebar'),
  mobileSidebar: document.getElementById('mobileSidebar'),
  toggleSidebar: document.getElementById('toggleSidebar'),
  graphToggle: document.getElementById('graphToggle'),
  graphPanel: document.getElementById('graphPanel'),
  graphClose: document.getElementById('graphClose'),
  graphCanvas: document.getElementById('graphCanvas'),
};

let manifest;
let currentPath = null;
let wikiMap = new Map();

marked.setOptions({
  gfm: true,
  breaks: false,
  headerIds: true,
  mangle: false,
});

function applyTheme(theme) {
  document.documentElement.style.setProperty('--text', theme.text);
  document.documentElement.style.setProperty('--bg', theme.bg);
  els.textColor.value = theme.text;
  els.bgColor.value = theme.bg;
}

function saveTheme(theme) {
  localStorage.setItem(THEME_KEY, JSON.stringify(theme));
}

function loadTheme() {
  try {
    const theme = JSON.parse(localStorage.getItem(THEME_KEY));
    if (theme?.text && theme?.bg) return theme;
  } catch {}
  return DEFAULTS;
}

class GraphView {
  constructor(container, manifest, currentPath, onNavigate) {
    this.container = container;
    this.manifest = manifest;
    this._currentPath = currentPath;
    this.onNavigate = onNavigate;

    this.nodeMap = new Map();
    buildGraphNodeMap(manifest.tree, this.nodeMap);

    this.nodes = [];
    this.nodeById = new Map();
    for (const [path, name] of this.nodeMap) {
      const node = { id: path, name, x: 0, y: 0, vx: 0, vy: 0 };
      this.nodes.push(node);
      this.nodeById.set(path, node);
    }

    this.edges = [];
    for (const [src, tgt] of manifest.edges || []) {
      const s = this.nodeById.get(src);
      const t = this.nodeById.get(tgt);
      if (s && t) this.edges.push({ source: s, target: t });
    }

    this.adj = new Map();
    for (const node of this.nodes) this.adj.set(node, new Set());
    for (const e of this.edges) {
      this.adj.get(e.source).add(e.target);
      this.adj.get(e.target).add(e.source);
    }

    this.canvas = document.createElement('canvas');
    this.ctx = this.canvas.getContext('2d');
    this.container.appendChild(this.canvas);

    this.dpr = window.devicePixelRatio || 1;
    this.viewX = 0;
    this.viewY = 0;
    this.hovered = null;
    this.dragging = null;
    this.panning = null;
    this.dragMoved = false;
    this.simAlpha = 1;
    this.initialized = false;

    this.setupEvents();
    // Defer layout-dependent setup until browser has laid out the panel
    requestAnimationFrame(() => {
      this.resize();
      if (!this.width || !this.height) return;
      this.initPositions();
      this.initialized = true;
      this.tick();
    });
  }

  get currentPath() { return this._currentPath; }
  set currentPath(v) { this._currentPath = v; }

  resize() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    if (w === 0 || h === 0) return;
    this.width = w;
    this.height = h;
    this.canvas.width = w * this.dpr;
    this.canvas.height = h * this.dpr;
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
  }

  initPositions() {
    const cx = this.width / 2;
    const cy = this.height / 2;
    const r = Math.min(this.width, this.height) * 0.35;
    const n = this.nodes.length;
    for (let i = 0; i < n; i++) {
      const angle = (2 * Math.PI * i) / n;
      this.nodes[i].x = cx + r * Math.cos(angle) + (Math.random() - 0.5) * 20;
      this.nodes[i].y = cy + r * Math.sin(angle) + (Math.random() - 0.5) * 20;
    }
  }

  applyForces() {
    if (this.simAlpha < 0.001) return;
    const repulsion = 3000;
    const attraction = 0.005;
    const centering = 0.02;
    const damping = 0.85;
    const minDist = 30;
    const idealEdgeLen = 120;

    for (let i = 0; i < this.nodes.length; i++) {
      for (let j = i + 1; j < this.nodes.length; j++) {
        let dx = this.nodes[j].x - this.nodes[i].x;
        let dy = this.nodes[j].y - this.nodes[i].y;
        let dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < minDist) dist = minDist;
        const force = repulsion / (dist * dist);
        const fx = force * (dx / dist) * this.simAlpha;
        const fy = force * (dy / dist) * this.simAlpha;
        this.nodes[i].vx -= fx;
        this.nodes[i].vy -= fy;
        this.nodes[j].vx += fx;
        this.nodes[j].vy += fy;
      }
    }

    for (const e of this.edges) {
      let dx = e.target.x - e.source.x;
      let dy = e.target.y - e.source.y;
      let dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 1) dist = 1;
      const force = (dist - idealEdgeLen) * attraction;
      const fx = force * (dx / dist) * this.simAlpha;
      const fy = force * (dy / dist) * this.simAlpha;
      e.source.vx += fx;
      e.source.vy += fy;
      e.target.vx -= fx;
      e.target.vy -= fy;
    }

    const cx = this.width / 2;
    const cy = this.height / 2;
    for (const node of this.nodes) {
      node.vx += (cx - node.x) * centering * this.simAlpha;
      node.vy += (cy - node.y) * centering * this.simAlpha;
      node.vx *= damping;
      node.vy *= damping;
      node.x += node.vx;
      node.y += node.vy;
    }
    this.simAlpha *= 0.997;
  }

  getNodeAt(x, y) {
    for (const node of this.nodes) {
      const dx = x - node.x;
      const dy = y - node.y;
      if (dx * dx + dy * dy < 144) return node;
    }
    return null;
  }

  render() {
    const ctx = this.ctx;
    const w = this.width;
    const h = this.height;
    const dpr = this.dpr;

    if (!w || !h) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const currentConnections = new Set();
    if (this._currentPath) {
      const current = this.nodeById.get(this._currentPath);
      if (current) {
        currentConnections.add(current);
        const neighbors = this.adj.get(current);
        if (neighbors) {
          for (const n of neighbors) currentConnections.add(n);
        }
      }
    }

    ctx.save();
    ctx.translate(this.viewX, this.viewY);

    const dimAlpha = 0.12;
    for (const e of this.edges) {
      const connected = currentConnections.has(e.source) && currentConnections.has(e.target);
      ctx.strokeStyle = connected ? 'rgba(255,255,255,0.35)' : `rgba(255,255,255,${dimAlpha})`;
      ctx.lineWidth = connected ? 1.2 : 0.5;
      ctx.beginPath();
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      ctx.stroke();
    }

    const nodeRadius = 5;
    const nodeRadiusHover = 7;
    const nodeRadiusCurrent = 8;

    for (const node of this.nodes) {
      const isCurrent = this._currentPath && node.id === this._currentPath;
      const isConnected = currentConnections.has(node);
      const isHovered = this.hovered === node;

      let alpha, radius;
      if (isCurrent) { alpha = 1; radius = nodeRadiusCurrent; }
      else if (isHovered) { alpha = 1; radius = nodeRadiusHover; }
      else if (isConnected) { alpha = 0.7; radius = nodeRadius; }
      else { alpha = dimAlpha; radius = nodeRadius; }

      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = `rgba(255,255,255,${alpha})`;
      ctx.fill();

      if (isCurrent) {
        ctx.strokeStyle = '#7ab7ff';
        ctx.lineWidth = 2;
        ctx.stroke();
      } else if (isHovered) {
        ctx.strokeStyle = 'rgba(255,255,255,0.6)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    }

    for (const node of this.nodes) {
      const sx = node.x + this.viewX;
      const sy = node.y + this.viewY;
      if (sx < -10 || sx > w + 10 || sy < -10 || sy > h + 10) continue;
      const name = node.name.length > 24 ? node.name.slice(0, 21) + '...' : node.name;
      ctx.font = '10px sans-serif';
      const tw = ctx.measureText(name).width;
      const lx = Math.max(2, Math.min(w - tw - 8, sx - tw / 2));
      const ly = nodeRadius + 4;
      ctx.fillStyle = 'rgba(0,0,0,0.7)';
      ctx.fillRect(lx - 3, sy + ly - 2, tw + 6, 14);
      ctx.fillStyle = this.hovered === node || (this._currentPath && node.id === this._currentPath) ? '#fff' : 'rgba(255,255,255,0.7)';
      ctx.fillText(name, lx, sy + ly + 9);
    }
    ctx.restore();
  }

  tick() {
    if (this.initialized) {
      this.applyForces();
      this.render();
    }
    this._frame = requestAnimationFrame(() => this.tick());
  }

  setupEvents() {
    const getPos = (e) => {
      const r = this.canvas.getBoundingClientRect();
      const t = e.touches ? e.touches[0] : e;
      return { x: t.clientX - r.left, y: t.clientY - r.top };
    };

    const worldPos = (pos) => ({
      x: pos.x - this.viewX,
      y: pos.y - this.viewY,
    });

    const onDown = (pos) => {
      const wp = worldPos(pos);
      const node = this.getNodeAt(wp.x, wp.y);
      if (node) {
        this.dragging = node;
        this.dragOffset = { x: wp.x - node.x, y: wp.y - node.y };
        this.dragMoved = false;
        this.simAlpha = 1;
      } else {
        this.panning = { startX: pos.x, startY: pos.y, viewX: this.viewX, viewY: this.viewY };
        this.canvas.style.cursor = 'grabbing';
      }
    };

    const onMove = (pos) => {
      if (this.dragging) {
        const wp = worldPos(pos);
        this.dragging.x = wp.x - this.dragOffset.x;
        this.dragging.y = wp.y - this.dragOffset.y;
        this.dragMoved = true;
        this.simAlpha = 1;
        return;
      }
      if (this.panning) {
        this.viewX = this.panning.viewX + (pos.x - this.panning.startX);
        this.viewY = this.panning.viewY + (pos.y - this.panning.startY);
        this.canvas.style.cursor = 'grabbing';
        return;
      }
      const wp = worldPos(pos);
      this.hovered = this.getNodeAt(wp.x, wp.y);
      this.canvas.style.cursor = this.hovered ? 'pointer' : '';
    };

    const onUp = () => {
      if (this.dragging) {
        const node = this.dragging;
        this.dragging = null;
        if (!this.dragMoved && this.onNavigate) {
          this.onNavigate(node.id);
        }
        return;
      }
      this.panning = null;
      this.canvas.style.cursor = '';
    };

    this.canvas.addEventListener('mousemove', (e) => onMove(getPos(e)));
    this.canvas.addEventListener('mousedown', (e) => onDown(getPos(e)));
    this.canvas.addEventListener('mouseup', onUp);
    this.canvas.addEventListener('mouseleave', () => {
      this.hovered = null;
      this.dragging = null;
      this.panning = null;
    });

    this.canvas.addEventListener('touchstart', (e) => {
      e.preventDefault();
      onDown(getPos(e));
    }, { passive: false });
    this.canvas.addEventListener('touchmove', (e) => {
      e.preventDefault();
      onMove(getPos(e));
    }, { passive: false });
    this.canvas.addEventListener('touchend', (e) => {
      e.preventDefault();
      onUp();
    }, { passive: false });

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.container);
  }

  destroy() {
    if (this._frame) cancelAnimationFrame(this._frame);
    if (this.resizeObserver) this.resizeObserver.disconnect();
  }
}

function buildGraphNodeMap(node, map) {
  if (node.type === 'file') {
    const name = node.name.replace(/\.md$/i, '');
    map.set(node.path, name);
    return;
  }
  for (const child of node.children || []) buildGraphNodeMap(child, map);
}

function slugifyTitle(title) {
  return title
    .replace(/\.md$/i, '')
    .trim()
    .toLowerCase();
}

function buildWikiMap(node, basePath = '') {
  if (node.type === 'file') {
    const fileName = node.name.replace(/\.md$/i, '');
    wikiMap.set(slugifyTitle(fileName), node.path);
    return;
  }
  for (const child of node.children || []) buildWikiMap(child, basePath);
}

function renderTree(node, container) {
  const sorted = [...(node.children || [])].sort((a, b) => {
    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
    return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' });
  });

  for (const child of sorted) {
    if (child.type === 'folder') {
      const details = document.createElement('details');
      details.open = true;
      const summary = document.createElement('summary');
      const span = document.createElement('span');
      span.className = 'folder-label';
      span.textContent = child.name;
      summary.appendChild(span);
      details.appendChild(summary);
      const inner = document.createElement('div');
      renderTree(child, inner);
      details.appendChild(inner);
      container.appendChild(details);
    } else if (child.type === 'file') {
      const link = document.createElement('a');
      link.href = `#${encodeURIComponent(child.path)}`;
      link.className = 'file-link';
      link.dataset.path = child.path;
      link.textContent = child.name.replace(/\.md$/i, '');
      container.appendChild(link);
    }
  }

  if (node.name === '6.0 Magic') {
    const sep = document.createElement('div');
    sep.style.cssText = 'border-top:1px solid #444;margin:6px 0';
    container.appendChild(sep);
    const link = document.createElement('a');
    link.href = '#__charmgr__';
    link.className = 'file-link charmgr-link';
    link.dataset.path = '__charmgr__';
    link.textContent = 'Character Manager';
    link.style.cssText = 'font-weight:bold;color:#4fc3f7';
    container.appendChild(link);
  }
}

function updateActiveLink() {
  document.querySelectorAll('.file-link').forEach((a) => {
    a.classList.toggle('active', a.dataset.path === currentPath);
  });
}

function setBreadcrumbs(path) {
  els.breadcrumbs.textContent = path;
}

function fixWikiLinks(markdown) {
  return markdown.replace(/\[\[([^\]]+)\]\]/g, (_, target) => {
    const clean = target.split('|')[0].trim();
    const mapped = wikiMap.get(slugifyTitle(clean));
    if (!mapped) return clean;
    return `[${clean}](#${encodeURIComponent(mapped)})`;
  });
}

async function loadPage(path) {
  currentPath = path;
  if (graphView) graphView.currentPath = path;
  updateActiveLink();
  setBreadcrumbs(path);
  els.content.innerHTML = '<div class="loading">Loading...</div>';

  if (path === '__charmgr__') {
    try {
      setBreadcrumbs('Character Manager');
      const res = await fetch('./charmgr.html');
      if (!res.ok) throw new Error('Could not load Character Manager');
      els.content.innerHTML = await res.text();
      initCharManager();
      window.scrollTo({ top: 0, behavior: 'instant' });
    } catch (err) {
      els.content.innerHTML = `<div class="error">${err.message}</div>`;
    }
    return;
  }

  try {
    const res = await fetch(`./content/${path}`);
    if (!res.ok) throw new Error(`Could not load ${path}`);
    let markdown = await res.text();
    markdown = fixWikiLinks(markdown);
    const html = marked.parse(markdown);
    const sanitized = DOMPurify.sanitize(html);
    els.content.innerHTML = sanitized;
    interceptContentLinks();
    window.scrollTo({ top: 0, behavior: 'instant' });
  } catch (err) {
    els.content.innerHTML = `<div class="error">${err.message}</div>`;
  }
}

function interceptContentLinks() {
  els.content.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener('click', (e) => {
      const hash = a.getAttribute('href');
      if (!hash) return;
      const target = decodeURIComponent(hash.slice(1));
      if (!target.endsWith('.md')) return;
      e.preventDefault();
      location.hash = encodeURIComponent(target);
    });
  });
}

function getDefaultFile(node) {
  if (node.type === 'file') return node.path;
  for (const child of node.children || []) {
    const found = getDefaultFile(child);
    if (found) return found;
  }
  return null;
}

let graphView = null;

function toggleGraph(manifest) {
  if (!els.graphPanel) return;
  if (els.graphPanel.classList.toggle('open')) {
    if (!graphView) {
      try {
        graphView = new GraphView(els.graphCanvas, manifest, currentPath, (path) => {
          location.hash = encodeURIComponent(path);
          els.graphPanel.classList.remove('open');
        });
      } catch (err) {
        console.error('GraphView failed:', err);
        els.graphPanel.classList.remove('open');
      }
    } else {
      graphView.currentPath = currentPath;
    }
  }
}

function registerUIEvents() {
  window.addEventListener('hashchange', () => {
    const path = decodeURIComponent(location.hash.slice(1));
    if (path) loadPage(path);
  });

  els.textColor.addEventListener('input', () => {
    const theme = { text: els.textColor.value, bg: els.bgColor.value };
    applyTheme(theme);
    saveTheme(theme);
  });

  els.bgColor.addEventListener('input', () => {
    const theme = { text: els.textColor.value, bg: els.bgColor.value };
    applyTheme(theme);
    saveTheme(theme);
  });

  els.resetTheme.addEventListener('click', () => {
    applyTheme(DEFAULTS);
    saveTheme(DEFAULTS);
  });

  els.mobileSidebar.addEventListener('click', () => els.sidebar.classList.add('open'));
  els.toggleSidebar.addEventListener('click', () => els.sidebar.classList.remove('open'));

  document.addEventListener('click', (e) => {
    const target = e.target;
    if (window.innerWidth > 900) return;
    if (!(target instanceof Element)) return;
    if (!els.sidebar.contains(target) && !els.mobileSidebar.contains(target)) {
      els.sidebar.classList.remove('open');
    }
  });

  if (els.graphToggle) {
    els.graphToggle.addEventListener('click', () => { try { toggleGraph(manifest); } catch (e) { console.error(e); } });
  }
  if (els.graphClose) {
    els.graphClose.addEventListener('click', () => { if (els.graphPanel) els.graphPanel.classList.remove('open'); });
  }
}

async function init() {
  applyTheme(loadTheme());

  // Register UI events first so theme/sidebar controls work even if manifest fails
  registerUIEvents();

  try {
    const manifestRes = await fetch('./manifest.json');
    manifest = await manifestRes.json();
    buildWikiMap(manifest.tree);
    renderTree(manifest.tree, els.tree);

    const requested = location.hash ? decodeURIComponent(location.hash.slice(1)) : null;
    const start = requested || manifest.defaultFile || getDefaultFile(manifest.tree);
    if (start) await loadPage(start);
  } catch (err) {
    els.content.innerHTML = `<div class="error">Failed to load site data: ${err.message}</div>`;
  }
}

init();
