import fs from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';

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
    const baseA = a.name.replace(/\.md$/i, '');
    const baseB = b.name.replace(/\.md$/i, '');
    if (baseA.localeCompare(baseB, undefined, { sensitivity: 'base' }) === 0) {
      return a.type === 'file' ? -1 : 1;
    }
    return baseA.localeCompare(baseB, undefined, { numeric: true, sensitivity: 'base' });
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
      const raw = m[1].split('|')[0].trim().toLowerCase();
      const pageName = raw.split('#')[0];  // strip fragment for lookup
      const resolved = nameMap.get(pageName);
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

// Copy search aliases for the website (site loads dist/aliases.json at runtime)
try {
  await fs.copyFile(path.join(repoRoot, 'aliases.json'), path.join(outDir, 'aliases.json'));
} catch { console.log('  Skipped aliases.json (not found)'); }

// Split massive graph_cache.json into per-tier files for the web graph view
try {
  const splitScript = path.join(repoRoot, 'scripts', 'split_graph_cache.py');
  execSync(`python3 "${splitScript}" "${path.join(outDir, 'graph_cache.json')}" "${path.join(outDir, 'graph_data')}"`, { stdio: 'inherit' });
} catch { console.log('  Skipped graph cache split (python3 not available)'); }

// Copy the newest fillable character sheet PDF.
// Convention: "Eyum Character Sheet vN.pdf" in the Character Sheet folder.
// Always pick the highest version number so new sheets need zero manual work.
try {
  const sheetDir = path.join(repoRoot, 'Eyum TTRPG', 'Character Manager', 'Character Sheet');
  const sheetRegex = /^Eyum Character Sheet v(\d+)\.pdf$/i;
  const entries = await fs.readdir(sheetDir);
  let best = null, bestV = -1;
  for (const name of entries) {
    const m = name.match(sheetRegex);
    if (m) {
      const v = parseInt(m[1], 10);
      if (v > bestV) { bestV = v; best = name; }
    }
  }
  if (best) {
    const csSrc = path.join(sheetDir, best);
    const pdfPath = path.join(outDir, 'character-sheet.pdf');
    await fs.copyFile(csSrc, pdfPath);
    console.log(`  Copied fillable character sheet: ${best} (auto-detected newest)`);

    // Keep the handbook's own copy of the sheet PDF in sync (local builds)
    try {
      await fs.copyFile(csSrc, path.join(repoRoot, 'Eyum TTRPG', '2.0 Reference Tables', 'Eyum Character Sheet.pdf'));
    } catch { console.log('  Skipped handbook sheet PDF copy'); }

    // Regenerate page preview PNGs from the new PDF (best-effort)
    try {
      for (const n of (await fs.readdir(outDir)).filter(n => /^cs_page-\d+\.png$/.test(n))) {
        await fs.rm(path.join(outDir, n), { force: true });
      }
      let rendered = false;
      try {
        execSync(`pdftoppm -png -r 150 "${pdfPath}" "${path.join(outDir, 'cs_page')}"`, { stdio: 'ignore' });
        rendered = true;
      } catch {
        for (const tool of ['magick -density 150', 'convert -density 150']) {
          try {
            execSync(`${tool} "${pdfPath}" "${path.join(outDir, 'cs_page')}"`, { stdio: 'ignore' });
            rendered = true;
            break;
          } catch { /* try next tool */ }
        }
        if (rendered) {
          // magick/convert emit cs_page-0.png, cs_page-1.png... -> shift to 1-based, drop page 0.
          // Rename from highest to lowest so targets are always free.
          const files = (await fs.readdir(outDir))
            .filter(n => /^cs_page-\d+\.png$/.test(n))
            .map(n => ({ n, i: parseInt(n.match(/-(\d+)\.png$/)[1], 10) }))
            .sort((a, b) => b.i - a.i);
          for (const f of files) {
            if (f.i === 0) await fs.rm(path.join(outDir, f.n), { force: true });
            else await fs.rename(path.join(outDir, f.n), path.join(outDir, `cs_page-${f.i + 1}.png`));
          }
        }
      }
      console.log(rendered ? '  Regenerated character sheet page previews' : '  Skipped page previews (no PDF renderer available)');
    } catch { console.log('  Skipped page previews (render error)'); }

    // Keep the download filename in index.html in sync with the newest version
    try {
      const idxPath = path.join(outDir, 'index.html');
      let html = await fs.readFile(idxPath, 'utf-8');
      const before = html;
      html = html.replace(/download="Eyum Character Sheet(?: v\d+)?\.pdf"/, `download="Eyum Character Sheet v${bestV}.pdf"`);
      if (html !== before) {
        await fs.writeFile(idxPath, html);
        console.log(`  Updated index.html download name to v${bestV}`);
      }
    } catch { console.log('  Skipped index.html download name update'); }
  } else {
    console.log('  Skipped character sheet (no "Eyum Character Sheet vN.pdf" found)');
  }
} catch { console.log('  Skipped character sheet PDF (folder not found)'); }

// Generate equipment combinations JSON
try {
  const eqScript = path.join(repoRoot, 'scripts', 'generate_equipment.py');
  execSync(`python3 "${eqScript}" "${path.join(outDir, 'equipment.json')}"`, { stdio: 'inherit' });
  // Also copy to Character Manager data dir so GUI can find it
  const guiEqPath = path.join(repoRoot, 'Eyum TTRPG', 'Character Manager', 'data', 'equipment.json');
  await fs.copyFile(path.join(outDir, 'equipment.json'), guiEqPath);
} catch { console.log('  Skipped equipment generation (python3 not available)'); }

const tree = await walkMarkdown(repoRoot);
await copyMarkdownFiles(tree);

// Copy embedded images into the site content tree and build a name -> path map
// so Obsidian-style embeds like ![[image.png]] resolve by filename no matter
// which folder the image lives in.
const IMAGE_EXTS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.avif']);
const imageMap = {};
async function copyImages(dir, rel = '') {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith('.') && entry.name !== '.obsidian') continue;
    if (IGNORE_DIRS.has(entry.name)) continue;
    const abs = path.join(dir, entry.name);
    const childRel = rel ? path.posix.join(rel, entry.name) : entry.name;
    if (entry.isDirectory()) {
      await copyImages(abs, childRel);
    } else if (entry.isFile() && IMAGE_EXTS.has(path.extname(entry.name).toLowerCase())) {
      const dest = path.join(contentDir, childRel);
      await mkdirp(path.dirname(dest));
      await fs.copyFile(abs, dest);
      const key = childRel.toLowerCase();
      if (!imageMap[key]) imageMap[key] = childRel;
      const nameKey = entry.name.toLowerCase();
      if (!imageMap[nameKey]) imageMap[nameKey] = childRel;
    }
  }
}
await copyImages(repoRoot);
if (Object.keys(imageMap).length > 0) console.log(`  Copied ${Object.keys(imageMap).length} embedded image file(s)`);

const nameMap = new Map();
buildNameMap(tree, nameMap);
const edges = extractAllEdges(tree, nameMap);

const manifest = {
  generatedAt: new Date().toISOString(),
  defaultFile: findDefaultFile(tree),
  tree,
  edges,
  images: imageMap,
};

await fs.writeFile(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
console.log(`Built site into dist/ (${edges.length} wiki links extracted)`);
