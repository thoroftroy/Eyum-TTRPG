// === Eyum Sheet Editor v6 - Grid snap + alignment guides ===
var PAGE_W = 816, PAGE_H = 1056, NUMPAGES = 3;
var elCounter = 0;
var elements = {};
var selectedEl = null;
var dragInfo = null;
var GRID_SIZE = 10;
var SNAP_THRESHOLD = 5;
var showGrid = true;
var guideLines = [];

var LOG = [];
function log(msg) { var ts = new Date().toISOString().slice(11,23); LOG.push('['+ts+'] '+msg); console.log('['+ts+'] '+msg); var dp = document.getElementById('debugPanel'); if(dp) { dp.textContent = LOG.join('\n'); dp.scrollTop = dp.scrollHeight; } }
log('=== v6 Grid Snap Editor starting ===');

function elid() { return 'e' + (++elCounter); }
function $(id) { return document.getElementById(id); }
function px(v) { return v + 'px'; }

// === Grid overlay ===
function updateGridOverlays() {
  for (var i=0; i<NUMPAGES; i++) {
    var gs = $('grid'+i);
    if (!gs) continue;
    if (showGrid) {
      gs.style.backgroundImage = 'linear-gradient(rgba(0,0,0,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,0.06) 1px, transparent 1px)';
      gs.style.backgroundSize = px(GRID_SIZE) + ' ' + px(GRID_SIZE);
      gs.style.backgroundPosition = '-1px -1px';
    } else {
      gs.style.backgroundImage = 'none';
    }
  }
}

// === Alignment guides ===
function clearGuides() {
  guideLines.forEach(function(l) { l.remove(); });
  guideLines = [];
}
function showGuide(x, y, w, h, pageIdx) {
  var gs = $('grid'+pageIdx);
  if (!gs) return;
  var line = document.createElement('div');
  line.className = 'guide-line';
  line.style.left = px(x);
  line.style.top = px(y);
  if (w) line.style.width = px(w);
  if (h) line.style.height = px(h);
  gs.appendChild(line);
  guideLines.push(line);
}

// === Snap to grid ===
function snapToGrid(val) {
  return Math.round(val / GRID_SIZE) * GRID_SIZE;
}

