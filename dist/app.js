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
  // Section 2.7 - Character Reference -> load editable character sheet
  if (path.includes('2.7 Character Reference')) {
    currentPath = path;
    setBreadcrumbs(path);
    updateActiveLink();
    if (graphView) graphView.currentPath = path;
    renderCharacterSheet();
    return;
  }

  currentPath = path;
  if (graphView) graphView.currentPath = path;
  updateActiveLink();
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

// ========== CHARACTER SHEET (2.7) ==========
const CS_KEY = 'eyum-character-sheet';
const AFFINITY_NAMES = [
  'Generic','Lightning','Hallowed','Tremor','Thunder','Obsidian',
  'Fire','Steam','Starlight','Deluge','Mirage','Quake',
  'Earth','Magma','Cursed','Shatter','Vacuum','Corruption',
  'Water','Ice/Cold','Ash','Sorrow','Warp','Miasma',
  'Air','Dust','Blight','Chaos','Storm','Gel',
  'Radiant','Mud','Poison','Infernal','Frostfire','Atomic',
  'Necrotic','Nova','Toxin','Metal','Glacial','Eldritch',
  'Psychic','Solar','Bloodfire','Torrent','Void'
];

function getDefaultSheetData() {
  return {
    name:'',race:'',background:'',title:'',sex:'',size:'',height:'',weight:'',build:'',age:'',
    level:'1',inspiration:'0',armorClass:'',initiative:'',speed:'',karma:'',
    profBonus:'+1',actionPts:'1',bonusActionPts:'1',reactionPts:'1',
    statPts:'24',skillPts:'5',affPts:'5',
    str:'8',strMod:'-1',dex:'8',dexMod:'-1',con:'8',conMod:'-1',
    wis:'8',wisMod:'-1',int:'8',intMod:'-1',cha:'8',chaMod:'-1',
    vitMax:'',vitCur:'',vitDice:'1d8',
    hpMax:'',hpCur:'',hpDice:'1d6',
    mpMax:'',mpCur:'',mpDice:'1d6',
    meleeDmg:'0',meleeAcc:'0',rangedDmg:'0',rangedAcc:'0',magicDmg:'0',magicAcc:'0',
    affinities:{},
    spells:'',
    strSave:'',athletics:'',conSave:'',dexSave:'',acrobatics:'',sleight:'',stealth:'',
    wisSave:'',arcana:'',history:'',search:'',situational:'',
    intSave:'',spot:'',nature:'',religion:'',medicine:'',
    chaSave:'',deception:'',intimidation:'',performance:'',persuasion:'',socialInsight:'',barter:'',
    passive1name:'',passive1desc:'',passive1uses:'',
    passive2name:'',passive2desc:'',passive2uses:'',
    passive3name:'',passive3desc:'',passive3uses:'',
    active1name:'',active1desc:'',active1cost:'',active1uses:'',
    active2name:'',active2desc:'',active2cost:'',active2uses:'',
    active3name:'',active3desc:'',active3cost:'',active3uses:'',
    copper:'',silver:'',gold:'',platinum:'',nerite:'',
    item1name:'',item1desc:'',item1dmg:'',item1val:'',item1qty:'',
    item2name:'',item2desc:'',item2dmg:'',item2val:'',item2qty:'',
    item3name:'',item3desc:'',item3dmg:'',item3val:'',item3qty:'',
    item4name:'',item4desc:'',item4dmg:'',item4val:'',item4qty:'',
    notes:'',backstory:''
  };
}

function loadSheetData() {
  try {
    const saved = JSON.parse(localStorage.getItem(CS_KEY));
    if (saved && typeof saved === 'object') {
      const defaults = getDefaultSheetData();
      for (const k in defaults) {
        if (saved[k] === undefined) saved[k] = defaults[k];
      }
      if (!saved.affinities || typeof saved.affinities !== 'object') saved.affinities = {};
      return saved;
    }
  } catch(e) {}
  return getDefaultSheetData();
}

function saveSheetData() {
  const data = {};
  document.querySelectorAll('.char-sheet input, .char-sheet textarea').forEach(function(el) {
    const name = el.getAttribute('data-cs');
    if (!name) return;
    if (name.startsWith('aff_')) {
      if (!data.affinities) data.affinities = {};
      data.affinities[name.slice(4)] = el.value;
    } else {
      data[name] = el.value;
    }
  });

  const saved = loadSheetData();
  for (const k in saved) {
    if (data[k] === undefined) data[k] = saved[k];
  }

  localStorage.setItem(CS_KEY, JSON.stringify(data));
  showSavedIndicator();
}

let saveTimer = null;
function autoSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveSheetData, 300);
}

function showSavedIndicator() {
  const el = document.getElementById('csSaved');
  if (!el) return;
  el.classList.add('visible');
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(function() { el.classList.remove('visible'); }, 2000);
}

