const THEME_KEY = 'eyum-theme';
const DEFAULTS = {
  text: '#ffffff',
  bg: '#000000',
  tableHeader: '#161616',
  tableRowA: '#242424',
  tableRowB: '#1d1d1d',
};

const els = {
  tree: document.getElementById('tree'),
  content: document.getElementById('content'),
  breadcrumbs: document.getElementById('breadcrumbs'),
  textColor: document.getElementById('textColor'),
  bgColor: document.getElementById('bgColor'),
  resetTheme: document.getElementById('resetTheme'),
  settingsBtn: document.getElementById('settingsBtn'),
  settingsPanel: document.getElementById('settingsPanel'),
  tableHeaderColor: document.getElementById('tableHeaderColor'),
  tableRowAColor: document.getElementById('tableRowAColor'),
  tableRowBColor: document.getElementById('tableRowBColor'),
  downloadsBtn: document.getElementById('downloadsBtn'),
  downloadsPanel: document.getElementById('downloadsPanel'),
  dlObsidian: document.getElementById('dlObsidian'),
  dlText: document.getElementById('dlText'),
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
  searchWrap: document.getElementById('searchWrap'),
  searchBox: document.getElementById('searchBox'),
  searchInput: document.getElementById('searchInput'),
  searchClear: document.getElementById('searchClear'),
  searchDropdown: document.getElementById('searchDropdown'),
};

let manifest;
let currentPath = null;
let wikiMap = new Map();
let imageMap = new Map();

marked.setOptions({
  gfm: true,
  breaks: false,
  headerIds: true,
  mangle: false,
});

function applyTheme(theme) {
  document.documentElement.style.setProperty('--text', theme.text);
  document.documentElement.style.setProperty('--bg', theme.bg);
  document.documentElement.style.setProperty('--table-header', theme.tableHeader);
  document.documentElement.style.setProperty('--table-row-a', theme.tableRowA);
  document.documentElement.style.setProperty('--table-row-b', theme.tableRowB);
  els.textColor.value = theme.text;
  els.bgColor.value = theme.bg;
  els.tableHeaderColor.value = theme.tableHeader;
  els.tableRowAColor.value = theme.tableRowA;
  els.tableRowBColor.value = theme.tableRowB;
}

function saveTheme(theme) {
  localStorage.setItem(THEME_KEY, JSON.stringify(theme));
}

function loadTheme() {
  try {
    const theme = JSON.parse(localStorage.getItem(THEME_KEY));
    if (theme && typeof theme === 'object') return { ...DEFAULTS, ...theme };
  } catch {}
  return { ...DEFAULTS };
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

function treeCompare(a, b) {
  const baseA = a.name.replace(/\.md$/i, '');
  const baseB = b.name.replace(/\.md$/i, '');
  if (baseA.localeCompare(baseB, undefined, { sensitivity: 'base' }) === 0) {
    return a.type === 'file' ? -1 : 1;
  }
  return baseA.localeCompare(baseB, undefined, { numeric: true, sensitivity: 'base' });
}

function numPrefix(name) {
  const match = name.match(/^\d+(?:\.\d+)*/);
  return match ? match[0] : '';
}

function renderTree(node, container) {
  const sorted = [...(node.children || [])].sort(treeCompare);
  const filePrefixes = sorted
    .filter((c) => c.type === 'file')
    .map((c) => numPrefix(c.name));

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
      const prefix = numPrefix(child.name);
      const isSubfile = prefix.includes('.') && filePrefixes.some(
        (f) => f !== prefix && f.includes('.') && prefix.startsWith(f + '.')
      );
      if (isSubfile) link.style.paddingLeft = '40px';
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

function fixWikiLinks(markdown, pagePath) {
  // Obsidian image embeds: ![[image.png]], ![[image.png|300]], ![[folder/image.png|300x200]]
  markdown = markdown.replace(/!\[\[([^\]]+)\]\]/g, (_, target) => {
    const parts = target.split('|');
    const raw = parts[0].trim();
    if (!IMAGE_EXTS_RE.test(raw)) {
      // Not an image embed (embedded note) - fall back to a normal wiki link
      return '[[' + target + ']]';
    }
    const src = resolveImageSrc(raw, pagePath);
    const size = parts.length > 1 ? parts[1].trim() : '';
    if (size) {
      const m = size.match(/^(\d+)(?:x(\d+))?$/);
      if (m) {
        return '<img src="' + src + '" width="' + m[1] + '"' + (m[2] ? ' height="' + m[2] + '"' : '') + ' alt="' + raw + '">';
      }
    }
    return '![' + raw + '](' + src + ')';
  });

  return markdown.replace(/\[\[([^\]]+)\]\]/g, (_, target) => {
    const parts = target.split('|');
    const raw = parts[0].trim();
    const display = parts.length > 1 ? parts[1].trim() : raw;
    const hashIdx = raw.indexOf('#');
    const pageName = hashIdx >= 0 ? raw.slice(0, hashIdx).trim() : raw;
    const fragment = hashIdx >= 0 ? raw.slice(hashIdx + 1).trim() : null;
    let mapped = wikiMap.get(slugifyTitle(pageName));
    if (!mapped && pageName.includes('/')) {
      mapped = wikiMap.get(slugifyTitle(pageName.split('/').pop()));
    }
    if (!mapped) return display;
    const url = `#${encodeURIComponent(mapped)}`;
    const fullUrl = fragment ? url + '%23' + slugifyFragment(fragment) : url;
    return `[${display}](${fullUrl})`;
  });
}

const IMAGE_EXTS_RE = /\.(png|jpe?g|gif|webp|svg|bmp|avif)$/i;

function resolveImageSrc(target, pagePath) {
  // Try the image map first (bare filename or full vault path), then fall back
  // to a path relative to the current page's folder.
  const lower = target.toLowerCase();
  if (imageMap.has(lower)) return './content/' + imageMap.get(lower);
  if (target.includes('/')) return './content/' + target;
  const dir = pagePath.includes('/') ? pagePath.split('/').slice(0, -1).join('/') : '';
  return './content/' + (dir ? dir + '/' : '') + target;
}