// === Snap to other elements ===
function snapToElements(el, pageIdx, proposedLeft, proposedTop, proposedW, proposedH) {
  var snapX = proposedLeft, snapY = proposedTop;
  var guides = { v: null, h: null }; // visual guides to show

  var rect = {
    left: proposedLeft, top: proposedTop,
    right: proposedLeft + proposedW, bottom: proposedTop + proposedH,
    cx: proposedLeft + proposedW/2, cy: proposedTop + proposedH/2
  };

  if (!elements[pageIdx]) return { left: snapX, top: snapY };

  var others = elements[pageIdx].filter(function(r) { return r.el !== el; });

  others.forEach(function(other) {
    var o = other.el;
    var ol = parseInt(o.style.left), ot = parseInt(o.style.top);
    var ow = parseInt(o.style.width), oh = parseInt(o.style.height);
    var or = ol + ow, ob = ot + oh;
    var ocx = ol + ow/2, ocy = ot + oh/2;

    // Left edge snap: my left vs their left, their right
    var dl_left = Math.abs(rect.left - ol);
    var dl_right = Math.abs(rect.left - or);
    if (dl_left <= SNAP_THRESHOLD && dl_left < (Math.abs(snapX - proposedLeft) + 1)) { snapX = ol; guides.v = { x: ol, y1: Math.min(rect.top, ot), y2: Math.max(rect.bottom, ob) }; }
    else if (dl_right <= SNAP_THRESHOLD && dl_right < (Math.abs(snapX - proposedLeft) + 1)) { snapX = or; guides.v = { x: or, y1: Math.min(rect.top, ot), y2: Math.max(rect.bottom, ob) }; }

    // Right edge snap: my right vs their left, their right
    if (!guides.v) {
      var dr_left = Math.abs(rect.right - ol);
      var dr_right = Math.abs(rect.right - or);
      if (dr_left <= SNAP_THRESHOLD && dr_left < (Math.abs((snapX + proposedW) - (proposedLeft + proposedW)) + 1)) { snapX = ol - proposedW; guides.v = { x: ol, y1: Math.min(rect.top, ot), y2: Math.max(rect.bottom, ob) }; }
      else if (dr_right <= SNAP_THRESHOLD && dr_right < (Math.abs((snapX + proposedW) - (proposedLeft + proposedW)) + 1)) { snapX = or - proposedW; guides.v = { x: or, y1: Math.min(rect.top, ot), y2: Math.max(rect.bottom, ob) }; }
    }

    // Center X snap
    if (!guides.v && Math.abs(rect.cx - ocx) <= SNAP_THRESHOLD) {
      snapX = ocx - proposedW/2; guides.v = { x: ocx, y1: Math.min(rect.top, ot), y2: Math.max(rect.bottom, ob) };
    }

    // Top edge snap
    var dt_top = Math.abs(rect.top - ot);
    var dt_bottom = Math.abs(rect.top - ob);
    if (dt_top <= SNAP_THRESHOLD && dt_top < (Math.abs(snapY - proposedTop) + 1)) { snapY = ot; guides.h = { y: ot, x1: Math.min(rect.left, ol), x2: Math.max(rect.right, or) }; }
    else if (dt_bottom <= SNAP_THRESHOLD && dt_bottom < (Math.abs(snapY - proposedTop) + 1)) { snapY = ob; guides.h = { y: ob, x1: Math.min(rect.left, ol), x2: Math.max(rect.right, or) }; }

    // Bottom edge snap
    if (!guides.h) {
      var db_top = Math.abs(rect.bottom - ot);
      var db_bottom = Math.abs(rect.bottom - ob);
      if (db_top <= SNAP_THRESHOLD) { snapY = ot - proposedH; guides.h = { y: ot, x1: Math.min(rect.left, ol), x2: Math.max(rect.right, or) }; }
      else if (db_bottom <= SNAP_THRESHOLD) { snapY = ob - proposedH; guides.h = { y: ob, x1: Math.min(rect.left, ol), x2: Math.max(rect.right, or) }; }
    }

    // Center Y snap
    if (!guides.h && Math.abs(rect.cy - ocy) <= SNAP_THRESHOLD) {
      snapY = ocy - proposedH/2; guides.h = { y: ocy, x1: Math.min(rect.left, ol), x2: Math.max(rect.right, or) };
    }
  });

  // Actually snap
  var result = { left: snapX, top: snapY };
  if (Math.abs(snapX - proposedLeft) <= SNAP_THRESHOLD) result.left = snapX;
  if (Math.abs(snapY - proposedTop) <= SNAP_THRESHOLD) result.top = snapY;

  // Show guides
  clearGuides();
  if (guides.v) showGuide(guides.v.x, guides.v.y1, 1, guides.v.y2 - guides.v.y1, pageIdx);
  if (guides.h) showGuide(guides.h.x1, guides.h.y, guides.h.x2 - guides.h.x1, 1, pageIdx);

  return { left: result.left, top: result.top, guides: guides };
}

// === Selection ===
function selectElement(el) {
  if (selectedEl === el) return;
  deselectAll();
  selectedEl = el;
  el.classList.add('selected');
  showPropPanel(el);
}
function deselectAll() {
  if (selectedEl) { selectedEl.classList.remove('selected'); hidePropPanel(); selectedEl = null; }
}

