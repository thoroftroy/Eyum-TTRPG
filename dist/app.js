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
  graphPanel: document.getElementById('graphPanel'),
  graphClose: document.getElementById('graphClose'),
  graphCanvas: document.getElementById('graphCanvas'),
  graphZoomIn: document.getElementById('graphZoomIn'),
  graphZoomOut: document.getElementById('graphZoomOut'),
  graphReset: document.getElementById('graphReset'),
  prevFile: document.getElementById('prevFile'),
  nextFile: document.getElementById('nextFile'),
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
      const node = { id: path, name, x: 0, y: 0, vx: 0, vy: 0, section: getSection(path) };
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

    for (const node of this.nodes) {
      node.degree = (this.adj.get(node) || new Set()).size;
    }

    this.canvas = document.createElement('canvas');
    this.ctx = this.canvas.getContext('2d');
    this.container.appendChild(this.canvas);

    this.dpr = window.devicePixelRatio || 1;
    this.viewX = 0;
    this.viewY = 0;
    this.zoom = 1;
    this.targetZoom = 1;
    this.viewTX = 0; // target pan
    this.viewTY = 0;
    this.hovered = null;
    this.dragging = null;
    this.panning = null;
    this.dragMoved = false;
    this.simAlpha = 1;
    this.initialized = false;

    this.setupEvents();
    this._initRetries = 0;
    this._tryInit();
  }

  _tryInit() {
    this.resize();
    if (this.width && this.height) {
      this.initPositions();
      this.initialized = true;
      this.tick();
      return;
    }
    this._initRetries++;
    if (this._initRetries < 50) {
      this._initTimer = setTimeout(() => this._tryInit(), 100);
    }
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
      const angle = (2 * Math.PI * i) / n + (Math.random() - 0.5) * 0.3;
      const jitter = (Math.random() - 0.5) * 60;
      this.nodes[i].x = cx + (r + jitter) * Math.cos(angle);
      this.nodes[i].y = cy + (r + jitter) * Math.sin(angle);
    }
  }

  applyForces() {
    if (this.simAlpha < 0.0005) return;
    const repulsion = 4000;
    const attraction = 0.008;
    const centering = 0.015;
    const damping = 0.82;
    const minDist = 40;
    const idealEdgeLen = 100;

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
    this.simAlpha *= 0.996;
  }

  getNodeAt(wx, wy) {
    const hitRadius = 18;
    for (const node of this.nodes) {
      const dx = wx - node.x;
      const dy = wy - node.y;
      if (dx * dx + dy * dy < hitRadius * hitRadius) return node;
    }
    return null;
  }

  nodeRadius(node) {
    return 3 + Math.log2(node.degree + 1) * 2.5;
  }

  nodeColor(node) {
    const colors = {
      '0': '#666',      // In Progress - grey
      '1': '#5e9cf5',   // Basics - blue
      '2': '#4ade80',   // Reference - green
      '3': '#f59e0b',   // Character Mgmt - amber
      '4': '#f87171',   // Races - red
      '5': '#c084fc',   // Deities - purple
      '6': '#22d3ee',   // Magic - cyan
      '7': '#facc15',   // Monsters - yellow
    };
    return colors[node.section] || '#888';
  }

  render() {
    const ctx = this.ctx;
    const w = this.width;
    const h = this.height;
    const dpr = this.dpr;

    if (!w || !h) return;

    const zoom = this.zoom;
    // Smooth zoom lerp
    this.zoom += (this.targetZoom - this.zoom) * 0.2;
    this.viewX += (this.viewTX - this.viewX) * 0.2;
    this.viewY += (this.viewTY - this.viewY) * 0.2;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    // Build hover connection set
    const hoverConnections = new Set();
    if (this.hovered) {
      hoverConnections.add(this.hovered);
      const neighbors = this.adj.get(this.hovered);
      if (neighbors) for (const n of neighbors) hoverConnections.add(n);
    }

    // Build current page connection set
    const currentConnections = new Set();
    if (this._currentPath) {
      const current = this.nodeById.get(this._currentPath);
      if (current) {
        currentConnections.add(current);
        const neighbors = this.adj.get(current);
        if (neighbors) for (const n of neighbors) currentConnections.add(n);
      }
    }

    const hasHover = this.hovered !== null;
    const highlightSet = hasHover ? hoverConnections : currentConnections;

    ctx.save();
    ctx.translate(w / 2, h / 2);
    ctx.scale(zoom, zoom);
    ctx.translate(-w / 2, -w / 2);
    ctx.translate(this.viewX, this.viewY);

    // Edges
    for (const e of this.edges) {
      const inHighlight = hasHover
        ? (hoverConnections.has(e.source) && hoverConnections.has(e.target))
        : (currentConnections.has(e.source) && currentConnections.has(e.target));

      let alpha, lineW;
      if (hasHover) {
        alpha = inHighlight ? 0.6 : 0.04;
        lineW = inHighlight ? 1.4 : 0.3;
      } else {
        alpha = inHighlight ? 0.4 : 0.08;
        lineW = inHighlight ? 1.2 : 0.4;
      }

      ctx.strokeStyle = `rgba(255,255,255,${alpha})`;
      ctx.lineWidth = lineW / zoom;
      ctx.beginPath();
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      ctx.stroke();
    }

    // Nodes
    const sortedNodes = [...this.nodes].sort((a, b) => {
      const aH = hoverConnections.has(a) ? 1 : 0;
      const bH = hoverConnections.has(b) ? 1 : 0;
      return aH - bH;
    });

    for (const node of sortedNodes) {
      const isCurrent = !hasHover && this._currentPath && node.id === this._currentPath;
      const isHovered = this.hovered === node;
      const isInHighlight = highlightSet.has(node);

      let alpha;
      if (isHovered) alpha = 1;
      else if (isCurrent) alpha = 1;
      else if (isInHighlight) alpha = hasHover ? 0.7 : 0.75;
      else alpha = hasHover ? 0.06 : 0.13;

      const baseR = this.nodeRadius(node);
      const r = (isHovered || isCurrent) ? baseR + 3 : baseR;
      const color = this.nodeColor(node);
      const glowR = r * 3;

      // Glow
      if (alpha > 0.2) {
        const glow = ctx.createRadialGradient(node.x, node.y, r * 0.4, node.x, node.y, glowR);
        glow.addColorStop(0, `rgba(${hexToRgb(color)},${alpha * 0.6})`);
        glow.addColorStop(0.4, `rgba(${hexToRgb(color)},${alpha * 0.15})`);
        glow.addColorStop(1, `rgba(${hexToRgb(color)},0)`);
        ctx.beginPath();
        ctx.arc(node.x, node.y, glowR, 0, 2 * Math.PI);
        ctx.fillStyle = glow;
        ctx.fill();
      }

      // Core
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = `rgba(${hexToRgb(color)},${alpha})`;
      ctx.fill();

      // Ring on hover/current
      if (isHovered || isCurrent) {
        ctx.strokeStyle = isCurrent ? '#ffffff' : `rgba(${hexToRgb(color)},0.9)`;
        ctx.lineWidth = (isCurrent ? 2.5 : 1.8) / zoom;
        ctx.stroke();
      }
    }

    // Labels (hovered node + current node only)
    for (const node of this.nodes) {
      const isCurrent = !hasHover && this._currentPath && node.id === this._currentPath;
      const isHovered = this.hovered === node;
      if (!isHovered && !isCurrent) continue;

      const r = this.nodeRadius(node) + 3;
      const name = node.name.length > 28 ? node.name.slice(0, 25) + '...' : node.name;
      const fontSize = Math.max(10, 12 / zoom);
      ctx.font = `600 ${fontSize}px Inter, ui-sans-serif, sans-serif`;
      const tw = ctx.measureText(name).width;
      const th = fontSize + 4;
      const lx = node.x - tw / 2;
      const ly = node.y + r + 6;

      ctx.fillStyle = 'rgba(0,0,0,0.75)';
      roundRect(ctx, lx - 5, ly - 2, tw + 10, th, 4 / zoom);
      ctx.fillStyle = isHovered ? '#fff' : `rgba(${hexToRgb(this.nodeColor(node))},0.95)`;
      ctx.fillText(name, lx, ly + fontSize * 0.85);
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

  // Public zoom controls
  zoomIn() { this.setZoom(this.targetZoom * 1.3); }
  zoomOut() { this.setZoom(this.targetZoom / 1.3); }
  resetView() {
    this.targetZoom = 1;
    this.viewTX = 0;
    this.viewTY = 0;
    this.zoom = 1;
    this.viewX = 0;
    this.viewY = 0;
    this.simAlpha = 1;
  }

  setZoom(z) {
    this.targetZoom = Math.max(0.15, Math.min(3, z));
  }

  setupEvents() {
    const getPos = (e) => {
      const r = this.canvas.getBoundingClientRect();
      const t = e.touches ? e.touches[0] : e;
      return { x: t.clientX - r.left, y: t.clientY - r.top };
    };

    const worldPos = (pos) => {
      const cx = this.width / 2;
      const cy = this.height / 2;
      return {
        x: (pos.x - cx) / this.zoom + cx - this.viewX,
        y: (pos.y - cy) / this.zoom + cy - this.viewY,
      };
    };

    // Pinch zoom state
    let pinchDist = 0;
    let pinchZoom = 1;

    const onDown = (pos, e) => {
      if (e && e.touches && e.touches.length === 2) {
        pinchDist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        pinchZoom = this.targetZoom;
        return;
      }
      const wp = worldPos(pos);
      const node = this.getNodeAt(wp.x, wp.y);
      if (node) {
        this.dragging = node;
        this.dragOffset = { x: wp.x - node.x, y: wp.y - node.y };
        this.dragMoved = false;
        this.simAlpha = 0.3;
      } else {
        this.panning = { startX: pos.x, startY: pos.y, viewTX: this.viewTX, viewTY: this.viewTY };
        this.canvas.style.cursor = 'grabbing';
      }
    };

    const onMove = (pos, e) => {
      if (e && e.touches && e.touches.length === 2) {
        const d = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        if (pinchDist > 0) {
          this.targetZoom = Math.max(0.15, Math.min(3, pinchZoom * (d / pinchDist)));
        }
        return;
      }
      if (this.dragging) {
        const wp = worldPos(pos);
        this.dragging.x = wp.x - this.dragOffset.x;
        this.dragging.y = wp.y - this.dragOffset.y;
        this.dragMoved = true;
        return;
      }
      if (this.panning) {
        this.viewTX = this.panning.viewTX + (pos.x - this.panning.startX);
        this.viewTY = this.panning.viewTY + (pos.y - this.panning.startY);
        this.canvas.style.cursor = 'grabbing';
        return;
      }
      const wp = worldPos(pos);
      this.hovered = this.getNodeAt(wp.x, wp.y);
      this.canvas.style.cursor = this.hovered ? 'pointer' : 'grab';
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
      this.pinchDist = 0;
      this.canvas.style.cursor = this.hovered ? 'pointer' : 'grab';
    };

    this.canvas.addEventListener('mousemove', (e) => onMove(getPos(e)));
    this.canvas.addEventListener('mousedown', (e) => onDown(getPos(e)));
    this.canvas.addEventListener('mouseup', onUp);
    this.canvas.addEventListener('mouseleave', () => {
      this.hovered = null;
      this.dragging = null;
      this.panning = null;
    });

    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = -e.deltaY * 0.002;
      this.targetZoom = Math.max(0.15, Math.min(3, this.targetZoom * (1 + delta)));
    }, { passive: false });

    this.canvas.addEventListener('touchstart', (e) => {
      e.preventDefault();
      onDown(getPos(e), e);
    }, { passive: false });
    this.canvas.addEventListener('touchmove', (e) => {
      e.preventDefault();
      onMove(getPos(e), e);
    }, { passive: false });
    this.canvas.addEventListener('touchend', (e) => {
      e.preventDefault();
      onUp();
    }, { passive: false });

    this.resizeObserver = new ResizeObserver(() => {
      if (!this.width || !this.height) return;
      const cx = this.width / 2;
      const cy = this.height / 2;
      this.resize();
      const nx = this.width / 2;
      const ny = this.height / 2;
      if (isNaN(nx) || isNaN(ny)) return;
      this.viewTX += (nx - cx);
      this.viewTY += (ny - cy);
    });
    this.resizeObserver.observe(this.container);
  }

  destroy() {
    if (this._frame) cancelAnimationFrame(this._frame);
    if (this.resizeObserver) this.resizeObserver.disconnect();
  }
}

