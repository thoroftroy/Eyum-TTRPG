import fs from 'node:fs/promises';
import path from 'node:path';

const repoRoot = process.cwd();
const siteDir = path.join(repoRoot, 'site');
const outDir = path.join(repoRoot, 'dist');
const contentDir = path.join(outDir, 'content');

const IGNORE_DIRS = new Set([
  '.git',
  '.github',
  'node_modules',
  'dist',
  'site',
]);

async function rmSafe(target) {
  await fs.rm(target, { recursive: true, force: true });
}

async function mkdirp(target) {
  await fs.mkdir(target, { recursive: true });
}

async function copyDir(src, dest) {
  await mkdirp(dest);
  const entries = await fs.readdir(src, { withFileTypes: true });
  for (const entry of entries) {
    const from = path.join(src, entry.name);
    const to = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      await copyDir(from, to);
    } else {
      await fs.copyFile(from, to);
    }
  }
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

await rmSafe(outDir);
await copyDir(siteDir, outDir);

const tree = await walkMarkdown(repoRoot);
await copyMarkdownFiles(tree);

const manifest = {
  generatedAt: new Date().toISOString(),
  defaultFile: findDefaultFile(tree),
  tree,
};

await fs.writeFile(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
console.log('Built site into dist/');