// === Properties Panel ===
var propPanel;
function showPropPanel(el) {
  hidePropPanel();
  propPanel = document.createElement('div');
  propPanel.className = 'prop-panel';
  propPanel.innerHTML =
    '<label>Size <input type="number" id="propFontSize" min="6" max="72" value="'+(parseInt(el.style.fontSize)||12)+'" style="width:45px"></label>'+
    '<label><input type="color" id="propColor" value="'+(rgbToHex(el.style.color)||'#222222')+'" style="width:24px;height:22px;padding:0;border:none;" title="Text color"></label>'+
    '<label><input type="color" id="propBg" value="'+(rgbToHex(el.style.backgroundColor)||'#ffffff')+'" style="width:24px;height:22px;padding:0;border:none;" title="Background"></label>'+
    '<button id="propBold" style="font-weight:bold;">B</button>'+
    '<button id="propItalic" style="font-style:italic;">I</button>';
  document.body.appendChild(propPanel);
  var rect = el.getBoundingClientRect();
  propPanel.style.left = px(Math.min(rect.left, window.innerWidth-250));
  propPanel.style.top = px(Math.max(rect.top - 40, 50));
  $('propFontSize').addEventListener('input', function() { el.style.fontSize = px(this.value); saveAll(); });
  $('propColor').addEventListener('input', function() { el.style.color = this.value; saveAll(); });
  $('propBg').addEventListener('input', function() { el.style.backgroundColor = this.value; saveAll(); });
  $('propBold').addEventListener('click', function() { el.style.fontWeight = el.style.fontWeight==='bold'?'normal':'bold'; saveAll(); });
  $('propItalic').addEventListener('click', function() { el.style.fontStyle = el.style.fontStyle==='italic'?'normal':'italic'; saveAll(); });
}
function rgbToHex(c) {
  if (!c || c==='transparent'||c==='rgba(0, 0, 0, 0)') return '#ffffff';
  if (c.startsWith('#')) return c;
  var m = c.match(/rgb\((\d+),\s*(\d+),\s*(\d+)/);
  if (m) return '#' + ('0'+parseInt(m[1]).toString(16)).slice(-2) + ('0'+parseInt(m[2]).toString(16)).slice(-2) + ('0'+parseInt(m[3]).toString(16)).slice(-2);
  return '#ffffff';
}
function hidePropPanel() { if (propPanel) { propPanel.remove(); propPanel = null; } }

// === Create Element ===
function createElement(pageIdx, type, left, top, width, height, html, id) {
  var grid = $('grid'+pageIdx);
  if (!grid) return null;
  id = id || elid();
  if (!elements[pageIdx]) elements[pageIdx] = [];

  var el = document.createElement('div');
  el.className = 'el el-'+type;
  el.id = id;
  el.style.left = px(left); el.style.top = px(top);
  el.style.width = px(width); el.style.height = px(height);
  el.style.fontSize = '12px';
  el.style.color = '#222';
  el.innerHTML = html;

  // Strip any old handles that might be in saved HTML
  el.querySelectorAll('.el-drag-handle, .el-resize-handle, .el-delete-btn, .table-btns, .row-delete-btn').forEach(function(h) { h.remove(); });

  var dh = document.createElement('div');
  dh.className = 'el-drag-handle';
  dh.addEventListener('mousedown', function(e) { startDrag(e, el, pageIdx); });
  el.appendChild(dh);

  var rh = document.createElement('div');
  rh.className = 'el-resize-handle';
  rh.addEventListener('mousedown', function(e) { startResize(e, el, pageIdx); });
  el.appendChild(rh);

  var db = document.createElement('button');
  db.className = 'el-delete-btn';
  db.innerHTML = '&times;';
  db.title = 'Delete';
  db.addEventListener('click', function(e) { e.stopPropagation(); deleteElement(el, pageIdx); });
  el.appendChild(db);

  el.addEventListener('mousedown', function(e) {
    if (e.target === dh || e.target === rh || e.target === db) return;
    if (e.target.closest('textarea, input, select, [contenteditable]')) return;
    selectElement(el);
  });

  // Debounced save on text changes
  var saveTimer = null;
  function debouncedSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveAll, 400);
  }
  el.querySelectorAll('textarea, input, select').forEach(function(f) {
    f.addEventListener('input', debouncedSave);
  });
  el.querySelectorAll('[contenteditable]').forEach(function(ce) {
    ce.addEventListener('input', debouncedSave);
    ce.addEventListener('blur', debouncedSave);
  });

  // Migrate old placeholder text -> real content
  el.querySelectorAll('textarea[placeholder]').forEach(function(ta) {
    if (!ta.value.trim() && ta.getAttribute('placeholder')) {
      ta.textContent = ta.getAttribute('placeholder');
      ta.removeAttribute('placeholder');
      debouncedSave();
    }
  });

  if (type === 'table') setupTableHandlers(el);

  grid.appendChild(el);
  elements[pageIdx].push({ el: el, type: type, left: left, top: top, width: width, height: height });
  debouncedSave();
  return el;
}

function deleteElement(el, pageIdx) {
  if (selectedEl === el) { deselectAll(); }
  el.remove();
  elements[pageIdx] = elements[pageIdx].filter(function(e) { return e.el !== el; });
  saveAll();
}