function getSection(path) {
  if (!path) return '0';
  const m = path.match(/^(\d+)/);
  return m ? m[1] : '0';
}

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1,3), 16);
  const g = parseInt(hex.slice(3,5), 16);
  const b = parseInt(hex.slice(5,7), 16);
  return `${r},${g},${b}`;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
  ctx.fill();
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

let flatFileList = [];
function buildFlatList(node) {
  if (node.type === 'file') flatFileList.push(node.path);
  for (const child of node.children || []) buildFlatList(child);
}

function updateNavButtons() {
  if (!currentPath) return;
  const idx = flatFileList.indexOf(currentPath);
  if (els.prevFile) els.prevFile.disabled = idx <= 0;
  if (els.nextFile) els.nextFile.disabled = idx < 0 || idx >= flatFileList.length - 1;
}

function renderTree(node, container) {
  const sorted = [...(node.children || [])].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' })
  );

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
      inner.style.paddingLeft = '14px';
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
    const parts = target.split('|');
    const raw = parts[0].trim();
    const display = parts.length > 1 ? parts[1].trim() : raw;
    const hashIdx = raw.indexOf('#');
    const pageName = hashIdx >= 0 ? raw.slice(0, hashIdx).trim() : raw;
    const fragment = hashIdx >= 0 ? raw.slice(hashIdx + 1).trim() : null;
    const mapped = wikiMap.get(slugifyTitle(pageName));
    if (!mapped) return display;
    const url = `#${encodeURIComponent(mapped)}`;
    const fullUrl = fragment ? url + '%23' + slugifyFragment(fragment) : url;
    return `[${display}](${fullUrl})`;
  });
}