function input_cs(name, value, cls, type) {
  type = type || 'text';
  cls = cls || '';
  return '<input type="'+type+'" data-cs="'+name+'" value="'+value.replace(/"/g,'&quot;')+'" class="'+cls+'" oninput="autoSave()">';
}

function textarea_cs(name, value) {
  return '<textarea data-cs="'+name+'" oninput="autoSave()">'+value.replace(/</g,'&lt;').replace(/>/g,'&gt;')+'</textarea>';
}

function renderCharacterSheet() {
  const d = loadSheetData();

  let html = '<div class="char-sheet-container">';
  html += '<div class="char-sheet-header">';
  html += '<h1>Character Reference</h1>';
  html += '<div class="btn-row">';
  html += '<a href="./character-sheet.pdf" download class="char-sheet-btn download">Download Blank PDF</a>';
  html += '<button class="char-sheet-btn" onclick="window.print()">Print Sheet</button>';
  html += '<button class="char-sheet-btn" onclick="clearSheet()">Clear All</button>';
  html += '<span class="char-sheet-saved" id="csSaved">Saved</span>';
  html += '</div></div>';

  html += '<div class="char-sheet">';

  // --- Character Info ---
  html += '<div class="section-title">Character Information</div>';
  html += '<table><colgroup><col style="width:14%"><col style="width:19%"><col style="width:14%"><col style="width:19%"><col style="width:14%"><col style="width:20%"></colgroup>';
  html += '<tr><td class="label-cell">Name</td><td>'+input_cs('name',d.name)+'</td><td class="label-cell">Level</td><td>'+input_cs('level',d.level,'narrow')+'</td><td class="label-cell">Stat Pts</td><td>'+input_cs('statPts',d.statPts,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Race</td><td>'+input_cs('race',d.race)+'</td><td class="label-cell">Inspiration</td><td>'+input_cs('inspiration',d.inspiration,'narrow')+'</td><td class="label-cell">Skill Pts</td><td>'+input_cs('skillPts',d.skillPts,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Background</td><td>'+input_cs('background',d.background)+'</td><td class="label-cell">Armor Class</td><td>'+input_cs('armorClass',d.armorClass,'narrow')+'</td><td class="label-cell">Affinity Pts</td><td>'+input_cs('affPts',d.affPts,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Title(s)</td><td>'+input_cs('title',d.title)+'</td><td class="label-cell">Initiative</td><td>'+input_cs('initiative',d.initiative,'narrow')+'</td><td rowspan="7" style="vertical-align:top;padding:8px;">';
  html += '<table style="width:100%"><tr><th>Stat</th><th>Score</th><th>Mod</th></tr>';
  html += '<tr><td class="label-cell">Strength</td><td>'+input_cs('str',d.str,'score')+'</td><td>'+input_cs('strMod',d.strMod,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Dexterity</td><td>'+input_cs('dex',d.dex,'score')+'</td><td>'+input_cs('dexMod',d.dexMod,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Constitution</td><td>'+input_cs('con',d.con,'score')+'</td><td>'+input_cs('conMod',d.conMod,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Wisdom</td><td>'+input_cs('wis',d.wis,'score')+'</td><td>'+input_cs('wisMod',d.wisMod,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Intelligence</td><td>'+input_cs('int',d.int,'score')+'</td><td>'+input_cs('intMod',d.intMod,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Charisma</td><td>'+input_cs('cha',d.cha,'score')+'</td><td>'+input_cs('chaMod',d.chaMod,'narrow')+'</td></tr>';
  html += '</table></td></tr>';
  html += '<tr><td class="label-cell">Sex</td><td>'+input_cs('sex',d.sex)+'</td><td class="label-cell">Speed</td><td>'+input_cs('speed',d.speed,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Size</td><td>'+input_cs('size',d.size)+'</td><td class="label-cell">Prof Bonus</td><td>'+input_cs('profBonus',d.profBonus,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Height</td><td>'+input_cs('height',d.height)+'</td><td class="label-cell">Action Pts</td><td>'+input_cs('actionPts',d.actionPts,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Weight</td><td>'+input_cs('weight',d.weight)+'</td><td class="label-cell">Bonus Action</td><td>'+input_cs('bonusActionPts',d.bonusActionPts,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Build</td><td>'+input_cs('build',d.build)+'</td><td class="label-cell">Reaction Pts</td><td>'+input_cs('reactionPts',d.reactionPts,'narrow')+'</td></tr>';
  html += '<tr><td class="label-cell">Age</td><td>'+input_cs('age',d.age)+'</td><td class="label-cell">Karma</td><td>'+input_cs('karma',d.karma,'narrow')+'</td></tr>';
  html += '</table>';

  // --- Pools & Combat ---
  html += '<div class="section-title">Pools &amp; Combat</div>';
  html += '<table>';
  html += '<tr><th></th><th>Max</th><th>Current</th><th>Dice</th><th></th><th></th><th>Base Dmg</th><th>Base Acc</th></tr>';
  html += '<tr><td class="label-cell">Vitality</td><td>'+input_cs('vitMax',d.vitMax,'med')+'</td><td>'+input_cs('vitCur',d.vitCur,'med')+'</td><td>'+input_cs('vitDice',d.vitDice,'med')+'</td><td class="label-cell">Melee</td><td></td><td>'+input_cs('meleeDmg',d.meleeDmg,'med')+'</td><td>'+input_cs('meleeAcc',d.meleeAcc,'med')+'</td></tr>';
  html += '<tr><td class="label-cell">Health</td><td>'+input_cs('hpMax',d.hpMax,'med')+'</td><td>'+input_cs('hpCur',d.hpCur,'med')+'</td><td>'+input_cs('hpDice',d.hpDice,'med')+'</td><td class="label-cell">Ranged</td><td></td><td>'+input_cs('rangedDmg',d.rangedDmg,'med')+'</td><td>'+input_cs('rangedAcc',d.rangedAcc,'med')+'</td></tr>';
  html += '<tr><td class="label-cell">Mana</td><td>'+input_cs('mpMax',d.mpMax,'med')+'</td><td>'+input_cs('mpCur',d.mpCur,'med')+'</td><td>'+input_cs('mpDice',d.mpDice,'med')+'</td><td class="label-cell">Magical</td><td></td><td>'+input_cs('magicDmg',d.magicDmg,'med')+'</td><td>'+input_cs('magicAcc',d.magicAcc,'med')+'</td></tr>';
  html += '</table>';

  // --- Affinities ---
  html += '<div class="section-title">Affinities</div>';
  html += '<div class="aff-grid">';
  AFFINITY_NAMES.forEach(function(name) {
    html += '<div class="aff-pair"><input type="text" value="'+name+'" readonly style="font-size:10px;opacity:.6;cursor:default;">'+input_cs('aff_'+name, d.affinities[name]||'', 'med', 'number')+'</div>';
  });
  html += '</div>';

  // --- Skills ---
  html += '<div class="section-title">Skills</div>';
  html += '<div class="two-col"><div><table>';
  html += '<tr><th>Skill</th><th>Mod</th><th>Prof</th><th>Exp</th></tr>';
  html += '<tr class="skill-cat"><td colspan="4">Strength</td></tr>';
  html += '<tr class="skill-sub"><td>Str Saving Throw</td><td>'+input_cs('strSave',d.strSave,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Athletics</td><td>'+input_cs('athletics',d.athletics,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-cat"><td colspan="4">Constitution</td></tr>';
  html += '<tr class="skill-sub"><td>Con Saving Throw</td><td>'+input_cs('conSave',d.conSave,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-cat"><td colspan="4">Dexterity</td></tr>';
  html += '<tr class="skill-sub"><td>Dex Saving Throw</td><td>'+input_cs('dexSave',d.dexSave,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Acrobatics</td><td>'+input_cs('acrobatics',d.acrobatics,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Sleight of Hand</td><td>'+input_cs('sleight',d.sleight,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Stealth</td><td>'+input_cs('stealth',d.stealth,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-cat"><td colspan="4">Wisdom</td></tr>';
  html += '<tr class="skill-sub"><td>Wis Saving Throw</td><td>'+input_cs('wisSave',d.wisSave,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Arcana</td><td>'+input_cs('arcana',d.arcana,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>History</td><td>'+input_cs('history',d.history,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Search</td><td>'+input_cs('search',d.search,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Situational Insight</td><td>'+input_cs('situational',d.situational,'med')+'</td><td></td><td></td></tr>';
  html += '</table></div><div><table>';
  html += '<tr><th>Skill</th><th>Mod</th><th>Prof</th><th>Exp</th></tr>';
  html += '<tr class="skill-cat"><td colspan="4">Intelligence</td></tr>';
  html += '<tr class="skill-sub"><td>Int Saving Throw</td><td>'+input_cs('intSave',d.intSave,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Spot</td><td>'+input_cs('spot',d.spot,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Nature</td><td>'+input_cs('nature',d.nature,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Religion</td><td>'+input_cs('religion',d.religion,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Medicine</td><td>'+input_cs('medicine',d.medicine,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-cat"><td colspan="4">Charisma</td></tr>';
  html += '<tr class="skill-sub"><td>Char Saving Throw</td><td>'+input_cs('chaSave',d.chaSave,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Deception</td><td>'+input_cs('deception',d.deception,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Intimidation</td><td>'+input_cs('intimidation',d.intimidation,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Performance</td><td>'+input_cs('performance',d.performance,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Persuasion</td><td>'+input_cs('persuasion',d.persuasion,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Social Insight</td><td>'+input_cs('socialInsight',d.socialInsight,'med')+'</td><td></td><td></td></tr>';
  html += '<tr class="skill-sub"><td>Barter</td><td>'+input_cs('barter',d.barter,'med')+'</td><td></td><td></td></tr>';
  html += '</table>';
  html += '<table class="cost-table" style="margin-top:10px;">';
  html += '<tr><th>Range</th><th>Norm</th><th>Prof</th><th>Exp</th></tr>';
  ['1-3|1|1|1','4-6|3|1|1','7-9|6|2|1','10-12|9|4|2','13-15|12|6|3','16-18|15|8|4','19-20|18|10|5','21+|50|25|10'].forEach(function(r){ var c=r.split('|'); html += '<tr><td>'+c[0]+'</td><td>'+c[1]+'</td><td>'+c[2]+'</td><td>'+c[3]+'</td></tr>'; });
  html += '</table></div></div>';

  // --- Passive Abilities ---
  html += '<div class="section-title">Passive Abilities</div>';
  html += '<table><tr><th>Name</th><th>Description</th><th>Uses / Recharge</th></tr>';
  for (var i=1; i<=3; i++) {
    html += '<tr><td>'+input_cs('passive'+i+'name',d['passive'+i+'name'])+'</td><td>'+input_cs('passive'+i+'desc',d['passive'+i+'desc'])+'</td><td>'+input_cs('passive'+i+'uses',d['passive'+i+'uses'])+'</td></tr>';
  }
  html += '</table>';

  // --- Active Abilities ---
  html += '<div class="section-title">Active Abilities</div>';
  html += '<table><tr><th>Name</th><th>Description</th><th>Cost</th><th>Uses / Recharge</th></tr>';
  for (var i=1; i<=3; i++) {
    html += '<tr><td>'+input_cs('active'+i+'name',d['active'+i+'name'])+'</td><td>'+input_cs('active'+i+'desc',d['active'+i+'desc'])+'</td><td>'+input_cs('active'+i+'cost',d['active'+i+'cost'])+'</td><td>'+input_cs('active'+i+'uses',d['active'+i+'uses'])+'</td></tr>';
  }
  html += '</table>';

  // --- Inventory ---
  html += '<div class="section-title">Inventory &amp; Currency</div>';
  html += '<div class="two-col"><div><table>';
  html += '<tr><th>Coin</th><th>Amount</th><th>Conv</th><th>Reference</th></tr>';
  html += '<tr><td class="label-cell">Copper</td><td>'+input_cs('copper',d.copper,'med')+'</td><td>100</td><td>1 Cent</td></tr>';
  html += '<tr><td class="label-cell">Silver</td><td>'+input_cs('silver',d.silver,'med')+'</td><td>100</td><td>1 Dollar</td></tr>';
  html += '<tr><td class="label-cell">Gold</td><td>'+input_cs('gold',d.gold,'med')+'</td><td>10</td><td>100 Dollars</td></tr>';
  html += '<tr><td class="label-cell">Platinum</td><td>'+input_cs('platinum',d.platinum,'med')+'</td><td>10</td><td>1000 Dollars</td></tr>';
  html += '<tr><td class="label-cell">Nerite</td><td>'+input_cs('nerite',d.nerite,'med')+'</td><td>\u2014</td><td>10000 Dollars</td></tr>';
  html += '</table></div><div><table>';
  html += '<tr><th>Item</th><th>Description</th><th>Dmg</th><th>Val</th><th>Qty</th></tr>';
  for (var i=1; i<=4; i++) {
    html += '<tr><td>'+input_cs('item'+i+'name',d['item'+i+'name'])+'</td><td>'+input_cs('item'+i+'desc',d['item'+i+'desc'])+'</td><td>'+input_cs('item'+i+'dmg',d['item'+i+'dmg'],'med')+'</td><td>'+input_cs('item'+i+'val',d['item'+i+'val'],'med')+'</td><td>'+input_cs('item'+i+'qty',d['item'+i+'qty'],'med')+'</td></tr>';
  }
  html += '</table></div></div>';

  // --- Spells ---
  html += '<div class="section-title">Spells</div>';
  html += textarea_cs('spells', d.spells);

  // --- Notes ---
  html += '<div class="section-title">Other Information / Notes</div>';
  html += textarea_cs('notes', d.notes);

  // --- Backstory ---
  html += '<div class="section-title">Backstory</div>';
  html += textarea_cs('backstory', d.backstory);

  html += '</div></div>';

  els.content.innerHTML = html;
  window.scrollTo({ top: 0, behavior: 'instant' });
}

function clearSheet() {
  if (!confirm('Clear all character sheet data?')) return;
  localStorage.removeItem(CS_KEY);
  renderCharacterSheet();
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