// === Drag / Resize with snapping ===
function startDrag(e, el, pageIdx) {
  e.preventDefault(); e.stopPropagation();
  if (!el.classList.contains('selected')) selectElement(el);
  var rect = el.getBoundingClientRect();
  dragInfo = {
    el: el, pageIdx: pageIdx,
    startX: e.clientX, startY: e.clientY,
    origLeft: parseInt(el.style.left), origTop: parseInt(el.style.top),
    origW: parseInt(el.style.width), origH: parseInt(el.style.height),
    mode: 'drag'
  };
}
function startResize(e, el, pageIdx) {
  e.preventDefault(); e.stopPropagation();
  if (!el.classList.contains('selected')) selectElement(el);
  dragInfo = {
    el: el, pageIdx: pageIdx,
    startX: e.clientX, startY: e.clientY,
    origW: parseInt(el.style.width), origH: parseInt(el.style.height),
    mode: 'resize'
  };
}
document.addEventListener('mousemove', function(e) {
  if (!dragInfo) return;
  if (dragInfo.mode === 'drag') {
    var rawLeft = dragInfo.origLeft + (e.clientX - dragInfo.startX);
    var rawTop = dragInfo.origTop + (e.clientY - dragInfo.startY);
    var snapped = snapToElements(dragInfo.el, dragInfo.pageIdx, rawLeft, rawTop, dragInfo.origW, dragInfo.origH);
    var nl = snapToGrid(snapped.left);
    var nt = snapToGrid(snapped.top);
    dragInfo.el.style.left = px(nl); dragInfo.el.style.top = px(nt);
  } else if (dragInfo.mode === 'resize') {
    var nw = Math.max(60, snapToGrid(dragInfo.origW + (e.clientX - dragInfo.startX)));
    var nh = Math.max(20, snapToGrid(dragInfo.origH + (e.clientY - dragInfo.startY)));
    dragInfo.el.style.width = px(nw); dragInfo.el.style.height = px(nh);
  }
});
document.addEventListener('mouseup', function(e) {
  if (!dragInfo) return;
  clearGuides();
  var rec = findElementRecord(dragInfo.el, dragInfo.pageIdx);
  if (rec) {
    rec.left = parseInt(dragInfo.el.style.left);
    rec.top = parseInt(dragInfo.el.style.top);
    rec.width = parseInt(dragInfo.el.style.width);
    rec.height = parseInt(dragInfo.el.style.height);
  }
  dragInfo = null;
  saveAll();
});

function findElementRecord(el, pageIdx) {
  if (!elements[pageIdx]) return null;
  for (var i=0; i<elements[pageIdx].length; i++)
    if (elements[pageIdx][i].el === el) return elements[pageIdx][i];
  return null;
}

// === Table handlers ===
function setupTableHandlers(el) {
  var table = el.querySelector('table');
  if (!table) return;

  // Strip old delete columns from saved tables
  table.querySelectorAll('.row-delete-btn').forEach(function(b) { var td = b.closest('td'); if (td) td.remove(); });
  var ths = table.querySelectorAll('thead th');
  if (ths.length > 0) {
    var lastTh = ths[ths.length-1];
    if (!lastTh.textContent.trim() && parseInt(lastTh.style.width) <= 28) lastTh.remove();
  }
  table.querySelectorAll('tbody td').forEach(function(td) {
    if (!td.textContent.trim() && parseInt(td.style.width) <= 28 && td.style.minWidth && parseInt(td.style.minWidth) <= 28) td.remove();
  });

  var headers = table.querySelectorAll('thead th');
  headers.forEach(function(th, idx) {
    th.style.position = 'relative';
    var handle = document.createElement('div');
    handle.className = 'col-resize-handle';
    handle.addEventListener('mousedown', function(e) {
      e.preventDefault(); e.stopPropagation();
      colResizeInfo = { th: th, startX: e.clientX, origW: th.offsetWidth, table: table, colIdx: idx };
    });
    th.appendChild(handle);
  });

  var addRowBtn = document.createElement('button');
  addRowBtn.className = 'table-action-btn';
  addRowBtn.textContent = '+ Row';
  addRowBtn.title = 'Add row';
  addRowBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    var tbody = table.querySelector('tbody');
    if (!tbody) return;
    var cols = table.querySelectorAll('thead th').length;
    var tr = document.createElement('tr');
    for (var i=0; i<cols; i++) { var td = document.createElement('td'); td.contentEditable = 'true'; tr.appendChild(td); }
    tbody.appendChild(tr);
    saveAll();
  });

  var addColBtn = document.createElement('button');
  addColBtn.className = 'table-action-btn';
  addColBtn.textContent = '+ Col';
  addColBtn.title = 'Add column';
  addColBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    var thead = table.querySelector('thead tr');
    var tbody = table.querySelector('tbody');
    if (!thead || !tbody) return;
    var th = document.createElement('th'); th.contentEditable = 'true'; th.textContent = 'Col';
    th.style.position = 'relative';
    var handle = document.createElement('div'); handle.className = 'col-resize-handle';
    handle.addEventListener('mousedown', function(ev) {
      ev.preventDefault(); ev.stopPropagation();
      colResizeInfo = { th: th, startX: ev.clientX, origW: th.offsetWidth, table: table, colIdx: thead.children.length };
    });
    th.appendChild(handle);
    thead.appendChild(th);
    var rows = tbody.querySelectorAll('tr');
    rows.forEach(function(tr) {
      var td = document.createElement('td'); td.contentEditable = 'true';
      tr.appendChild(td);
    });
    saveAll();
  });

  var delRowBtn = document.createElement('button');
  delRowBtn.className = 'table-action-btn';
  delRowBtn.textContent = '- Row';
  delRowBtn.title = 'Delete last row';
  delRowBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    var tbody = table.querySelector('tbody');
    if (!tbody) return;
    var rows = tbody.querySelectorAll('tr');
    if (rows.length > 0) { rows[rows.length-1].remove(); saveAll(); }
  });

  var delColBtn = document.createElement('button');
  delColBtn.className = 'table-action-btn';
  delColBtn.textContent = '- Col';
  delColBtn.title = 'Delete last column';
  delColBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    var thead = table.querySelector('thead tr');
    var tbody = table.querySelector('tbody');
    if (!thead || !tbody) return;
    var ths = thead.querySelectorAll('th');
    if (ths.length <= 1) return; // keep at least one
    ths[ths.length-1].remove();
    var rows = tbody.querySelectorAll('tr');
    rows.forEach(function(tr) {
      var tds = tr.querySelectorAll('td');
      if (tds.length > 0) tds[tds.length-1].remove();
    });
    saveAll();
  });

  var btnWrap = document.createElement('div');
  btnWrap.className = 'table-btns';
  btnWrap.appendChild(addRowBtn);
  btnWrap.appendChild(delRowBtn);
  btnWrap.appendChild(addColBtn);
  btnWrap.appendChild(delColBtn);
  el.appendChild(btnWrap);

  // Make existing cells editable
  var cells = table.querySelectorAll('td');
  cells.forEach(function(td) { td.contentEditable = 'true'; });
}

