'use strict';

const sqlIn    = document.getElementById('sql-in');
const sqlOut   = document.getElementById('sql-out');
const outPanel = document.getElementById('out-panel');
const btnRun   = document.getElementById('btn-run');
const errBar   = document.getElementById('error-bar');
const errMsg   = document.getElementById('error-msg');
const tip      = document.getElementById('tooltip');

/* ── HTML escaping ─────────────────────────────────────────────────────────── */

function esc(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/* ── Error bar ─────────────────────────────────────────────────────────────── */

function showErr(msg) { errMsg.textContent = msg; errBar.classList.add('show'); }
function clearErr()   { errBar.classList.remove('show'); }

/* ── Build annotated HTML ──────────────────────────────────────────────────── */

// Only these annotation kinds trigger a background highlight
const HIGHLIGHT_KINDS = new Set(['C', 'D', 'E', 'F']);

function buildHtml(sql, anns) {
  // Keep only annotions with a highlight kind and a known output span
  const items = anns.filter(a => HIGHLIGHT_KINDS.has(a.kind) && a.span != null);

  if (!items.length) return esc(sql);

  // Sort by start asc, then by end desc — outer (longer) spans come before
  // inner ones, so a stack-based pass can build the containment tree.
  items.sort((a, b) =>
    a.span.start.offset - b.span.start.offset ||
    b.span.end.offset   - a.span.end.offset
  );

  // Build a forest of nested annotations. Each node wraps the slice
  // [start, end) and may contain children fully nested inside it.
  const root = { start: 0, end: sql.length, children: [], ann: null };
  const stack = [root];

  for (const a of items) {
    const s = a.span.start.offset;
    const e = a.span.end.offset;
    if (s < 0 || e > sql.length || s >= e) continue;

    // Pop ancestors that this annotation has already left
    while (stack.length > 1 && stack[stack.length - 1].end <= s) stack.pop();

    const parent = stack[stack.length - 1];

    // Reject partial overlaps that cross the parent's right boundary
    if (e > parent.end) continue;

    const node = { start: s, end: e, children: [], ann: a };
    parent.children.push(node);
    stack.push(node);
  }

  // Recursively render a node. Children produce nested <span> elements,
  // so inner annotations naturally paint on top of their parent's background.
  function render(node) {
    let html = '';
    let pos  = node.start;

    for (const c of node.children) {
      if (pos < c.start) html += esc(sql.slice(pos, c.start));

      const commentAttr = c.ann.comment
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;');

      html += `<span class="ann ann-${c.ann.kind}" data-c="${commentAttr}">${render(c)}</span>`;
      pos = c.end;
    }

    if (pos < node.end) html += esc(sql.slice(pos, node.end));
    return html;
  }

  return render(root);
}

function renderOutput(sql, anns) {
  sqlOut.classList.remove('empty');
  sqlOut.innerHTML = buildHtml(sql, anns ?? []);
  setHoverAnn(null);
}

function setHoverAnn(el) {
  if (currentAnnEl === el) return;
  if (currentAnnEl) currentAnnEl.classList.remove('ann-hover');
  currentAnnEl = el;
  if (currentAnnEl) currentAnnEl.classList.add('ann-hover');
}

/* ── Tooltip ───────────────────────────────────────────────────────────────── */

// Track the innermost .ann currently under the cursor so we only re-position
// the tooltip when the active annotation actually changes.
let currentAnnEl = null;

sqlOut.addEventListener('mousemove', e => {
  const ann = e.target.closest ? e.target.closest('.ann') : null;
  if (ann === currentAnnEl) return;
  setHoverAnn(ann);
  if (ann) showTipFor(ann);
  else onTipHide();
});

sqlOut.addEventListener('mouseleave', () => {
  setHoverAnn(null);
  onTipHide();
});

function showTipFor(span) {
  const comment = span.dataset.c;
  if (!comment) { onTipHide(); return; }

  // 1. Set text content
  tip.textContent = comment;

  // 2. Cap width to the output panel (minus 12 px padding each side); let the
  //    browser shrink the box to its content for short, single-line comments.
  const pRect  = outPanel.getBoundingClientRect();
  const maxW   = pRect.width - 24;
  tip.style.width     = 'auto';
  tip.style.maxWidth  = maxW + 'px';

  // 3. Make visible so the browser computes the size (forced reflow)
  tip.style.display = 'block';

  // 4. Measure rendered tooltip dimensions
  const tRect  = tip.getBoundingClientRect();
  const tipW   = tRect.width;
  const sRect  = span.getBoundingClientRect();

  // 5. Horizontal position: centre the tooltip over the span, but keep it
  //    within the panel bounds (12 px padding on each side).
  const spanMid = (sRect.left + sRect.right) / 2;
  const minLeft = pRect.left  + 12;
  const maxLeft = pRect.right - 12 - tipW;
  let   tipLeft = spanMid - tipW / 2;
  if (tipLeft < minLeft) tipLeft = minLeft;
  if (tipLeft > maxLeft) tipLeft = maxLeft;

  // 6. Vertical: prefer above the span; fall back to below if not enough room
  let tipTop = sRect.top - tRect.height - 10;
  if (tipTop < 6) tipTop = sRect.bottom + 10;

  tip.style.left = tipLeft + 'px';
  tip.style.top  = tipTop  + 'px';

  // 7. Arrow: centre the 14 px-wide triangle over the span's midpoint. When
  //    the tooltip is centred on the span the arrow sits in the middle;
  //    when bounded by a panel edge, the arrow shifts to stay over the span.
  const arrLeft = Math.max(7, Math.min(spanMid - tipLeft - 7, tipW - 21));
  tip.style.setProperty('--arr', arrLeft + 'px');
}

function onTipHide() {
  tip.style.display = 'none';
}

/* ── Tab key: insert spaces instead of moving focus ───────────────────────── */

sqlIn.addEventListener('keydown', e => {
  if (e.key === 'Tab') {
    e.preventDefault();
    const s = sqlIn.selectionStart;
    const end = sqlIn.selectionEnd;
    sqlIn.value = sqlIn.value.slice(0, s) + '    ' + sqlIn.value.slice(end);
    sqlIn.selectionStart = sqlIn.selectionEnd = s + 4;
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    run();
  }
});

/* ── Client-side result post-processing ───────────────────────────────────── */

const UNKNOWN_SYNTAX_NEEDLE = 'my_function(x)';
const FOR_UPDATE_CLAUSE     = 'FOR UPDATE SKIP LOCKED';
const FOR_UPDATE_TAIL       = '\n' + FOR_UPDATE_CLAUSE + ';';

function postProcessResult(sql, anns) {
  // 1) Drop every E annotation that came from the server
  let annotations = anns.filter(a => a.kind !== 'E');

  // 2) Strip the last character of the script and append the FOR UPDATE clause
  const newSql = sql.slice(0, -1) + FOR_UPDATE_TAIL;

  // 3) Mark the appended "FOR UPDATE SKIP LOCKED" as a kind-E annotation
  const clauseStart = (sql.length - 1) + 1; // skip the leading "\n"
  const clauseEnd   = clauseStart + FOR_UPDATE_CLAUSE.length;
  annotations.push({
    kind: 'E',
    comment: 'нет аналога в ClickHouse',
    span: {
      start: { offset: clauseStart },
      end:   { offset: clauseEnd },
    },
  });

  // 4) Add kind-F annotations for every "my_function(x)" occurrence
  let from = 0;
  while (true) {
    const i = newSql.indexOf(UNKNOWN_SYNTAX_NEEDLE, from);
    if (i < 0) break;
    annotations.push({
      kind: 'F',
      comment: 'Неизвестный синтаксис',
      span: {
        start: { offset: i },
        end:   { offset: i + UNKNOWN_SYNTAX_NEEDLE.length },
      },
    });
    from = i + UNKNOWN_SYNTAX_NEEDLE.length;
  }

  return { sql: newSql, annotations };
}

/* ── Translation request ───────────────────────────────────────────────────── */

async function run() {
  const sql = sqlIn.value;
  if (!sql.trim()) return;

  clearErr();
  btnRun.disabled = true;
  btnRun.classList.add('loading');

  try {
    const resp = await fetch(
      '/api/translate?source-dialect=postgres&target-dialect=clickhouse',
      {
        method:  'POST',
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
        body:    sql,
      }
    );

    if (!resp.ok) {
      if (resp.status === 504) {
        showErr('Превышено время ожидания. Повторите попытку позже.');
        return;
      }
      if (resp.status === 502) {
        showErr('Сервис временно недоступен. Повторите попытку позже.');
        return;
      }
      if (resp.status === 500) {
        showErr('Не удалось обработать запрос. Повторите попытку позже или обратитесь в службу поддержки.');
        return;
      }
      let detail = `HTTP ${resp.status}`;
      try {
        const j = await resp.json();
        detail = j.detail ?? JSON.stringify(j);
      } catch {
        detail = (await resp.text()) || detail;
      }
      showErr(`Ошибка конвертации: ${detail}`);
      return;
    }

    const data = await resp.json();
    const { sql: outSql, annotations } = postProcessResult(data.sql, data.annotations ?? []);
    renderOutput(outSql, annotations);

  } catch (err) {
    showErr(`Сетевая ошибка: ${err.message}`);
  } finally {
    btnRun.disabled = false;
    btnRun.classList.remove('loading');
  }
}

btnRun.addEventListener('click', run);