function slugifyFragment(text) {
  return text.toLowerCase().replace(/[^\w]+/g, '-').replace(/^-+|-+$/g, '');
}

async function loadPage(path, scrollToId) {
  // Section 2.7 - Character Reference -> load editable character sheet
  if (path.includes('2.7 Character Sheet')) {
    currentPath = path;
    setBreadcrumbs(path);
    updateActiveLink();
    if (graphView) graphView.currentPath = path;
    renderCharacterSheet();
    return;
  }

  currentPath = path;
  let pageName = path.replace(/\.md$/i, '').split('/').pop();
  document.title = pageName + ': Eyum TTRPG';
  if (graphView) graphView.currentPath = path;
  updateActiveLink();
  updateNavButtons();
  setBreadcrumbs(path);
  els.content.innerHTML = '<div class="loading">Loading...</div>';

  try {
    const res = await fetch(`./content/${path}`);
    if (!res.ok) throw new Error(`Could not load ${path}`);
    let markdown = await res.text();
    markdown = fixWikiLinks(markdown);
    const html = marked.parse(markdown);
    const sanitized = DOMPurify.sanitize(html);
    els.content.innerHTML = sanitized;
    interceptContentLinks();
    const targetId = scrollToId || (() => {
      try {
        const raw = decodeURIComponent(location.hash.slice(1));
        const parts = raw.split('#');
        return parts.length > 1 ? parts[1] : null;
      } catch { return null; }
    })();
    if (targetId) {
      requestAnimationFrame(() => {
        let el = document.getElementById(targetId);
        if (!el) {
          const searchText = targetId.replace(/-/g, ' ').toLowerCase();
          const headings = els.content.querySelectorAll('h1,h2,h3,h4,h5,h6');
          for (const h of headings) {
            if (h.textContent.toLowerCase().trim() === searchText) {
              el = h;
              break;
            }
          }
        }
        if (el) el.scrollIntoView({ behavior: 'instant' });
        else els.content.scrollTop = 0;
      });
    } else {
      els.content.scrollTop = 0;
    }
  } catch (err) {
    els.content.innerHTML = `<div class="error">${err.message}</div>`;
  }
}