var colResizeInfo = null;
document.addEventListener('mousemove', function(e) {
  if (!colResizeInfo) return;
  var diff = e.clientX - colResizeInfo.startX;
  var nw = Math.max(30, colResizeInfo.origW + diff);
  colResizeInfo.th.style.width = px(nw);
  colResizeInfo.th.style.minWidth = px(nw);
});
document.addEventListener('mouseup', function(e) {
  if (colResizeInfo) { colResizeInfo = null; saveAll(); }
});

// === Helper builders ===
function hField(label, value, inputWidth) {
  var iw = inputWidth || 120;
  return '<div class="field-wrap"><label contenteditable="true" class="field-label">'+label+'</label><input type="text" value="'+(value||'')+'" style="width:'+iw+'px;" class="field-input"></div>';
}
function hTable(headers, rows, colWidths) {
  var ncols = headers.length;
  var html = '<table class="editable-table"><thead><tr>';
  headers.forEach(function(h, i) {
    var w = colWidths && colWidths[i] ? ' style="width:'+colWidths[i]+'px;min-width:'+colWidths[i]+'px;"' : '';
    html += '<th contenteditable="true"'+w+'>'+h+'</th>';
  });
  html += '</tr></thead><tbody>';
  rows.forEach(function(row) {
    html += '<tr>';
    var isSection = row.length === 1 && ncols > 1;
    if (isSection) {
      html += '<td contenteditable="true" colspan="'+ncols+'" style="font-weight:800;color:#2c3e50;text-transform:uppercase;font-size:11px;padding-top:6px;background:#f5f5f5;">'+row[0]+'</td>';
    } else {
      row.forEach(function(cell) { html += '<td contenteditable="true">'+(cell||'')+'</td>'; });
      for (var ci = row.length; ci < ncols; ci++) { html += '<td contenteditable="true"></td>'; }
    }
    html += '</tr>';
  });
  html += '</tbody></table>';
  return html;
}
function hTextarea(content) {
  return '<textarea class="el-textarea">'+(content||'')+'</textarea>';
}
function hLabel(text) {
  return '<div contenteditable="true" class="el-label-text">'+text+'</div>';
}

