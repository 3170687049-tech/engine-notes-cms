/* 引擎笔记 —— 首屏轮播 / 筛选排序 / 全站搜索 / 阅读体验
   纯原生 JS，无依赖，file:// 直接打开也能跑 */
(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  /* ============ 1. 首屏轮播 ============ */
  (function () {
    var hero = document.getElementById('hero');
    if (!hero) return;
    var slides = $$('.hero__link', hero);
    var dots = $$('.hero__dot', hero);
    if (slides.length < 2) return;

    var cur = 0, timer = null;

    function go(i) {
      cur = (i + slides.length) % slides.length;
      slides.forEach(function (s, k) { s.classList.toggle('is-active', k === cur); });
      dots.forEach(function (d, k) { d.classList.toggle('is-on', k === cur); });
    }
    function play() { stop(); timer = setInterval(function () { go(cur + 1); }, 6500); }
    function stop() { if (timer) clearInterval(timer); timer = null; }

    dots.forEach(function (d) {
      d.addEventListener('click', function () { go(+d.dataset.go); play(); });
    });
    hero.addEventListener('mouseenter', stop);
    hero.addEventListener('mouseleave', play);

    // 触屏左右滑动
    var x0 = null;
    hero.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
    hero.addEventListener('touchend', function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 45) { go(cur + (dx < 0 ? 1 : -1)); play(); }
      x0 = null;
    });

    // 键盘左右键
    document.addEventListener('keydown', function (e) {
      if (document.activeElement && /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return;
      if (e.key === 'ArrowRight') { go(cur + 1); stop(); }
      if (e.key === 'ArrowLeft') { go(cur - 1); stop(); }
    });

    play();
  })();

  /* ============ 2. 列表：搜索 / 筛选 / 排序 + URL 同步 ============ */
  (function () {
    var grid = document.getElementById('grid');
    if (!grid) return;
    var cards = $$('.card', grid);
    var input = document.getElementById('q');
    var sort = document.getElementById('sort');
    var count = document.getElementById('count');
    var empty = document.getElementById('noresult');
    var pop = document.getElementById('pop');
    var posts = window.__POSTS__ || [];

    var params = new URLSearchParams(location.search);
    var state = {
      q: params.get('q') || '',
      brand: params.get('brand') || '',
      cat: params.get('cat') || '',
      sort: params.get('sort') || 'date'
    };
    if (input) input.value = state.q;
    if (sort) sort.value = state.sort;

    function syncURL() {
      var p = new URLSearchParams();
      if (state.q) p.set('q', state.q);
      if (state.brand) p.set('brand', state.brand);
      if (state.cat) p.set('cat', state.cat);
      if (state.sort && state.sort !== 'date') p.set('sort', state.sort);
      var qs = p.toString();
      if (history.replaceState) {
        history.replaceState(null, '', qs ? '?' + qs : location.pathname);
      }
    }

    function apply() {
      var shown = 0;
      cards.forEach(function (card) {
        var hay = [card.dataset.title, card.dataset.brand, card.dataset.cat, card.dataset.tags]
          .join(' ').toLowerCase();
        var ok =
          (!state.q || hay.indexOf(state.q.toLowerCase()) > -1) &&
          (!state.brand || card.dataset.brand === state.brand) &&
          (!state.cat || card.dataset.cat === state.cat);
        card.hidden = !ok;
        if (ok) shown++;
      });

      if (state.sort === 'score') {
        cards.sort(function (a, b) { return (+b.dataset.score) - (+a.dataset.score); });
      } else if (state.sort === 'year') {
        cards.sort(function (a, b) {
          return b.dataset.year - a.dataset.year || b.dataset.date.localeCompare(a.dataset.date);
        });
      } else {
        cards.sort(function (a, b) { return b.dataset.date.localeCompare(a.dataset.date); });
      }
      cards.forEach(function (c) { grid.appendChild(c); });

      // 计数用全站数据（首屏轮播里的文章不在卡片网格中）
      if (count) {
        var n = shown;
        if (posts.length) {
          n = posts.filter(function (p) {
            var hay = (p.t + ' ' + p.b + ' ' + p.m + ' ' + p.c + ' ' + (p.g || []).join(' ') + ' ' + p.e + ' ' + (p.x || '')).toLowerCase();
            return (!state.q || hay.indexOf(state.q.toLowerCase()) > -1) &&
              (!state.brand || p.b === state.brand) &&
              (!state.cat || p.c === state.cat);
          }).length;
        }
        count.textContent = '共 ' + n + ' 篇';
      }
      if (empty) empty.hidden = shown !== 0;
      syncURL();
    }

    // 还原 URL 里的筛选状态
    if (state.brand || state.cat) {
      $$('.chips .chip').forEach(function (c) {
        var f = c.dataset.filter, v = c.dataset.value;
        if (f && v === state[f]) {
          c.parentNode.querySelectorAll('.chip').forEach(function (x) { x.classList.remove('is-on'); });
          c.classList.add('is-on');
        }
      });
    }
    apply();

    /* ---- 全站搜索下拉（标题 / 摘要 / 正文关键词） ---- */
    function highlight(text, q) {
      var i = text.toLowerCase().indexOf(q.toLowerCase());
      if (i < 0) return text;
      return text.slice(0, i) + '<mark>' + text.slice(i, i + q.length) + '</mark>' + text.slice(i + q.length);
    }

    function renderPop() {
      var q = state.q.trim();
      if (!q) { pop.hidden = true; pop.innerHTML = ''; return; }
      var base = document.body.dataset.base || '';
      var hits = posts.filter(function (p) {
        return (p.t + ' ' + p.b + ' ' + p.m + ' ' + p.c + ' ' + (p.g || []).join(' ') + ' ' + p.e + ' ' + (p.x || ''))
          .toLowerCase().indexOf(q.toLowerCase()) > -1;
      }).slice(0, 8);

      pop.innerHTML = hits.length
        ? hits.map(function (p) {
            return '<a class="pop__item" href="' + base + p.u + '">' +
              '<span class="pop__t">' + highlight(p.t, q) + '</span>' +
              '<span class="pop__m">' + p.d + ' · ' + p.b + ' ' + p.m + (p.v ? ' · ' + p.v + ' 分' : '') + '</span></a>';
          }).join('')
        : '<p class="pop__empty">没找到相关文章</p>';
      pop.hidden = false;
    }

    if (input && pop) {
      input.addEventListener('input', function () {
        state.q = input.value.trim();
        apply();
        renderPop();
      });
      input.addEventListener('focus', function () { if (state.q.trim()) renderPop(); });
      document.addEventListener('click', function (e) {
        if (!e.target.closest('.search')) pop.hidden = true;
      });
    }

    if (sort) sort.addEventListener('change', function () { state.sort = sort.value; apply(); });

    $$('.chips').forEach(function (group) {
      group.addEventListener('click', function (e) {
        var chip = e.target.closest('.chip');
        if (!chip) return;
        var f = chip.dataset.filter, v = chip.dataset.value;
        var on = chip.classList.contains('is-on');
        $$('.chip', group).forEach(function (c) { c.classList.remove('is-on'); });
        chip.classList.add('is-on');
        state[f] = on ? '' : (v || '');
        apply();
      });
    });

    document.addEventListener('keydown', function (e) {
      if (!input) return;
      if (e.key === '/' && document.activeElement !== input) { e.preventDefault(); input.focus(); }
      if (e.key === 'Escape' && document.activeElement === input) {
        input.value = ''; state.q = ''; apply(); renderPop(); input.blur();
      }
    });
  })();

  /* ============ 3. 文章页：阅读进度 / 目录高亮 / 回到顶部 / 图片灯箱 ============ */
  (function () {
    var body = document.querySelector('.post__body');
    if (!body) return;

    // 阅读进度
    var bar = document.querySelector('.progress i');
    var top = document.getElementById('totop');
    var links = $$('.tocbox a');
    var heads = links.map(function (a) { return document.getElementById(decodeURIComponent(a.hash.slice(1))); });

    function onScroll() {
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      var pct = max > 0 ? (h.scrollTop / max) * 100 : 0;
      if (bar) bar.style.width = pct.toFixed(2) + '%';
      if (top) top.classList.toggle('is-on', h.scrollTop > 600);

      // 目录高亮当前小节
      var idx = -1;
      heads.forEach(function (el, i) { if (el && el.getBoundingClientRect().top < 140) idx = i; });
      links.forEach(function (a, i) { a.classList.toggle('is-cur', i === idx); });
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    onScroll();

    if (top) top.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });

    // 图片点击放大
    var box = document.getElementById('lightbox');
    if (box) {
      $$('img', body).forEach(function (img) {
        img.style.cursor = 'zoom-in';
        img.addEventListener('click', function () {
          box.querySelector('img').src = img.src;
          box.querySelector('img').alt = img.alt || '';
          box.hidden = false;
        });
      });
      box.addEventListener('click', function () { box.hidden = true; });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') box.hidden = true;
      });
    }
  })();

  /* ============ 4. 归档页：年份快捷跳转高亮 ============ */
  (function () {
    var nav = document.querySelector('.yearnav');
    if (!nav) return;
    nav.addEventListener('click', function (e) {
      var a = e.target.closest('a');
      if (!a) return;
      $$('a', nav).forEach(function (x) { x.classList.remove('is-on'); });
      a.classList.add('is-on');
    });
  })();
})();