function interceptContentLinks() {
  els.content.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener('click', (e) => {
      const hash = a.getAttribute('href');
      if (!hash) return;
      const decoded = decodeURIComponent(hash.slice(1));
      const [target, fragment] = decoded.split('#');
      if (!target || !target.endsWith('.md')) return;
      e.preventDefault();
      location.hash = encodeURIComponent(target) + (fragment ? '#' + fragment : '');
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

// ========== CHARACTER SHEET (2.7) - pdf.js render + AcroForm annotation overlays ==========
const CS_STORAGE_KEY = 'eyum-char-sheet-v3';
var _csReady = false;
var _csLoading = false;
var _csPageData = [];        // [{canvas, fields:[{name,x,y,w,h,multiline}], width, height}]
var _csFieldValues = {};
var _csSaveTimer = null;

function loadCsData() {
  try {
    var d = JSON.parse(localStorage.getItem(CS_STORAGE_KEY));
    if (d && typeof d === 'object') _csFieldValues = d;
    else _csFieldValues = {};
  } catch(e) { _csFieldValues = {}; }
}

function saveCsData() {
  document.querySelectorAll('.cs-input').forEach(function(el) {
    _csFieldValues[el.name] = el.value;
  });
  localStorage.setItem(CS_STORAGE_KEY, JSON.stringify(_csFieldValues));
}
window.addEventListener('beforeunload', saveCsData);

function autoSaveCs() {
  clearTimeout(_csSaveTimer);
  _csSaveTimer = setTimeout(saveCsData, 400);
}
window.autoSaveCs = autoSaveCs;

window.saveFilledCsPdf = async function() {
  saveCsData();
  try {
    var resp = await fetch('./character-sheet.pdf');
    var buf = new Uint8Array(await resp.arrayBuffer());
    var PDFLib = window.PDFLib;
    if (!PDFLib || !PDFLib.PDFDocument) {
      // Load pdf-lib lazily
      await new Promise(function(ok, fail) {
        var s = document.createElement('script');
        s.src = 'https://unpkg.com/pdf-lib@1.17.1/dist/pdf-lib.min.js';
        s.onload = ok; s.onerror = fail;
        document.head.appendChild(s);
      });
      PDFLib = window.PDFLib;
    }
    var doc = await PDFLib.PDFDocument.load(buf);
    var form = doc.getForm();
    var fields = form.getFields();
    fields.forEach(function(f) {
      var nm = f.getName();
      if (_csFieldValues[nm] !== undefined && f.setText) {
        f.setText(_csFieldValues[nm]);
      }
    });
    var bytes = await doc.save();
    var blob = new Blob([bytes], {type:'application/pdf'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = 'Eyum Character Sheet (Filled).pdf'; a.click();
    setTimeout(function(){ URL.revokeObjectURL(url); }, 5000);
  } catch(e) {
    alert('Failed to save filled PDF: ' + e.message);
  }
};

async function initCs() {
  loadCsData();
  pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js';

  var resp = await fetch('./character-sheet.pdf');
  var buf = await resp.arrayBuffer();
  var pdfDoc = await pdfjsLib.getDocument({data: buf}).promise;
  _csPageData = [];

  for (var pi = 0; pi < pdfDoc.numPages; pi++) {
    var page = await pdfDoc.getPage(pi + 1);
    var viewport = page.getViewport({scale: 1});
    var ph = viewport.height;
    var pw = viewport.width;

    var fields = [];
    try {
      var annots = await page.getAnnotations();
      annots.forEach(function(a) {
        if (a.subtype === 'Widget' && a.fieldType === 'Tx') {
          var r = a.rect;
          fields.push({
            name: a.fieldName,
            x: r[0], y: ph - r[3], w: r[2] - r[0], h: r[3] - r[1],
            multiline: !!(a.fieldFlags & 0x1000)
          });
        }
      });
    } catch(e) {}

    var canvas = document.createElement('canvas');
    canvas.width = pw; canvas.height = ph;
    var ctx = canvas.getContext('2d');
    await page.render({canvasContext: ctx, viewport: viewport}).promise;
    _csPageData.push({canvas: canvas, fields: fields, width: pw, height: ph});
  }
  _csReady = true;
}

function escAttr(s) { return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function buildCsHTML() {
  var html = '<div class="cs-toolbar">';
  html += '<h2>Character Reference</h2>';
  html += '<div class="cs-btns">';
  html += '<a href="./character-sheet.pdf" download class="char-sheet-btn download">Download Blank PDF</a>';
  html += '<button class="char-sheet-btn save" onclick="saveFilledCsPdf()">Save Filled Copy</button>';
  html += '</div>';
  html += '<p class="cs-hint">Fill fields directly below. Your data is saved automatically in your browser and will persist when you navigate away.</p>';
  html += '</div>';
  html += '<div class="cs-container">';

  _csPageData.forEach(function(pd, pi) {
    html += '<div class="cs-page" style="position:relative;width:' + pd.width + 'px;height:' + pd.height + 'px;margin:0 auto 8px auto;">';
    html += '<img src="' + pd.canvas.toDataURL() + '" style="display:block;width:100%;height:100%;" alt="Character Sheet page ' + (pi+1) + '">';
    pd.fields.forEach(function(f) {
      var val = _csFieldValues[f.name] || '';
      var fs = Math.round(Math.min(f.h * 0.65, 14));
      if (f.multiline) {
        html += '<textarea class="cs-input" name="' + f.name + '" oninput="autoSaveCs()" style="position:absolute;left:' + f.x + 'px;top:' + f.y + 'px;width:' + f.w + 'px;height:' + f.h + 'px;font-size:' + fs + 'px;">' + escAttr(val) + '</textarea>';
      } else {
        html += '<input class="cs-input" name="' + f.name + '" value="' + escAttr(val) + '" oninput="autoSaveCs()" style="position:absolute;left:' + f.x + 'px;top:' + f.y + 'px;width:' + f.w + 'px;height:' + f.h + 'px;font-size:' + fs + 'px;">';
      }
    });
    html += '</div>';
  });

  html += '</div>';
  return html;
}

async function renderCharacterSheet() {
  if (_csLoading) return;
  if (!_csReady) {
    _csLoading = true;
    els.content.innerHTML = '<div class="loading">Loading character sheet...</div>';
    try { await initCs(); } catch(e) {
      _csLoading = false;
      els.content.innerHTML = '<div class="error">Failed to load character sheet: ' + e.message + '</div>';
      return;
    }
    _csLoading = false;
  }
  els.content.innerHTML = buildCsHTML();
  els.content.scrollTop = 0;
}

let graphView = null;

function showGraphError(msg) {
  // Show error inside the graph canvas area — don't toggle panel state
  if (!els.graphCanvas) return;
  const old = els.graphCanvas.querySelector('.graph-error-msg');
  if (old) old.remove();
  const div = document.createElement('div');
  div.className = 'graph-error-msg';
  div.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#ff4444;font:13px monospace;padding:24px;text-align:center;white-space:pre-wrap;z-index:10;pointer-events:none;background:rgba(0,0,0,0.85)';
  div.textContent = msg;
  els.graphCanvas.appendChild(div);
  setTimeout(() => div.remove(), 5000);
}

function toggleGraph(manifest) {
  if (!els.graphPanel) return;
  if (!manifest || !manifest.tree) { showGraphError('Manifest not loaded yet.\nWait for page to finish loading.'); return; }
  if (!els.graphPanel.classList.toggle('open')) return; // panel closed

  // Panel just opened
  if (graphView) {
    graphView.currentPath = currentPath;
    if (graphView) graphView.resetView();
    return;
  }

  // First open — create GraphView
  try {
    graphView = new GraphView(els.graphCanvas, manifest, currentPath, (path) => {
      location.hash = encodeURIComponent(path);
      els.graphPanel.classList.remove('open');
    });
    if (!graphView.nodes || graphView.nodes.length === 0) {
      showGraphError('Graph has 0 nodes.\nTree: ' + (manifest.tree ? 'ok' : 'missing') + ' | Edges: ' + (manifest.edges ? manifest.edges.length : 'none'));
      graphView.destroy();
      graphView = null;
      els.graphPanel.classList.remove('open');
    }
  } catch (err) {
    showGraphError('GraphView crashed:\n' + (err.message || String(err)));
    graphView = null;
    els.graphPanel.classList.remove('open');
  }
}

function registerUIEvents() {
  window.addEventListener('hashchange', () => {
    const raw = decodeURIComponent(location.hash.slice(1));
    const [path, fragment] = raw.split('#');
    if (path) loadPage(path, fragment || undefined);
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

  if (els.graphClose) {
    els.graphClose.addEventListener('click', () => { if (els.graphPanel) els.graphPanel.classList.remove('open'); });
  }
  if (els.graphZoomIn) {
    els.graphZoomIn.addEventListener('click', () => { if (graphView) graphView.zoomIn(); });
  }
  if (els.graphZoomOut) {
    els.graphZoomOut.addEventListener('click', () => { if (graphView) graphView.zoomOut(); });
  }
  if (els.graphReset) {
    els.graphReset.addEventListener('click', () => { if (graphView) graphView.resetView(); });
  }
  if (els.prevFile) {
    els.prevFile.addEventListener('click', () => {
      const idx = flatFileList.indexOf(currentPath);
      if (idx > 0) location.hash = encodeURIComponent(flatFileList[idx - 1]);
    });
  }
  if (els.nextFile) {
    els.nextFile.addEventListener('click', () => {
      const idx = flatFileList.indexOf(currentPath);
      if (idx >= 0 && idx < flatFileList.length - 1) location.hash = encodeURIComponent(flatFileList[idx + 1]);
    });
  }

  // Escape key closes graph panel
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && els.graphPanel && els.graphPanel.classList.contains('open')) {
      els.graphPanel.classList.remove('open');
    }
  });
}

async function init() {
  applyTheme(loadTheme());

  // Register UI events first so theme/sidebar controls work even if manifest fails
  registerUIEvents();

  try {
    const manifestRes = await fetch('./manifest.json');
    manifest = await manifestRes.json();
    buildWikiMap(manifest.tree);
    buildFlatList(manifest.tree);
    renderTree(manifest.tree, els.tree);

    const raw = location.hash ? decodeURIComponent(location.hash.slice(1)) : null;
    const [requestedPath, requestedFragment] = raw ? raw.split('#') : [null, null];
    const start = requestedPath || manifest.defaultFile || getDefaultFile(manifest.tree);
    if (start) await loadPage(start, requestedFragment || undefined);
  } catch (err) {
    els.content.innerHTML = `<div class="error">Failed to load site data: ${err.message}</div>`;
  }
}

init();