// === Init ===
document.addEventListener('DOMContentLoaded', function() {
  log('DOM ready');
  for (var i=0; i<NUMPAGES; i++) {
    var ps = $('pageSheet'+i);
    if (ps) { ps.style.width = px(PAGE_W); ps.style.height = px(PAGE_H); }
    var gs = $('grid'+i);
    if (gs) {
      gs.style.width = px(PAGE_W);
      gs.style.minHeight = px(PAGE_H);
      gs.style.position = 'relative';
      gs.style.overflow = 'visible';
      gs.style.background = '#fff';
    }
    elements[i] = [];
  }

  updateGridOverlays();

  $('btnReset').addEventListener('click', resetAll);
  $('btnPrint').addEventListener('click', function(){ window.print(); });
  $('btnDebug').addEventListener('click', function(){
    var dp = $('debugPanel'); dp.style.display = dp.style.display==='none'?'block':'none';
  });
  $('btnToggleGrid').addEventListener('click', function() {
    showGrid = !showGrid;
    updateGridOverlays();
    $('btnToggleGrid').textContent = showGrid ? 'Grid: ON' : 'Grid: OFF';
  });
  $('btnGridSize').addEventListener('change', function() {
    GRID_SIZE = parseInt(this.value) || 10;
    SNAP_THRESHOLD = Math.max(3, GRID_SIZE / 2);
    updateGridOverlays();
  });

  $('btnAddField').addEventListener('click', function(){ var p=askPage(); if(p>=0){ createElement(p,'field',40,40,260,40,hField('Label',''),null); saveAll(); } });
  $('btnAddTable').addEventListener('click', function(){
    var p=askPage(); if(p<0) return;
    var cols=parseInt(prompt('Columns?','3')), rows=parseInt(prompt('Rows?','3'));
    if(!cols||!rows||cols<1||rows<1) return;
    var hdrs=[]; for(var i=0;i<cols;i++) hdrs.push('Header '+(i+1));
    var rws=[]; for(var r=0;r<rows;r++){ var row=[]; for(var c=0;c<cols;c++) row.push(''); rws.push(row); }
    createElement(p,'table',40,40,500,200,hTable(hdrs,rws),null); saveAll();
  });
  $('btnAddTextarea').addEventListener('click', function(){ var p=askPage(); if(p>=0){ createElement(p,'textarea',40,40,300,150,hTextarea('Notes...'),null); saveAll(); } });
  $('btnAddLabel').addEventListener('click', function(){ var p=askPage(); if(p>=0){ createElement(p,'label',40,40,200,30,hLabel(''),null); saveAll(); } });

  // Save on page unload
  window.addEventListener('beforeunload', function() { saveAll(); });

  document.addEventListener('mousedown', function(e) {
    if (e.target.closest('.grid-canvas') && !e.target.closest('.el') && !e.target.closest('.prop-panel')) deselectAll();
  });
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Delete' && selectedEl && !e.target.closest('[contenteditable]') && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
      var p = getPageOfElement(selectedEl); if (p>=0) deleteElement(selectedEl, p);
    }
  });

  if (!loadAll()) { buildDefaultSheet(); saveAll(); }
  log('Init done. ' + countAll() + ' elements');
});

function askPage() { var p=parseInt(prompt('Page? (1, 2, or 3)','1'))-1; return (isNaN(p)||p<0||p>2)?-1:p; }
function getPageOfElement(el) { for (var k in elements) for (var i=0;i<elements[k].length;i++) if (elements[k][i].el===el) return parseInt(k); return -1; }
function countAll() { var n=0; for (var k in elements) n+=elements[k].length; return n; }

// === Save / Load ===
function syncValues(el) {
  el.querySelectorAll('textarea').forEach(function(ta) { ta.textContent = ta.value; });
  el.querySelectorAll('input').forEach(function(inp) { inp.setAttribute('value', inp.value); });
  el.querySelectorAll('select').forEach(function(sel) {
    var opt = sel.querySelector('option[value="'+sel.value+'"]');
    if (opt) opt.setAttribute('selected', '');
  });
}
function getCleanHTML(el) {
  var clone = el.cloneNode(true);
  clone.querySelectorAll('.el-drag-handle, .el-resize-handle, .el-delete-btn, .table-btns').forEach(function(h) { h.remove(); });
  syncValues(clone);
  return clone.innerHTML;
}
function saveAll() {
  var data = { nextId: elCounter, pages: {}, gridSize: GRID_SIZE, showGrid: showGrid };
  for (var k in elements) {
    data.pages[k] = elements[k].map(function(rec) {
      var el = rec.el;
      return {
        id: el.id, type: rec.type,
        left: parseInt(el.style.left), top: parseInt(el.style.top),
        width: parseInt(el.style.width), height: parseInt(el.style.height),
        fontSize: el.style.fontSize, color: el.style.color,
        bgColor: el.style.backgroundColor, fontWeight: el.style.fontWeight,
        fontStyle: el.style.fontStyle, html: getCleanHTML(el)
      };
    });
  }
  localStorage.setItem('eyum-sheet-v7', JSON.stringify(data));
}
function loadAll() {
  var raw = localStorage.getItem('eyum-sheet-v7');
  if (!raw) { raw = localStorage.getItem('eyum-sheet-v6'); }
  if (!raw) return false;
  try {
    var data = JSON.parse(raw);
    elCounter = data.nextId || 0;
    GRID_SIZE = data.gridSize || 10;
    showGrid = data.showGrid !== false;
    $('btnToggleGrid').textContent = showGrid ? 'Grid: ON' : 'Grid: OFF';
    $('btnGridSize').value = GRID_SIZE;
    SNAP_THRESHOLD = Math.max(3, GRID_SIZE / 2);
    for (var i=0; i<NUMPAGES; i++) { $('grid'+i).innerHTML = ''; elements[i] = []; }
    for (var k in data.pages) {
      var pi = parseInt(k);
      data.pages[k].forEach(function(d) {
        var el = createElement(pi, d.type, d.left, d.top, d.width, d.height, d.html, d.id);
        if (el) {
          if (d.fontSize) el.style.fontSize = d.fontSize;
          if (d.color) el.style.color = d.color;
          if (d.bgColor) el.style.backgroundColor = d.bgColor;
          if (d.fontWeight) el.style.fontWeight = d.fontWeight;
          if (d.fontStyle) el.style.fontStyle = d.fontStyle;
        }
      });
    }
    updateGridOverlays();
    log('Loaded ' + countAll() + ' elements');
    return true;
  } catch(e) { log('Load error: '+e.message); return false; }
}
function resetAll() {
  log('=== Reset ===');
  for (var i=0; i<NUMPAGES; i++) { $('grid'+i).innerHTML = ''; elements[i] = []; }
  elCounter = 0; selectedEl = null;
  localStorage.removeItem('eyum-sheet-v6');
  localStorage.removeItem('eyum-sheet-v7');
  buildDefaultSheet(); saveAll();
}

