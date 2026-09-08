/* ============================================================
   引擎笔记 · 撰稿页 compose.js
   - 元数据/正文/评分
   - 工具栏插入 Markdown
   - localStorage 草稿管理
   - 导出 .md（带 frontmatter）
   - 实时预览（marked.js 走 CDN）
   ============================================================ */
(function () {
  'use strict';

  // ---------- DOM ----------
  const $ = (id) => document.getElementById(id);
  const editor = $('editor');
  const preview = $('preview');
  const prevTitle = $('prevTitle');
  const prevDeck = $('prevDeck');
  const draftList = $('draftList');
  const imgFile = $('imgFile');

  const fields = {
    title:    $('f-title'),
    slug:     $('f-slug'),
    date:     $('f-date'),
    author:   $('f-author'),
    brand:    $('f-brand'),
    model:    $('f-model'),
    category: $('f-category'),
    tags:     $('f-tags'),
    score:    $('f-score'),
    cover:    $('f-cover'),
    loan:     $('f-loan'),
    excerpt:  $('f-excerpt'),
  };
  const ratings = {
    power:    $('r-power'),
    handling: $('r-handling'),
    comfort:  $('r-comfort'),
    interior: $('r-interior'),
    smart:    $('r-smart'),
    value:    $('r-value'),
  };

  const DRAFT_KEY = 'engineNotes.drafts.v1';
  const ACTIVE_KEY = 'engineNotes.active.v1';

  // ---------- marked.js（CDN 懒加载） ----------
  let markedReady = null;
  function loadMarked() {
    if (markedReady) return markedReady;
    markedReady = new Promise((resolve, reject) => {
      if (window.marked) return resolve(window.marked);
      const s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js';
      s.onload = () => resolve(window.marked);
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return markedReady;
  }

  // ---------- 工具：日期 ----------
  function today() {
    const d = new Date();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${d.getFullYear()}-${m}-${day}`;
  }
  fields.date.value = today();

  // ---------- 工具：slug ----------
  function autoSlug(s) {
    return s.toLowerCase()
      .replace(/[\s_]+/g, '-')
      .replace(/[^\w\u4e00-\u9fa5-]/g, '')
      .replace(/-+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  // ---------- 收集/填充 ----------
  function collect() {
    const data = {
      title: fields.title.value.trim(),
      slug: fields.slug.value.trim(),
      date: fields.date.value || today(),
      author: fields.author.value.trim() || 'Wesley Lin',
      brand: fields.brand.value.trim(),
      model: fields.model.value.trim(),
      category: fields.category.value,
      tags: fields.tags.value.split(',').map((s) => s.trim()).filter(Boolean),
      score: fields.score.value ? Number(fields.score.value) : '',
      cover: fields.cover.value.trim(),
      loan: fields.loan.value.trim(),
      excerpt: fields.excerpt.value.trim(),
      ratings: {
        动力:   ratings.power.value ? Number(ratings.power.value) : '',
        操控:   ratings.handling.value ? Number(ratings.handling.value) : '',
        舒适:   ratings.comfort.value ? Number(ratings.comfort.value) : '',
        内饰:   ratings.interior.value ? Number(ratings.interior.value) : '',
        智能化: ratings.smart.value ? Number(ratings.smart.value) : '',
        性价比: ratings.value.value ? Number(ratings.value.value) : '',
      },
      body: editor.value,
      _updated: Date.now(),
    };
    return data;
  }

  function fill(d) {
    if (!d) return;
    fields.title.value    = d.title || '';
    fields.slug.value     = d.slug || (d.title ? autoSlug(d.title) : '');
    fields.date.value     = d.date || today();
    fields.author.value   = d.author || 'Wesley Lin';
    fields.brand.value    = d.brand || '';
    fields.model.value    = d.model || '';
    fields.category.value = d.category || '评测';
    fields.tags.value     = (d.tags || []).join(', ');
    fields.score.value    = d.score || '';
    fields.cover.value    = d.cover || '';
    fields.loan.value     = d.loan || '';
    fields.excerpt.value  = d.excerpt || '';
    if (d.ratings) {
      ratings.power.value    = d.ratings['动力'] || '';
      ratings.handling.value = d.ratings['操控'] || '';
      ratings.comfort.value  = d.ratings['舒适'] || '';
      ratings.interior.value = d.ratings['内饰'] || '';
      ratings.smart.value    = d.ratings['智能化'] || '';
      ratings.value.value    = d.ratings['性价比'] || '';
    }
    editor.value = d.body || '';
  }

  // ---------- 工具栏 ----------
  document.querySelectorAll('.toolbar-compose button[data-wrap], .toolbar-compose button[data-prefix], .toolbar-compose button[data-insert]').forEach((btn) => {
    btn.addEventListener('click', () => {
      editor.focus();
      const wrap = btn.dataset.wrap;
      const pre  = btn.dataset.prefix;
      const ins  = btn.dataset.insert;

      const start = editor.selectionStart;
      const end   = editor.selectionEnd;
      const sel   = editor.value.slice(start, end);

      let before = editor.value.slice(0, start);
      let after  = editor.value.slice(end);

      if (wrap) {
        const selected = sel || '文字';
        const replaced = wrap + selected + wrap;
        editor.value = before + replaced + after;
        // 选中包裹后的中间内容
        const newPos = start + wrap.length + selected.length;
        editor.setSelectionRange(start + wrap.length, newPos);
      } else if (pre) {
        // 在行首插入
        const lineStart = before.lastIndexOf('\n') + 1;
        const realStart = (start === lineStart) ? start : lineStart;
        editor.value = editor.value.slice(0, realStart) + pre + editor.value.slice(realStart);
        editor.setSelectionRange(start + pre.length, end + pre.length);
      } else if (ins) {
        editor.value = before + ins + after;
        editor.setSelectionRange(start + ins.length, start + ins.length);
      }
      renderPreview();
      saveActive();
    });
  });

  // 图片上传：转 data URL 嵌入（仅当前草稿有效，不上传服务器）
  $('tbImgUpload').addEventListener('click', () => imgFile.click());
  imgFile.addEventListener('change', () => {
    const f = imgFile.files && imgFile.files[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target.result;
      editor.focus();
      const pos = editor.selectionStart;
      editor.value = editor.value.slice(0, pos) + `\n\n![${f.name}](${dataUrl})\n\n` + editor.value.slice(pos);
      renderPreview();
      saveActive();
    };
    reader.readAsDataURL(f);
    imgFile.value = '';
  });

  // 标题/摘要/正文变化 → 预览 + 自动存 active
  Object.values(fields).forEach((el) => el.addEventListener('input', () => { renderPreview(); saveActive(); }));
  Object.values(ratings).forEach((el) => el.addEventListener('input', saveActive));
  editor.addEventListener('input', () => { renderPreview(); saveActive(); });

  // 标题变化 → 自动推导 slug（只在用户没改过 slug 时）
  let slugTouched = false;
  fields.slug.addEventListener('input', () => { slugTouched = true; saveActive(); });
  fields.title.addEventListener('input', () => {
    if (!slugTouched) fields.slug.value = autoSlug(fields.title.value);
  });

  // ---------- 预览 ----------
  async function renderPreview() {
    prevTitle.textContent = fields.title.value || '（标题）';
    prevDeck.textContent  = fields.excerpt.value || '（摘要）';
    try {
      const m = await loadMarked();
      const html = m.parse(editor.value || '*(正文预览)*', { gfm: true, breaks: false });
      preview.innerHTML = html;
      // 触发一次 layout 让 CSS 生效
    } catch (err) {
      preview.innerHTML = '<p style="color:#999">预览加载失败（marked.js 未就绪）</p>';
    }
  }

  // ---------- Frontmatter 序列化 ----------
  function buildFrontmatter(d) {
    const out = ['---'];
    out.push(`title: "${(d.title || '').replace(/"/g, '\\"')}"`);
    if (d.slug)   out.push(`slug: ${d.slug}`);
    if (d.date)   out.push(`date: ${d.date}`);
    if (d.author) out.push(`author: "${d.author.replace(/"/g, '\\"')}"`);
    if (d.brand)  out.push(`brand: "${d.brand.replace(/"/g, '\\"')}"`);
    if (d.model)  out.push(`model: "${d.model.replace(/"/g, '\\"')}"`);
    if (d.category) out.push(`category: ${d.category}`);
    if (d.tags.length) out.push(`tags: [${d.tags.join(', ')}]`);
    if (d.score !== '' && d.score !== null) out.push(`score: ${d.score}`);
    if (d.cover) out.push(`cover: ${d.cover}`);
    if (d.loan)  out.push(`loan: "${d.loan.replace(/"/g, '\\"')}"`);
    // 评分维度
    const valid = Object.entries(d.ratings).filter(([, v]) => v !== '' && v !== null);
    if (valid.length) {
      out.push('ratings:');
      for (const [k, v] of valid) out.push(`  ${k}: ${v}`);
    }
    if (d.excerpt) {
      out.push(`excerpt: "${d.excerpt.replace(/"/g, '\\"').replace(/\n/g, ' ')}"`);
    } else {
      // 自动从正文截前 200 字
      const plain = (d.body || '').replace(/[#>*_`!\[\]()|-]/g, '').replace(/\s+/g, '').slice(0, 200);
      if (plain) out.push(`excerpt: "${plain}…"`);
    }
    out.push('---', '');
    return out.join('\n');
  }

  // ---------- 草稿管理（localStorage） ----------
  function loadAllDrafts() {
    try { return JSON.parse(localStorage.getItem(DRAFT_KEY) || '{}'); }
    catch { return {}; }
  }
  function saveAllDrafts(map) {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(map));
  }
  function slugifyKey(d) {
    return (d.slug || d.title || '').trim() || ('draft-' + Date.now());
  }
  function saveDraft() {
    const d = collect();
    const map = loadAllDrafts();
    const key = slugifyKey(d);
    map[key] = d;
    saveAllDrafts(map);
    saveActive(key);
    refreshDraftList();
    flash('已保存草稿：' + key);
  }
  function loadDraft(key) {
    const map = loadAllDrafts();
    if (!map[key]) return;
    fill(map[key]);
    saveActive(key);
    renderPreview();
    flash('已加载草稿：' + key);
  }
  function deleteDraft(key) {
    const map = loadAllDrafts();
    if (!map[key]) return;
    if (!confirm(`删除草稿「${key}」？`)) return;
    delete map[key];
    saveAllDrafts(map);
    refreshDraftList();
  }
  function refreshDraftList() {
    const map = loadAllDrafts();
    const keys = Object.keys(map).sort((a, b) => (map[b]._updated || 0) - (map[a]._updated || 0));
    draftList.innerHTML = '';
    if (!keys.length) {
      draftList.innerHTML = '<li class="compose__drafts-empty">暂无草稿</li>';
      return;
    }
    keys.forEach((k) => {
      const d = map[k];
      const li = document.createElement('li');
      li.className = 'compose__drafts-item';
      li.innerHTML = `
        <a href="#" data-key="${k.replace(/"/g, '&quot;')}">
          <strong>${(d.title || '（无标题）').slice(0, 24)}</strong>
          <em>${d.date || ''}</em>
        </a>
        <button data-del="${k.replace(/"/g, '&quot;')}" title="删除" type="button">×</button>`;
      draftList.appendChild(li);
    });
    draftList.querySelectorAll('a[data-key]').forEach((a) => {
      a.addEventListener('click', (e) => { e.preventDefault(); loadDraft(a.dataset.key); });
    });
    draftList.querySelectorAll('button[data-del]').forEach((b) => {
      b.addEventListener('click', (e) => { e.preventDefault(); deleteDraft(b.dataset.del); });
    });
  }

  // active（最近编辑的草稿 key + 实时内容）
  function saveActive(key) {
    const d = collect();
    const data = { key: key || null, payload: d };
    localStorage.setItem(ACTIVE_KEY, JSON.stringify(data));
  }
  function loadActive() {
    try {
      const a = JSON.parse(localStorage.getItem(ACTIVE_KEY) || 'null');
      if (a && a.payload) fill(a.payload);
    } catch {}
  }

  // ---------- 导出 .md ----------
  function exportMd() {
    const d = collect();
    const fm = buildFrontmatter(d);
    const text = fm + (d.body || '').trim() + '\n';
    const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = (d.slug || 'untitled') + '.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
    flash('已导出 .md：' + a.download);
  }

  // ---------- 清空 ----------
  function clearAll() {
    if (!confirm('清空当前编辑器（不影响已保存草稿）？')) return;
    ['title','slug','brand','model','tags','score','cover','loan','excerpt'].forEach((k) => fields[k].value = '');
    Object.values(ratings).forEach((r) => r.value = '');
    fields.date.value = today();
    editor.value = '';
    slugTouched = false;
    renderPreview();
    saveActive();
  }

  // ---------- 顶部按钮 ----------
  $('draftBtn').addEventListener('click', saveDraft);
  $('exportBtn').addEventListener('click', exportMd);
  $('clearBtn').addEventListener('click', clearAll);

  // ---------- 提示 ----------
  let flashTimer = null;
  function flash(msg) {
    let el = document.getElementById('__flash');
    if (!el) {
      el = document.createElement('div');
      el.id = '__flash';
      el.style.cssText = 'position:fixed;left:50%;bottom:32px;transform:translateX(-50%);background:#16130F;color:#fff;font-family:var(--sans);font-size:13px;padding:10px 18px;border-radius:100px;z-index:999;box-shadow:0 6px 24px rgba(0,0,0,.18);opacity:0;transition:opacity .2s';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.opacity = '1';
    clearTimeout(flashTimer);
    flashTimer = setTimeout(() => { el.style.opacity = '0'; }, 1800);
  }

  // ---------- 启动 ----------
  loadActive();
  renderPreview();
  refreshDraftList();
})();