function fixImageSrcs(markdown, pagePath) {
  // Standard markdown images: ![](relative/path.png) - resolve against the site
  // content folder. Absolute/external/data URLs are left alone.
  return markdown.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, src) => {
    const s = src.trim();
    if (/^(https?:|data:|\/\/|\/|#|\.\/content\/)/i.test(s)) return '![' + alt + '](' + s + ')';
    if (!IMAGE_EXTS_RE.test(s.split(/[?#]/)[0])) return '![' + alt + '](' + s + ')';
    return '![' + alt + '](' + resolveImageSrc(s, pagePath) + ')';
  });
}

function slugifyFragment(text) {
  return text.toLowerCase().replace(/[^\w]+/g, '-').replace(/^-+|-+$/g, '');
}

// marked's GFM table parser treats any non-empty line directly after a table as
// a table row. Make sure tables are always terminated by a blank line so notes
// and paragraphs after a table are not swallowed into it.
const TABLE_ROW = /^\s*\|/;
const TABLE_SEP = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;
const BLOCK_START = /^(\s{0,3}#|\s*>|\s*```|\s*~~~|\s*[-*+]\s|\s*\d+[.)]\s|\s{0,3}(-{3,}|\*{3,}|_{3,})\s*$| {4}\S)/;

function guardTableBorders(markdown) {
  const lines = markdown.split('\n');
  const out = [];
  let inTable = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (inTable && line.trim() !== '') {
      const next = i + 1 < lines.length ? lines[i + 1] : '';
      const gluedTable = TABLE_ROW.test(line) && TABLE_SEP.test(next);
      const stillTable = TABLE_ROW.test(line) || (line.includes('|') && !BLOCK_START.test(line));
      if (!stillTable || gluedTable) {
        out.push('');
        inTable = false;
      }
    }
    if (!inTable && TABLE_ROW.test(line)) {
      const next = i + 1 < lines.length ? lines[i + 1] : '';
      if (TABLE_SEP.test(next)) inTable = true;
    }
    if (inTable && line.trim() === '') inTable = false;
    out.push(line);
  }
  return out.join('\n');
}

async function loadPage(path, scrollToId) {
  // A real page is being shown — the search page (if any) is done, so clear its
  // ?search= URL param without triggering navigation events.
  searchPageActive = false;
  if (location.search) {
    history.replaceState(null, '', location.pathname + location.hash);
  }

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
    markdown = fixWikiLinks(markdown, path);
    markdown = fixImageSrcs(markdown, path);
    markdown = guardTableBorders(markdown);
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
const CS_STORAGE_KEY = 'eyum-char-sheet-filled';
var _csReady = false;
var _csLoading = false;
var _csPageData = [];        // [{canvas, fields:[{name,x,y,w,h,multiline}], width, height}]
var _csFieldValues = {};
var _csSaveTimer = null;

function loadCsData() {
  try {
    var d = JSON.parse(localStorage.getItem(CS_STORAGE_KEY));
    if (!d || typeof d !== 'object') {
      // Migrate once from an older versioned key (eyum-char-sheet-v3, v4, ...).
      // Take the highest version found and store it under the new stable key.
      var bestKey = null, bestV = -1;
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        var m = k && k.match(/^eyum-char-sheet-v(\d+)$/);
        if (m) {
          var v = parseInt(m[1], 10);
          if (v > bestV) { bestV = v; bestKey = k; }
        }
      }
      if (bestKey) {
        d = JSON.parse(localStorage.getItem(bestKey));
        localStorage.setItem(CS_STORAGE_KEY, localStorage.getItem(bestKey));
      }
    }
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
    html += '<img class="cs-page-img" src="' + pd.canvas.toDataURL() + '" style="display:block;width:100%;height:100%;" alt="Character Sheet page ' + (pi+1) + '">';
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

// ========== HANDBOOK DOWNLOADS ==========
function collectHandbookFiles(node, acc) {
  if (node.type === 'file') { acc.push(node.path); return; }
  for (const child of node.children || []) collectHandbookFiles(child, acc);
}

let jsZipPromise = null;
function loadJSZip() {
  if (!jsZipPromise) {
    jsZipPromise = new Promise((resolve, reject) => {
      if (window.JSZip) return resolve(window.JSZip);
      const s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js';
      s.onload = () => resolve(window.JSZip);
      s.onerror = () => reject(new Error('Could not load JSZip'));
      document.head.appendChild(s);
    });
  }
  return jsZipPromise;
}

async function downloadHandbook(mode) {
  const btn = mode === 'text' ? els.dlText : els.dlObsidian;
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Preparing...';
  try {
    const paths = [];
    collectHandbookFiles(manifest.tree, paths);
    if (mode === 'text') {
      const parts = ['EYUM TTRPG - COMPLETE HANDBOOK\n'];
      for (const path of paths) {
        const res = await fetch(`./content/${path}`);
        if (!res.ok) continue;
        parts.push('\n======================================================================\n  MARKDOWN: ' + path + '\n======================================================================\n\n' + await res.text() + '\n');
      }
      const blob = new Blob(parts, { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Eyum-TTRPG-Handbook.txt';
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } else {
      const JSZip = await loadJSZip();
      const zip = new JSZip();
      for (const path of paths) {
        const res = await fetch(`./content/${path}`);
        if (!res.ok) continue;
        zip.file(path, await res.text());
      }
      const blob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Eyum-TTRPG-Handbook-Obsidian.zip';
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    }
  } catch (err) {
    alert('Download failed: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
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

  [els.textColor, els.bgColor, els.tableHeaderColor, els.tableRowAColor, els.tableRowBColor].forEach((input) => {
    input.addEventListener('input', () => {
      const theme = {
        text: els.textColor.value,
        bg: els.bgColor.value,
        tableHeader: els.tableHeaderColor.value,
        tableRowA: els.tableRowAColor.value,
        tableRowB: els.tableRowBColor.value,
      };
      applyTheme(theme);
      saveTheme(theme);
    });
  });

  els.settingsBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    els.settingsPanel.classList.toggle('open');
  });

  els.downloadsBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    els.downloadsPanel.classList.toggle('open');
  });

  document.addEventListener('click', (e) => {
    if (els.settingsPanel.classList.contains('open') &&
        !els.settingsPanel.contains(e.target) && !els.settingsBtn.contains(e.target)) {
      els.settingsPanel.classList.remove('open');
    }
    if (els.downloadsPanel.classList.contains('open') &&
        !els.downloadsPanel.contains(e.target) && !els.downloadsBtn.contains(e.target)) {
      els.downloadsPanel.classList.remove('open');
    }
  });

  els.dlObsidian.addEventListener('click', () => downloadHandbook('md'));
  els.dlText.addEventListener('click', () => downloadHandbook('text'));

  els.resetTheme.addEventListener('click', () => {
    applyTheme(DEFAULTS);
    saveTheme(DEFAULTS);
    els.settingsPanel.classList.remove('open');
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

  // Escape key closes graph panel, settings panel, and downloads panel
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (els.graphPanel && els.graphPanel.classList.contains('open')) {
      els.graphPanel.classList.remove('open');
    }
    if (els.settingsPanel && els.settingsPanel.classList.contains('open')) {
      els.settingsPanel.classList.remove('open');
    }
    if (els.downloadsPanel && els.downloadsPanel.classList.contains('open')) {
      els.downloadsPanel.classList.remove('open');
    }
  });

  initSearchUI();
}

async function init() {
  applyTheme(loadTheme());

  // Register UI events first so theme/sidebar controls work even if manifest fails
  registerUIEvents();

  try {
    const manifestRes = await fetch('./manifest.json');
    manifest = await manifestRes.json();
    imageMap = new Map(Object.entries(manifest.images || {}));
    buildWikiMap(manifest.tree);
    buildFlatList(manifest.tree);
    renderTree(manifest.tree, els.tree);

    const raw = location.hash ? decodeURIComponent(location.hash.slice(1)) : null;
    const [requestedPath, requestedFragment] = raw ? raw.split('#') : [null, null];

    // Build the search index in the background (runtime-generated so it is
    // always fresh against the current content — never hardcoded).
    startSearchIndex();

    // A ?search= URL opens the search page directly (so users can share/edit
    // search URLs). Otherwise load the requested/default page as usual.
    const urlSearch = getSearchParam();
    if (urlSearch) {
      showSearchPage(urlSearch);
    } else {
      const start = requestedPath || manifest.defaultFile || getDefaultFile(manifest.tree);
      if (start) await loadPage(start, requestedFragment || undefined);
    }
  } catch (err) {
    els.content.innerHTML = `<div class="error">Failed to load site data: ${err.message}</div>`;
  }
}

// ==================== SEARCH ====================
// The search index is generated at runtime from manifest.json + freshly
// fetched content files on every page load, so it always reflects the current
// handbook content. Nothing in this section is hardcoded or pre-generated.

let searchPageActive = false;
let currentSearchTerm = null;
let searchIndexPromise = null;
let searchIndex = null; // { files, glossary, glossaryPath, wordFiles, docCount }
let searchDebounce = null;
let searchSelIdx = -1;
let searchDropdownItems = [];

const GLOSSARY_MIN = 650;
const PAGE_MIN = 600;
const HEADING_MIN = 650;
const CONTENT_CAP = 50;
const HEADING_CAP = 60;

function escHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function escRe(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function normText(s) {
  return String(s || '').toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim();
}

function singularize(w) {
  if (w.length <= 3) return w;
  if (w.endsWith('ies')) return w.slice(0, -3) + 'y';
  if (w.endsWith('ches') || w.endsWith('shes') || w.endsWith('xes') || w.endsWith('zes') || w.endsWith('ses')) return w.slice(0, -2);
  if (w.endsWith('s') && !w.endsWith('ss') && !w.endsWith('us') && !w.endsWith('is')) return w.slice(0, -1);
  return w;
}

function lev(a, b, max) {
  if (a === b) return 0;
  const la = a.length, lb = b.length;
  if (Math.abs(la - lb) > max) return max + 1;
  let v0 = new Array(lb + 1), v1 = new Array(lb + 1);
  for (let j = 0; j <= lb; j++) v0[j] = j;
  for (let i = 1; i <= la; i++) {
    v1[0] = i;
    let rowMin = v1[0];
    const ca = a.charCodeAt(i - 1);
    for (let j = 1; j <= lb; j++) {
      const cost = ca === b.charCodeAt(j - 1) ? 0 : 1;
      const m = Math.min(v0[j] + 1, v1[j - 1] + 1, v0[j - 1] + cost);
      v1[j] = m;
      if (m < rowMin) rowMin = m;
    }
    if (rowMin > max) return max + 1;
    const tmp = v0; v0 = v1; v1 = tmp;
  }
  return v0[lb];
}

// Score a normalized query against a normalized target string. Higher is
// better. Tiers: exact > prefix > suffix > substring > whole-word > word
// prefix > acronym > ordered multi-token > edit-distance (typos).
function matchScore(q, t) {
  if (!q || !t) return 0;
  const qw = q.split(' ');
  const tw = t.split(' ').filter(Boolean);
  if (t === q) return 1000;
  if (t.startsWith(q)) return 920 - Math.min(60, t.length - q.length);
  if (t.endsWith(q)) return 885;
  if (t.includes(q)) return 860;
  if (tw.includes(q)) return 840;
  for (const w of tw) if (w.startsWith(q)) return 805;
  if (tw.length >= 2 && q.length >= 2) {
    const initials = tw.map((w) => w[0]).join('');
    if (initials === q) return 780;
    if (initials.startsWith(q)) return 765;
  }
  if (qw.length > 1) {
    let all = true;
    for (const tok of qw) {
      let found = false;
      for (const w of tw) {
        if (w.startsWith(tok)) { found = true; break; }
      }
      if (!found) { all = false; break; }
    }
    if (all) return t.includes(q) ? 830 : 725;
  }
  if (q.length >= 3) {
    const maxWhole = q.length <= 6 ? 2 : 3;
    if (t.length <= 60) {
      const d = lev(q, t, maxWhole);
      if (d <= maxWhole) return Math.max(0, 700 - d * 18 - Math.max(0, t.length - q.length) * 0.5);
    }
    const maxWord = q.length <= 4 ? 1 : 2;
    let best = 0;
    for (const w of tw) {
      const d = lev(q, w, maxWord);
      if (d <= maxWord) {
        const s = 690 - d * 25 - Math.abs(w.length - q.length) * 2;
        if (s > best) best = s;
      }
    }
    return best;
  }
  return 0;
}

// ---- URL handling: ?search=<term> opens the search page ----
function getSearchParam() {
  try {
    const q = new URLSearchParams(location.search).get('search');
    return q ? q.trim().slice(0, 120) : null;
  } catch { return null; }
}

function setSearchParam(term, replace) {
  const url = term
    ? location.pathname + '?search=' + encodeURIComponent(term)
    : location.pathname;
  if (replace) history.replaceState(null, '', url);
  else history.pushState(null, '', url);
}

// ---- Runtime index builder ----
function startSearchIndex() {
  if (searchIndexPromise) return searchIndexPromise;
  searchIndexPromise = buildSearchIndex()
    .then((idx) => {
      searchIndex = idx;
      // Refresh a dropdown that was opened while indexing
      if (els.searchDropdown && els.searchDropdown.classList.contains('open')) {
        renderSearchDropdown((els.searchInput && els.searchInput.value || '').trim());
      }
      return idx;
    })
    .catch((err) => {
      console.error('Search index build failed:', err);
      if (els.searchDropdown && els.searchDropdown.classList.contains('open')) {
        els.searchDropdown.innerHTML = '<div class="sd-note">Search index failed to build.</div>';
      }
      return null;
    });
  return searchIndexPromise;
}

async function waitForIndex() {
  if (searchIndex) return true;
  if (!manifest) return false;
  try { await startSearchIndex(); return !!searchIndex; } catch { return false; }
}

function stripMd(md) {
  return md
    .replace(/```[\s\S]*?(?:```|$)/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!\[\[[^\]]*\]\]/g, ' ')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[\[([^\]|#]*)(?:#[^\]]*)?(?:\|[^\]]*)?\]\]/g, '$1')
    .replace(/\[([^\]]*)\]\(([^)]*)\)/g, '$1')
    .replace(/<[^>]+>/g, ' ')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/\|/g, ' ')
    .replace(/^[ \t]*>+\s?/gm, ' ')
    .replace(/^[ \t]*([-*+]|\d+[.)])\s+/gm, ' ')
    .replace(/^\s{0,3}([-*_])(\s*\1){2,}\s*$/gm, ' ')
    .replace(/[*_~]{1,3}/g, '')
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/\n{3,}/g, '\n\n');
}

function extractHeadings(md, plain) {
  const out = [];
  const re = /^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/gm;
  let m;
  let searchFrom = 0;
  while ((m = re.exec(md)) !== null) {
    const text = stripInline(m[2].trim());
    if (!text) continue;
    const pos = plain.indexOf(text, searchFrom);
    if (pos >= 0) searchFrom = pos + text.length;
    out.push({ text, norm: normText(text), id: slugifyFragment(text), pos: pos >= 0 ? pos : -1 });
  }
  return out;
}

function stripInline(s) {
  return String(s)
    .replace(/!\[\[[^\]]*\]\]/g, ' ')
    .replace(/\[\[([^\]]*)\]\]/g, (m, inner) => {
      const parts = inner.split('|');
      let raw = parts[0].trim();
      const hash = raw.indexOf('#');
      if (hash >= 0) raw = raw.slice(0, hash);
      return raw;
    })
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/<[^>]+>/g, ' ')
    .replace(/[*_~`]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function splitTableRow(line) {
  const cells = [];
  let cur = '', depth = 0, i = 0;
  const s = line.trim();
  const end = s.endsWith('|') ? s.length - 1 : s.length;
  while (i < end) {
    const ch = s[i];
    if (ch === '[' && s[i + 1] === '[') { cur += ch + s[i + 1]; i += 2; depth++; continue; }
    if (ch === ']' && s[i + 1] === ']' && depth > 0) { cur += ch + s[i + 1]; i += 2; depth--; continue; }
    if (ch === '|' && depth === 0) { cells.push(cur.trim()); cur = ''; i++; continue; }
    cur += ch; i++;
  }
  cells.push(cur.trim());
  return cells;
}

function extractWikiRefs(s) {
  const refs = [];
  const re = /\[\[([^\]]+)\]\]/g;
  let m;
  while ((m = re.exec(s)) !== null) {
    const parts = m[1].split('|');
    const raw = parts[0].trim();
    const hash = raw.indexOf('#');
    const label = (hash >= 0 ? raw.slice(0, hash) : raw).trim();
    const frag = hash >= 0 ? raw.slice(hash + 1).trim() : null;
    refs.push({
      label,
      path: wikiMap.get(slugifyTitle(label)) || null,
      frag: frag ? slugifyFragment(frag) : null,
    });
  }
  return refs;
}

function parseGlossary(md) {
  const entries = [];
  const lines = md.split('\n');
  let category = 'Glossary';
  let inDefTable = false;
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { inDefTable = false; continue; }
    const cat = line.match(/^#{4}\s+(.+)$/);
    if (cat) { category = stripInline(cat[1]); inDefTable = false; continue; }
    if (/^#{1,3}\s/.test(line)) { inDefTable = false; continue; }
    if (!line.startsWith('|')) { inDefTable = false; continue; }
    const cells = splitTableRow(line);
    while (cells.length && !cells[0]) cells.shift();
    if (cells.length < 2) continue;
    const header = cells.map((c) => normText(stripInline(c)));
    if (header.includes('term') && header.includes('definition')) { inDefTable = true; continue; }
    if (!inDefTable) continue;
    const term = stripInline(cells[0]);
    if (!term || /^[-:]+$/.test(term)) continue;
    const definition = stripInline(cells[1]);
    const refs = [];
    for (const cell of cells.slice(2)) refs.push(...extractWikiRefs(cell));
    entries.push({
      term,
      termNorm: normText(term),
      aliasNorm: normText(term.replace(/\([^)]*\)/g, '')),
      definition,
      category,
      refs,
    });
  }
  return entries;
}

function countOccurrences(hay, needle) {
  if (!hay || !needle) return 0;
  let n = 0, i = 0;
  while ((i = hay.indexOf(needle, i)) !== -1) {
    n++;
    i += needle.length;
  }
  return n;
}

function editCandidates1(w) {
  const out = new Set();
  const letters = 'abcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < w.length; i++) out.add(w.slice(0, i) + w.slice(i + 1));
  for (let i = 0; i < w.length - 1; i++) out.add(w.slice(0, i) + w[i + 1] + w[i] + w.slice(i + 2));
  for (let i = 0; i < w.length; i++) for (const c of letters) out.add(w.slice(0, i) + c + w.slice(i + 1));
  for (let i = 0; i <= w.length; i++) for (const c of letters) out.add(w.slice(0, i) + c + w.slice(i));
  return out;
}

// SymSpell-style expansion: return dictionary words within a small edit
// distance of the token, sorted by distance then popularity.
function expandToken(tok) {
  const dict = searchIndex.wordFiles;
  const found = new Map();
  for (const c of editCandidates1(tok)) {
    if (dict.has(c)) found.set(c, 1);
  }
  if (!found.size && tok.length >= 5 && tok.length <= 10) {
    let outer = 0;
    for (const c of editCandidates1(tok)) {
      if (++outer > 40) break;
      for (const c2 of editCandidates1(c)) {
        if (dict.has(c2) && !found.has(c2)) found.set(c2, 2);
      }
    }
  }
  return [...found.entries()].map(([w, d]) => ({ w, d, pop: dict.get(w).size, set: dict.get(w) }));
}

function isGlossaryExact(g, qNorm, qSing) {
  for (const k of [g.termNorm, g.aliasNorm]) {
    if (!k) continue;
    if (k === qNorm) return true;
    if (qNorm.length >= 4 && singularize(k) === qSing) return true;
    const words = k.split(' ');
    // Terminal word matches the query: catches parenthetical abbreviations
    // like (DC), (Ap), (HP) even for 2-3 char queries.
    if (qNorm.length >= 2 && words[words.length - 1] === qNorm) return true;
    if (qNorm.length >= 3) {
      for (const w of words) {
        if (w === qNorm || (qNorm.length >= 4 && singularize(w) === qSing)) return true;
      }
    }
  }
  return false;
}

function buildSnippets(f, tokens, qNorm) {
  const hay = f.text;
  const lower = hay.toLowerCase();
  const wins = [];
  let idx = -1;
  let firstIdx = -1;
  let guard = 0;
  let tok = null;
  for (const t of tokens) {
    if (lower.indexOf(t) !== -1) { tok = t; break; }
  }
  if (!tok) {
    // All tokens were matched via fuzzy expansion — search normalized text
    tok = tokens[0];
    const t = f.textNorm;
    idx = t.indexOf(tok);
    if (idx === -1) return { snippet: null, frag: null };
    const start = Math.max(0, idx - 90);
    wins.push(t.slice(start, Math.min(t.length, idx + tok.length + 130)).trim());
    return { snippet: wins.join(' … '), frag: null };
  }
  while (wins.length < 3 && guard++ < 300) {
    idx = lower.indexOf(tok, idx + 1);
    if (idx === -1) break;
    if (firstIdx === -1) firstIdx = idx;
    const start = Math.max(0, idx - 90);
    const end = Math.min(hay.length, idx + tok.length + 130);
    wins.push(hay.slice(start, end).replace(/\s+/g, ' ').trim());
  }
  let frag = null;
  if (firstIdx !== -1) {
    for (let i = f.headings.length - 1; i >= 0; i--) {
      if (f.headings[i].pos >= 0 && f.headings[i].pos <= firstIdx) { frag = f.headings[i].id; break; }
    }
  }
  return { snippet: wins.join(' … '), frag };
}

async function buildSearchIndex() {
  const paths = [];
  collectHandbookFiles(manifest.tree, paths);
  const glossaryPath = paths.find((p) => /glossary\.md$/i.test(p)) || null;
  const docs = new Array(paths.length);
  let next = 0;
  const CONC = 8;
  async function worker() {
    while (next < paths.length) {
      const i = next++;
      const p = paths[i];
      let md = '';
      try {
        const res = await fetch('./content/' + p);
        if (res.ok) md = await res.text();
      } catch { /* keep empty */ }
      docs[i] = { path: p, md };
    }
  }
  await Promise.all(Array.from({ length: Math.min(CONC, paths.length) }, worker));

  const files = [];
  const wordFiles = new Map(); // word -> Set(fileIdx)
  for (let i = 0; i < docs.length; i++) {
    const d = docs[i];
    const name = d.path.replace(/\.md$/i, '').split('/').pop();
    const text = stripMd(d.md);
    const textNorm = normText(text);
    const headings = extractHeadings(d.md, text);
    files.push({
      path: d.path,
      name,
      nameNorm: normText(name),
      section: getSection(d.path),
      text,
      textNorm,
      headings,
    });
    const seen = new Set();
    for (const w of textNorm.split(' ')) {
      if (w.length < 3 || seen.has(w)) continue;
      seen.add(w);
      let set = wordFiles.get(w);
      if (!set) { set = new Set(); wordFiles.set(w, set); }
      set.add(i);
    }
  }

  let glossary = [];
  if (glossaryPath) {
    const doc = docs.find((d) => d.path === glossaryPath);
    if (doc) glossary = parseGlossary(doc.md);
  }
  return { files, glossary, glossaryPath, wordFiles, docCount: files.length };
}

// ---- Query engine ----
function runSearch(query, opts = {}) {
  const q = (query || '').trim().slice(0, 120);
  const qNorm = normText(q);
  const tokens = qNorm ? qNorm.split(' ').filter(Boolean) : [];
  const empty = {
    query: q, tokens,
    glossary: [], pages: [], headings: [], content: [],
    suggestions: [], contentTruncated: false,
    counts: { glossary: 0, pages: 0, headings: 0, content: 0 },
  };
  if (!tokens.length || !searchIndex) return empty;

  const res = {
    query: q, tokens,
    glossary: [], pages: [], headings: [], content: [],
    suggestions: [], contentTruncated: false,
    counts: { glossary: 0, pages: 0, headings: 0, content: 0 },
  };
  const qSing = singularize(qNorm);
  const shortQuery = qNorm.length < 3;
  const expandedByToken = new Map();

  // Glossary
  for (const g of searchIndex.glossary) {
    const exact = isGlossaryExact(g, qNorm, qSing);
    let s = Math.max(matchScore(qNorm, g.termNorm), matchScore(qNorm, g.aliasNorm));
    if (s < GLOSSARY_MIN) {
      s = Math.max(s, matchScore(qSing, singularize(g.termNorm)), matchScore(qSing, singularize(g.aliasNorm)));
    }
    if (exact || s >= GLOSSARY_MIN) {
      res.glossary.push({ term: g.term, definition: g.definition, category: g.category, refs: g.refs, score: s, exact });
    }
  }
  res.glossary.sort((a, b) => (b.exact - a.exact) || (b.score - a.score) || (a.term.length - b.term.length));
  res.counts.glossary = res.glossary.length;

  const glossHas = res.glossary.length > 0;
  const glossPath = searchIndex.glossaryPath;

  // Pages / file names
  for (const f of searchIndex.files) {
    const s = matchScore(qNorm, f.nameNorm);
    if (s >= PAGE_MIN) res.pages.push({ path: f.path, name: f.name, score: s });
  }
  res.pages.sort((a, b) => b.score - a.score || (a.name.length - b.name.length));
  res.counts.pages = res.pages.length;

  // Headings
  for (const f of searchIndex.files) {
    if (glossHas && f.path === glossPath) continue;
    for (const h of f.headings) {
      const s = matchScore(qNorm, h.norm);
      if (s >= HEADING_MIN) res.headings.push({ path: f.path, page: f.name, text: h.text, frag: h.id, score: s });
    }
  }
  res.headings.sort((a, b) => b.score - a.score || (a.text.length - b.text.length));
  res.counts.headings = res.headings.length;
  if (opts.dropdown) res.headings = res.headings.slice(0, 4);
  else if (res.headings.length > HEADING_CAP) res.headings = res.headings.slice(0, HEADING_CAP);

  // In-text matches (skipped for very short queries to avoid noise)
  if (!shortQuery) {
    const files = searchIndex.files;
    const acc = new Map(); // fileIdx -> {score, direct}
    const addScore = (i, s, d) => {
      let e = acc.get(i);
      if (!e) { e = { score: 0, direct: 0 }; acc.set(i, e); }
      e.score += s;
      if (d) e.direct += d;
    };
    for (const t of tokens) {
      let anyDirect = false;
      for (let i = 0; i < files.length; i++) {
        const c = countOccurrences(files[i].textNorm, t);
        if (c > 0) { anyDirect = true; addScore(i, c * 5, c); }
      }
      if (!anyDirect) {
        const cands = expandToken(t).sort((a, b) => a.d - b.d || (b.pop - a.pop));
        if (cands.length) {
          const best = cands[0];
          expandedByToken.set(t, best);
          if (best.d === 1) res.suggestions.push({ from: t, to: best.w });
          const mult = best.d === 1 ? 0.55 : 0.25;
          for (const i of best.set) {
            const c = countOccurrences(files[i].textNorm, best.w);
            if (c > 0) addScore(i, c * 5 * mult, 0);
          }
        }
      }
    }
    for (let i = 0; i < files.length; i++) {
      const pc = countOccurrences(files[i].textNorm, qNorm);
      if (pc > 0) addScore(i, pc * 25, pc);
    }
    const directTokens = tokens.length - expandedByToken.size;
    for (const [i, e] of acc) {
      if (glossHas && files[i].path === glossPath) { acc.delete(i); continue; }
      if (e.score <= 0) { acc.delete(i); continue; }
      if (tokens.length > 1 && directTokens < tokens.length) {
        e.score = Math.floor(e.score * (0.4 + 0.6 * directTokens / tokens.length));
      }
    }
    const entries = [...acc.entries()]
      .map(([i, e]) => ({ i, score: e.score, count: e.direct }))
      .sort((a, b) => b.score - a.score);
    res.counts.content = entries.length;
    const cap = opts.dropdown ? 3 : CONTENT_CAP;
    res.contentTruncated = entries.length > cap;
    for (const en of entries.slice(0, cap)) {
      const f = files[en.i];
      const { snippet, frag } = buildSnippets(f, tokens, qNorm);
      res.content.push({ path: f.path, page: f.name, score: en.score, count: en.count, snippet, frag });
    }
    res.suggestions = res.suggestions.slice(0, 5);
  }
  return res;
}

// ---- Shared rendering helpers ----
function highlightHTML(text, tokens) {
  const esc = escHtml(text);
  if (!tokens || !tokens.length) return esc;
  const parts = tokens.filter(Boolean).map(escRe);
  if (!parts.length) return esc;
  return esc.replace(new RegExp('(' + parts.join('|') + ')', 'gi'), '<mark class="search-hl">$1</mark>');
}

function groupHeader(title, n) {
  return '<div class="sp-group-title"><h2>' + escHtml(title) + '</h2><span>' + n + ' result' + (n === 1 ? '' : 's') + '</span></div>';
}

function glossaryBubbleHTML(g, tokens, compact) {
  const cls = compact ? 'sd-gloss' : 'sp-gloss';
  const def = g.definition.length > 420 ? g.definition.slice(0, 420) + '…' : g.definition;
  const refs = g.refs.filter((r) => r.path).slice(0, 3);
  const refsHtml = refs.length
    ? '<div class="sd-gloss-refs">' + refs.map((r) =>
        '<a class="sd-ref" data-path="' + escAttr(r.path) + '" data-frag="' + escAttr(r.frag || '') + '" href="#' + encodeURIComponent(r.path) + (r.frag ? '#' + r.frag : '') + '">' + escHtml(r.label) + '</a>'
      ).join('') + '</div>'
    : '';
  return '<div class="' + cls + '"><div class="sd-gloss-term">' + escHtml(g.term)
    + ' <span class="sd-gloss-cat">' + escHtml(g.category) + '</span></div>'
    + '<div class="sd-gloss-def">' + highlightHTML(def, tokens) + '</div>'
    + refsHtml + '</div>';
}

function renderSearchResultsHTML(res) {
  const parts = [];
  const total = res.counts.glossary + res.counts.pages + res.counts.headings + res.counts.content;
  if (total === 0) {
    parts.push('<div class="sp-empty">No results for “' + escHtml(res.query) + '”.</div>');
    if (res.suggestions.length) {
      parts.push('<div class="sp-empty-sugg">Did you mean: ');
      for (const s of res.suggestions.slice(0, 5)) {
        parts.push('<button class="sd-sugg" data-sugg="' + escAttr(s.to) + '">' + escHtml(s.to) + '</button> ');
      }
      parts.push('</div>');
    }
  }
  if (res.glossary.length) {
    parts.push(groupHeader('Glossary', res.counts.glossary));
    for (const g of res.glossary) parts.push(glossaryBubbleHTML(g, res.tokens, false));
  }
  if (res.pages.length) {
    parts.push(groupHeader('Chapters & Pages', res.counts.pages));
    for (const p of res.pages) {
      parts.push('<a class="sp-row" data-path="' + escAttr(p.path) + '" data-frag="" href="#' + encodeURIComponent(p.path) + '">'
        + '<div class="sp-row-main">' + highlightHTML(p.name, res.tokens) + '</div>'
        + '<div class="sp-row-sub">' + escHtml(p.path) + '</div></a>');
    }
  }
  if (res.headings.length) {
    parts.push(groupHeader('Headings', res.counts.headings));
    for (const h of res.headings) {
      const href = '#' + encodeURIComponent(h.path) + (h.frag ? '#' + h.frag : '');
      parts.push('<a class="sp-row" data-path="' + escAttr(h.path) + '" data-frag="' + escAttr(h.frag || '') + '" href="' + escAttr(href) + '">'
        + '<div class="sp-row-main">' + highlightHTML(h.text, res.tokens) + '</div>'
        + '<div class="sp-row-sub">' + escHtml(h.page) + ' — ' + escHtml(h.path) + '</div></a>');
    }
  }
  if (res.content.length) {
    parts.push(groupHeader('In Text', res.counts.content));
    for (const c of res.content) {
      const href = '#' + encodeURIComponent(c.path) + (c.frag ? '#' + c.frag : '');
      parts.push('<a class="sp-row" data-path="' + escAttr(c.path) + '" data-frag="' + escAttr(c.frag || '') + '" href="' + escAttr(href) + '">'
        + '<div class="sp-row-main">' + escHtml(c.page) + '</div>'
        + (c.snippet ? '<div class="sp-snippet">…' + highlightHTML(c.snippet, res.tokens) + '…</div>' : '')
        + '<div class="sp-row-sub">' + escHtml(c.path) + '</div></a>');
    }
    if (res.contentTruncated) {
      parts.push('<div class="sp-hint">Showing the top ' + res.content.length + ' in-text matches. Refine your query to narrow results.</div>');
    }
  }
  return parts.join('');
}

// ---- Full search page (rendered in the main content area) ----
function buildSearchPageFrame(q) {
  return '<div class="search-page">'
    + '<div class="sp-header">'
    + '<div class="sp-box"><span class="search-icon" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"></circle><line x1="21" y1="21" x2="16.2" y2="16.2"></line></svg></span>'
    + '<input id="spInput" class="sp-input" type="text" value="' + escAttr(q) + '" placeholder="Search the handbook…" autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="Search the handbook" />'
    + '<button id="spClear" class="search-clear" title="Clear search" aria-label="Clear search">✕</button>'
    + '</div>'
    + '<div class="sp-meta" id="spMeta"></div>'
    + '<div class="sp-hint">Matches update as you type · press Enter to jump to the first result</div>'
    + '</div>'
    + '<div id="spResults" class="sp-results"></div>'
    + '</div>';
}

function navigateSearchResult(path, frag) {
  if (!path) return;
  hideSearchDropdown();
  location.hash = encodeURIComponent(path) + (frag ? '#' + frag : '');
}

async function updateSearchPageResults(q) {
  const meta = document.getElementById('spMeta');
  const results = document.getElementById('spResults');
  if (!results) return;
  results.innerHTML = '<div class="loading">Searching…</div>';
  const ok = await waitForIndex();
  if (!ok) {
    results.innerHTML = '<div class="error">The search index failed to build. Reload the page to retry.</div>';
    return;
  }
  const res = runSearch(q, {});
  const total = res.counts.glossary + res.counts.pages + res.counts.headings + res.counts.content;
  if (meta) meta.textContent = total === 0
    ? 'No results'
    : total + ' result' + (total === 1 ? '' : 's') + ' for “' + q + '”';
  results.innerHTML = renderSearchResultsHTML(res);
}

function bindSearchPageEvents() {
  const input = document.getElementById('spInput');
  const clear = document.getElementById('spClear');
  const results = document.getElementById('spResults');
  if (!input || !results) return;
  let timer = null;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const q = input.value.trim();
      currentSearchTerm = q;
      if (q) {
        setSearchParam(q, true);
        setBreadcrumbs('Search: "' + q + '"');
        document.title = 'Search: ' + q + ': Eyum TTRPG';
        updateSearchPageResults(q);
      } else {
        setSearchParam('', true);
        setBreadcrumbs('Search');
        document.title = 'Search: Eyum TTRPG';
        if (results) results.innerHTML = '<div class="sp-empty">Type a query to search the whole handbook.</div>';
        const meta = document.getElementById('spMeta');
        if (meta) meta.textContent = '';
      }
    }, 180);
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const first = results.querySelector('[data-path]');
      if (first) {
        e.preventDefault();
        navigateSearchResult(first.getAttribute('data-path'), first.getAttribute('data-frag'));
      }
    }
  });
  if (clear) {
    clear.addEventListener('click', () => {
      input.value = '';
      input.dispatchEvent(new Event('input'));
      input.focus();
    });
  }
  results.addEventListener('click', (e) => {
    const sugg = e.target.closest('[data-sugg]');
    if (sugg) {
      input.value = sugg.getAttribute('data-sugg');
      input.dispatchEvent(new Event('input'));
      input.focus();
      return;
    }
    const el = e.target.closest('[data-path]');
    if (el) {
      if (!e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) e.preventDefault();
      navigateSearchResult(el.getAttribute('data-path'), el.getAttribute('data-frag'));
    }
  });
}

function refreshSearchPage(q) {
  currentSearchTerm = q;
  const input = document.getElementById('spInput');
  if (input && input.value !== q) input.value = q;
  setBreadcrumbs('Search: "' + q + '"');
  document.title = 'Search: ' + q + ': Eyum TTRPG';
  updateSearchPageResults(q);
}

function showSearchPage(q) {
  searchPageActive = true;
  currentSearchTerm = q;
  currentPath = null;
  document.title = 'Search: ' + q + ': Eyum TTRPG';
  setBreadcrumbs('Search: "' + q + '"');
  updateActiveLink();
  if (els.prevFile) els.prevFile.disabled = true;
  if (els.nextFile) els.nextFile.disabled = true;
  els.content.innerHTML = buildSearchPageFrame(q);
  bindSearchPageEvents();
  els.content.scrollTop = 0;
  updateSearchPageResults(q);
}

function openSearchPage(term, replace) {
  if (!term) return;
  hideSearchDropdown();
  if (searchPageActive) {
    setSearchParam(term, true);
    refreshSearchPage(term);
  } else {
    setSearchParam(term, false);
    showSearchPage(term);
  }
}

// ---- Quick-search dropdown (sidebar) ----
function hideSearchDropdown() {
  if (els.searchDropdown) els.searchDropdown.classList.remove('open');
  searchSelIdx = -1;
}

function positionDropdown(dd) {
  const r = els.searchWrap ? els.searchWrap.getBoundingClientRect() : null;
  if (!r || r.width === 0) return;
  const maxH = Math.min(window.innerHeight * 0.7, 560);
  if (window.innerWidth <= 900) {
    // The mobile sidebar is transform-animated, which makes it the containing
    // block for fixed children — position the dropdown relative to the wrap.
    dd.classList.add('absolute-mode');
    dd.style.left = '0px';
    dd.style.top = Math.round(r.height + 4) + 'px';
    dd.style.width = Math.round(r.width) + 'px';
  } else {
    dd.classList.remove('absolute-mode');
    dd.style.left = Math.round(r.left) + 'px';
    dd.style.top = Math.round(Math.min(r.bottom + 4, window.innerHeight - maxH - 8)) + 'px';
    dd.style.width = Math.max(260, Math.round(r.width)) + 'px';
  }
  dd.style.maxHeight = maxH + 'px';
}

function renderSearchDropdown(q) {
  const dd = els.searchDropdown;
  if (!dd) return;
  if (!q) { dd.classList.remove('open'); dd.innerHTML = ''; searchDropdownItems = []; return; }
  positionDropdown(dd);
  dd.classList.add('open');
  if (!searchIndex) {
    if (manifest) startSearchIndex();
    dd.innerHTML = '<div class="sd-note">' + (manifest ? 'Indexing the handbook…' : 'Loading…') + '</div>';
    searchDropdownItems = [];
    return;
  }
  const res = runSearch(q, { dropdown: true });
  let html = '';
  for (const g of res.glossary.filter((g2) => g2.exact).slice(0, 2)) {
    html += glossaryBubbleHTML(g, res.tokens, true);
  }
  if (res.pages.length) {
    html += '<div class="sd-group">Chapters &amp; Pages</div>';
    for (const p of res.pages.slice(0, 6)) {
      html += '<a class="sd-row" role="option" data-path="' + escAttr(p.path) + '" data-frag="" href="#' + encodeURIComponent(p.path) + '">'
        + '<span class="sd-row-main">' + highlightHTML(p.name, res.tokens) + '</span>'
        + '<span class="sd-row-sub">' + escHtml(p.path) + '</span></a>';
    }
  }
  if (res.headings.length) {
    html += '<div class="sd-group">Headings</div>';
    for (const h of res.headings.slice(0, 4)) {
      html += '<a class="sd-row" role="option" data-path="' + escAttr(h.path) + '" data-frag="' + escAttr(h.frag || '') + '" href="#' + encodeURIComponent(h.path) + '">'
        + '<span class="sd-row-main">' + highlightHTML(h.text, res.tokens) + '</span>'
        + '<span class="sd-row-sub">' + escHtml(h.page) + '</span></a>';
    }
  }
  if (res.content.length) {
    html += '<div class="sd-group">In Text</div>';
    for (const c of res.content.slice(0, 3)) {
      html += '<a class="sd-row" role="option" data-path="' + escAttr(c.path) + '" data-frag="' + escAttr(c.frag || '') + '" href="#' + encodeURIComponent(c.path) + '">'
        + '<span class="sd-row-main">' + escHtml(c.page) + '</span>'
        + (c.snippet ? '<span class="sd-row-sub">…' + highlightHTML(c.snippet, res.tokens) + '…</span>' : '') + '</a>';
    }
  }
  const total = res.counts.glossary + res.counts.pages + res.counts.headings + res.counts.content;
  if (!res.glossary.length && !res.pages.length && !res.headings.length && !res.content.length) {
    html += '<div class="sd-empty">No matches for “' + escHtml(res.query) + '”</div>';
    for (const s of res.suggestions.slice(0, 4)) {
      html += '<button class="sd-sugg" data-sugg="' + escAttr(s.to) + '">' + escHtml(s.to) + '</button>';
    }
  }
  html += '<button class="sd-footer" data-action="open">↵ Open search page'
    + (total ? ' · ' + total + ' result' + (total === 1 ? '' : 's') : '') + '</button>';
  dd.innerHTML = html;
  searchDropdownItems = [...dd.querySelectorAll('.sd-row')];
  searchSelIdx = -1;
}

function scheduleDropdownRender() {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    const q = els.searchInput.value.trim();
    if (els.searchClear) els.searchClear.hidden = !q;
    renderSearchDropdown(q);
  }, 140);
}

function initSearchUI() {
  if (!els.searchInput || !els.searchDropdown) return;

  els.searchInput.addEventListener('input', scheduleDropdownRender);
  els.searchInput.addEventListener('focus', () => {
    if (window.innerWidth <= 900 && els.sidebar) els.sidebar.classList.add('open');
    const q = els.searchInput.value.trim();
    if (q) renderSearchDropdown(q);
  });
  els.searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!searchDropdownItems.length) return;
      const dir = e.key === 'ArrowDown' ? 1 : -1;
      searchSelIdx = searchSelIdx < 0
        ? (dir === 1 ? 0 : searchDropdownItems.length - 1)
        : (searchSelIdx + dir + searchDropdownItems.length) % searchDropdownItems.length;
      searchDropdownItems.forEach((el, i) => el.classList.toggle('selected', i === searchSelIdx));
      const cur = searchDropdownItems[searchSelIdx];
      if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (searchSelIdx >= 0 && searchDropdownItems[searchSelIdx]) {
        const row = searchDropdownItems[searchSelIdx];
        navigateSearchResult(row.getAttribute('data-path'), row.getAttribute('data-frag'));
      } else {
        const q = els.searchInput.value.trim();
        if (q) openSearchPage(q, false);
      }
    } else if (e.key === 'Escape') {
      hideSearchDropdown();
    }
  });

  if (els.searchClear) {
    els.searchClear.addEventListener('click', () => {
      els.searchInput.value = '';
      els.searchClear.hidden = true;
      hideSearchDropdown();
      els.searchInput.focus();
    });
  }

  els.searchDropdown.addEventListener('click', (e) => {
    if (e.target.closest('[data-action="open"]')) {
      openSearchPage(els.searchInput.value.trim(), false);
      return;
    }
    const sugg = e.target.closest('[data-sugg]');
    if (sugg) {
      els.searchInput.value = sugg.getAttribute('data-sugg');
      els.searchInput.focus();
      scheduleDropdownRender();
      return;
    }
    const row = e.target.closest('.sd-row');
    if (row) {
      // Keep Ctrl/Cmd-click working for new tabs (href fallback); otherwise
      // navigate with the fragment so heading anchors are honored.
      if (!e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) e.preventDefault();
      navigateSearchResult(row.getAttribute('data-path'), row.getAttribute('data-frag'));
    }
  });

  document.addEventListener('click', (e) => {
    if (!els.searchWrap || els.searchWrap.contains(e.target)) return;
    hideSearchDropdown();
  });

  document.addEventListener('scroll', (e) => {
    if (els.searchDropdown && (e.target === els.searchDropdown || els.searchDropdown.contains(e.target))) return;
    hideSearchDropdown();
  }, true);

  window.addEventListener('resize', hideSearchDropdown);
  window.addEventListener('hashchange', hideSearchDropdown);

  // Ctrl/Cmd+K focuses search
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      els.searchInput.focus();
      els.searchInput.select();
      if (window.innerWidth <= 900 && els.sidebar) els.sidebar.classList.add('open');
    }
  });

  // Back/forward between search URLs and page URLs
  window.addEventListener('popstate', () => {
    const q = getSearchParam();
    if (q) {
      if (!searchPageActive) showSearchPage(q);
      else if (q !== currentSearchTerm) refreshSearchPage(q);
    } else if (searchPageActive) {
      searchPageActive = false;
    }
  });
}

init();