// === Default Sheet ===
function buildDefaultSheet() {
  log('Building default sheet...');
  var x = 20, y = 20, fw = 260, fh = 38, c2 = 290, c3 = 560;

  createElement(0, 'field', x, 20, fw, fh, hField('Name', '')); 
  createElement(0, 'field', c2, 20, 180, fh, hField('Level', '1', 60)); 
  createElement(0, 'field', c3, 20, 200, fh, hField('Stat Points (STP)', '24', 60));
  y = 60;
  createElement(0, 'field', x, y, fw, fh, hField('Race', '')); 
  createElement(0, 'field', c2, y, 180, fh, hField('Inspiration', '0', 60));
  createElement(0, 'field', c3, y, 200, fh, hField('Skill Points (SKP)', '5', 60));
  y+=42;
  createElement(0, 'field', x, y, fw, fh, hField('Background', ''));
  createElement(0, 'field', c2, y, 180, fh, hField('Armor Class', '', 60));
  createElement(0, 'field', c3, y, 200, fh, hField('Affinity Points (AFFP)', '5', 60));
  y+=42;
  createElement(0, 'field', x, y, fw, fh, hField('Title(s)', ''));
  createElement(0, 'field', c2, y, 180, fh, hField('Initiative', '', 60));
  y+=42;
  createElement(0, 'field', x, y, fw, fh, hField('Sex', ''));
  createElement(0, 'field', c2, y, 180, fh, hField('Speed', '', 60));
  createElement(0, 'field', c3, y, 200, fh, hField('Karma', '', 60));
  y+=42;
  createElement(0, 'field', x, y, fw, fh, hField('Size', ''));
  createElement(0, 'field', c2, y, 180, fh, hField('Proficiency Bonus', '+1', 60));
  createElement(0, 'field', c3, y, 200, fh, hField('Action Points (AP)', '1', 60));
  y+=42;
  createElement(0, 'field', x, y, fw, fh, hField('Height', ''));
  createElement(0, 'field', c2, y, 210, fh, hField('Bonus Action Pts (BAP)', '1', 60));
  createElement(0, 'field', c3, y, 200, fh, hField('Reaction Points (RP)', '1', 60));
  y+=42;
  createElement(0, 'field', x, y, fw, fh, hField('Weight', ''));
  createElement(0, 'field', c2, y, 180, fh, hField('Build', '', 60));
  y+=42;
  createElement(0, 'field', x, y, fw, fh, hField('Age', ''));

  var statsH = ['Stat','Score','Modifier'];
  var statsR = [['Strength','8','-1'],['Dexterity','8','-1'],['Constitution','8','-1'],['Wisdom','8','-1'],['Intelligence','8','-1'],['Charisma','8','-1']];
  createElement(0, 'table', 20, 400, 300, 230, hTable(statsH, statsR, [110,60,60]));

  var poolH = ['Pool','Max','Current','Dice'];
  var poolR = [['Vitality (VIT)','','','1d8'],['Health (HP)','','','1d6'],['Mana (MP)','','','1d6']];
  createElement(0, 'table', 340, 400, 260, 130, hTable(poolH, poolR, [100,50,55,50]));

  var cmbH = ['Combat','Base Dmg','Base Acc'];
  var cmbR = [['Melee','0','0'],['Ranged','0','0'],['Magical','0','0']];
  createElement(0, 'table', 620, 400, 170, 130, hTable(cmbH, cmbR, [60,70,70]));

  var affH = ['Affinity','Val','Affinity','Val','Affinity','Val','Affinity','Val','Affinity','Val','Affinity','Val'];
  var affNames = ['Generic','Lightning','Hallowed','Tremor','Thunder','Obsidian','Fire','Steam','Starlight','Deluge','Mirage','Quake','Earth','Magma','Cursed','Shatter','Vacuum','Corruption','Water','Ice/Cold','Ash','Sorrow','Warp','Miasma','Air','Dust','Blight','Chaos','Storm','Gel','Radiant','Mud','Poison','Infernal','Frostfire','Atomic','Necrotic','Nova','Toxin','Metal','Glacial','Eldritch','Psychic','Solar','Bloodfire','Torrent','Void'];
  var affRows=[],row=[];
  affNames.forEach(function(n,i){ row.push(n);row.push(''); if(row.length>=12){ affRows.push(row);row=[]; } });
  if(row.length>0) affRows.push(row);
  createElement(0, 'table', 20, 540, PAGE_W-40, 190, hTable(affH, affRows, [70,32,70,32,70,32,70,32,70,32,70,32]));

  createElement(0, 'textarea', 20, 740, PAGE_W-40, 250, hTextarea('List your spells...'));

  var skH = ['Skill','Mod','Prof','Exp'];
  var skL = [['STRENGTH'],['  Str Saving Throw','','',''],['  Athletics','','',''],['CONSTITUTION'],['  Con Saving Throw','','',''],['DEXTERITY'],['  Dex Saving Throw','','',''],['  Acrobatics','','',''],['  Sleight of Hand','','',''],['  Stealth','','',''],['WISDOM'],['  Wis Saving Throw','','',''],['  Arcana','','',''],['  History','','',''],['  Search','','',''],['  Situational Insight','','','']];
  var skR = [['INTELLIGENCE'],['  Int Saving Throw','','',''],['  Spot','','',''],['  Nature','','',''],['  Religion','','',''],['  Medicine','','',''],['CHARISMA'],['  Char Saving Throw','','',''],['  Deception','','',''],['  Intimidation','','',''],['  Performance','','',''],['  Persuasion','','',''],['  Social Insight','','',''],['  Barter','','','']];
  createElement(1, 'table', 10, 10, 390, 580, hTable(skH, skL, [150,40,40,40]));
  createElement(1, 'table', 410, 10, 390, 400, hTable(skH, skR, [150,40,40,40]));

  var costH = ['Range','Norm','Prof','Exp'];
  var costR = [['1-3','1','1','1'],['4-6','3','1','1'],['7-9','6','2','1'],['10-12','9','4','2'],['13-15','12','6','3'],['16-18','15','8','4'],['19-20','18','10','5'],['21+','50','25','10']];
  createElement(1, 'table', 410, 420, 390, 170, hTable(costH, costR, [80,60,60,60]));

  var passH = ['Name','Description','Uses / Recharge'];
  createElement(1, 'table', 10, 600, 790, 140, hTable(passH, [['','',''],['','',''],['','','']], [150,420,150]));

  var actH = ['Name','Description','Cost','Uses / Recharge'];
  createElement(1, 'table', 10, 750, 790, 140, hTable(actH, [['','','',''],['','','',''],['','','','']], [120,420,60,150]));

  var curH = ['Coin Type','Amount','Conv','Reference'];
  createElement(2, 'table', 20, 20, 380, 170, hTable(curH, [['Copper','','100','1 Cent'],['Silver','','100','1 Dollar'],['Gold','','10','100 Dollars'],['Platinum','','10','1000 Dollars'],['Nerite','','\u2014','10000 Dollars']], [80,60,50,120]));

  var itmH = ['Item Name','Description','Dmg','Val','Qty'];
  createElement(2, 'table', 420, 20, 380, 170, hTable(itmH, [['','','','',''],['','','','',''],['','','','',''],['','','','','']], [80,150,40,40,40]));

  createElement(2, 'label', 20, 200, 200, 22, hLabel('Other Information / Notes'));
  createElement(2, 'textarea', 20, 225, 380, 280, hTextarea('Additional notes...'));
  createElement(2, 'label', 420, 200, 200, 22, hLabel('Backstory'));
  createElement(2, 'textarea', 420, 225, 380, 280, hTextarea('Character backstory...'));

  log('Default sheet built: ' + countAll() + ' elements');
}
