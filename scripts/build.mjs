import fs from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import path from 'node:path';

const repoRoot = process.cwd();
const outDir = path.join(repoRoot, 'dist');
const contentDir = path.join(outDir, 'content');

const IGNORE_DIRS = new Set([
  '.git',
  '.github',
  'node_modules',
  'dist',
]);

async function rmSafe(target) {
  await fs.rm(target, { recursive: true, force: true });
}

async function mkdirp(target) {
  await fs.mkdir(target, { recursive: true });
}

async function walkMarkdown(dir, rel = '') {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const children = [];

  for (const entry of entries) {
    if (entry.name.startsWith('.') && entry.name !== '.obsidian') continue;
    if (IGNORE_DIRS.has(entry.name)) continue;

    const abs = path.join(dir, entry.name);
    const childRel = rel ? path.posix.join(rel, entry.name) : entry.name;

    if (entry.isDirectory()) {
      const subtree = await walkMarkdown(abs, childRel);
      if (subtree.children.length > 0) {
        children.push({ type: 'folder', name: entry.name, path: childRel, children: subtree.children });
      }
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      children.push({ type: 'file', name: entry.name, path: childRel });
    }
  }

  children.sort((a, b) => {
    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
    return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' });
  });

  return { type: 'folder', name: rel ? path.basename(rel) : 'root', path: rel, children };
}

async function copyMarkdownFiles(node) {
  if (node.type === 'file') {
    const src = path.join(repoRoot, node.path);
    const dest = path.join(contentDir, node.path);
    await mkdirp(path.dirname(dest));
    await fs.copyFile(src, dest);
    return;
  }
  for (const child of node.children || []) {
    await copyMarkdownFiles(child);
  }
}

function findDefaultFile(node) {
  if (node.type === 'file') return node.path;
  for (const child of node.children || []) {
    const found = findDefaultFile(child);
    if (found) return found;
  }
  return null;
}

// Build name-to-path map for wiki link resolution
function buildNameMap(node, map) {
  if (node.type === 'file') {
    const name = node.name.replace(/\.md$/i, '').toLowerCase().trim();
    if (!map.has(name)) map.set(name, node.path);
    return;
  }
  for (const child of node.children || []) buildNameMap(child, map);
}

// Extract [[wiki links]] from a markdown file
function extractLinksFromFile(filePath, nameMap) {
  try {
    const content = readFileSync(filePath, 'utf-8');
    const links = [];
    const re = /\[\[([^\]]+)\]\]/g;
    let m;
    while ((m = re.exec(content)) !== null) {
      const target = m[1].split('|')[0].trim().toLowerCase();
      const resolved = nameMap.get(target);
      if (resolved) links.push(resolved);
    }
    return links;
  } catch {
    return [];
  }
}

// Extract all edges from the file tree
function extractAllEdges(node, nameMap) {
  const edges = [];
  function walk(n) {
    if (n.type === 'file') {
      const filePath = path.join(repoRoot, n.path);
      const targets = extractLinksFromFile(filePath, nameMap);
      for (const t of targets) {
        if (t !== n.path) edges.push([n.path, t]);
      }
      return;
    }
    for (const c of n.children || []) walk(c);
  }
  walk(node);
  return edges;
}

// Ensure content dir is clean before copying markdown from source
await rmSafe(contentDir);

// Copy Character Manager data files for the web app
const charMgrData = path.join(repoRoot, 'Eyum TTRPG', 'Character Manager', 'data');
const dataFiles = ['graph_cache.json', 'spells.json', 'rules.json', 'builds.json'];
for (const f of dataFiles) {
  const src = path.join(charMgrData, f);
  try { await fs.copyFile(src, path.join(outDir, f)); }
  catch { console.log(`  Skipped ${f} (not found, run generator first)`); }
}

const tree = await walkMarkdown(repoRoot);
await copyMarkdownFiles(tree);

const nameMap = new Map();
buildNameMap(tree, nameMap);
const edges = extractAllEdges(tree, nameMap);

const manifest = {
  generatedAt: new Date().toISOString(),
  defaultFile: findDefaultFile(tree),
  tree,
  edges,
};

await fs.writeFile(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
console.log(`Built site into dist/ (${edges.length} wiki links extracted)`);
