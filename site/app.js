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
  currentPath = path;
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

async function init() {
  applyTheme(loadTheme());

  const manifestRes = await fetch('./manifest.json');
  manifest = await manifestRes.json();
  buildWikiMap(manifest.tree);
  renderTree(manifest.tree, els.tree);

  const requested = location.hash ? decodeURIComponent(location.hash.slice(1)) : null;
  const start = requested || manifest.defaultFile || getDefaultFile(manifest.tree);
  if (start) await loadPage(start);

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
}

init().catch((err) => {
  els.content.innerHTML = `<div class="error">Failed to initialize site: ${err.message}</div>`;
});
