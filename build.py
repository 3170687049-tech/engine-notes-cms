# -*- coding: utf-8 -*-
"""
引擎笔记 ENGINE NOTES —— 静态站点生成器

用法：
    python3 build.py              # 构建到 dist/
    python3 build.py --serve      # 构建并启动本地预览服务器

依赖：markdown, pyyaml
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html as html_lib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"
TEMPLATES = ROOT / "templates"
DIST = ROOT / "dist"

try:
    import yaml
    import markdown
except ImportError:
    sys.exit("缺少依赖，请先运行： pip install markdown pyyaml")


# ---------------------------------------------------------------
# 工具
# ---------------------------------------------------------------
def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


TOKEN_RE = re.compile(r"\{\{(\w+)\}\}")


def render(tpl_text: str, **kw) -> str:
    """用 {{KEY}} 占位符渲染（比 str.format / string.Template 安全，正文里任何符号都不冲突）。"""

    def _sub(m):
        v = kw.get(m.group(1), "")
        return "" if v is None else str(v)

    return TOKEN_RE.sub(_sub, tpl_text)


def tpl(name: str) -> str:
    return read_text(TEMPLATES / name)


FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)


def fmt_date(d: dt.date) -> str:
    return f"{d.year} 年 {d.month} 月 {d.day} 日"


def parse_post(path: Path) -> dict | None:
    raw = read_text(path)
    m = FM_RE.match(raw)
    if not m:
        print(f"  ! 跳过（缺少 frontmatter）：{path.name}")
        return None
    meta = yaml.safe_load(m.group(1)) or {}

    md = markdown.Markdown(
        extensions=["extra", "toc", "sane_lists", "smarty"],
        extension_configs={"toc": {"permalink": False, "toc_depth": "2-3"}},
    )
    body_html = md.convert(raw[m.end():])

    title = (meta.get("title") or path.stem).strip()
    slug = str(meta.get("slug") or path.stem).strip()

    date_raw = meta.get("date")
    if isinstance(date_raw, dt.datetime):
        date = date_raw.date()
    elif isinstance(date_raw, dt.date):
        date = date_raw
    elif isinstance(date_raw, str):
        date = dt.datetime.strptime(str(date_raw), "%Y-%m-%d").date()
    else:
        date = dt.date.today()

    ratings = {str(k): float(v) for k, v in (meta.get("ratings") or {}).items()}
    score = round(sum(ratings.values()) / len(ratings), 1) if ratings else None

    plain = html_lib.unescape(re.sub(r"<[^>]+>", "", body_html))
    plain = re.sub(r"\s+", " ", plain).strip()
    words = len(re.sub(r"\s", "", plain))

    return {
        "title": title,
        "slug": slug,
        "date": date,
        "date_str": fmt_date(date),
        "date_iso": date.isoformat(),
        "year": date.year,
        "excerpt": str(meta.get("excerpt") or "").strip(),
        "author": str(meta.get("author") or "").strip(),
        "brand": str(meta.get("brand") or "").strip(),
        "model": str(meta.get("model") or "").strip(),
        "category": str(meta.get("category") or "评测").strip(),
        "tags": [str(t) for t in (meta.get("tags") or [])],
        "verdict": str(meta.get("verdict") or "").strip(),
        "spec": meta.get("spec") or {},
        "ratings": ratings,
        "score": score,
        "cover": str(meta.get("cover") or "").strip(),
        "cover_alt": str(meta.get("cover_alt") or "").strip(),
        "featured": bool(meta.get("featured")),
        "draft": bool(meta.get("draft")),
        "body": body_html,
        "plain": plain[:4000],
        "toc": md.toc,
        "words": words,
        "minutes": max(1, round(words / 400)),
        "source_file": path.name,
        "cover_resolved": "",
    }


def hue(s: str) -> int:
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:6], 16) % 360


def cover_block(post: dict, mod: str = "", prefix: str = "") -> str:
    """封面：有真实照片用照片，没有则生成排版封面（永远不会开天窗）。"""
    if post.get("cover_resolved"):
        alt = post.get("cover_alt") or post["title"]
        return (
            f'<figure class="cover cover--photo {mod}">'
            f'<img src="{prefix}{post["cover_resolved"]}" alt="{html_lib.escape(alt)}" loading="lazy">'
            f"</figure>"
        )
    h = hue(post["slug"] + post["brand"])
    return (
        f'<figure class="cover cover--type {mod}" style="--h:{h}">'
        f'<span class="cover__stripes" aria-hidden="true"></span>'
        f'<span class="cover__grain" aria-hidden="true"></span>'
        f'<figcaption>'
        f'<span class="cover__brand">{html_lib.escape(post["brand"] or post["category"])}</span>'
        f'<span class="cover__model">{html_lib.escape(post["model"] or post["title"][:12])}</span>'
        f'<span class="cover__cat">{html_lib.escape(post["category"])}</span>'
        f"</figcaption></figure>"
    )


def radar_svg(ratings: dict, size: int = 260) -> str:
    """评分雷达图（纯 SVG，不依赖任何图表库）。"""
    keys = list(ratings.keys())
    n = len(keys)
    if n < 3:
        return ""
    cx = cy = size / 2
    r = size / 2 - 34
    import math

    def pt(i, v):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        return cx + math.cos(ang) * r * (v / 10), cy + math.sin(ang) * r * (v / 10)

    rings = ""
    for lvl in (2, 4, 6, 8, 10):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, lvl) for i in range(n)))
        rings += (
            f'<polygon points="{pts}" fill="none" stroke="#E5DFD5" stroke-width="1"'
            + (' stroke-dasharray="2 3"' if lvl != 10 else "")
            + "/>"
        )

    spokes = "".join(
        f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#E5DFD5" stroke-width="1"/>'
        for x, y in (pt(i, 10) for i in range(n))
    )

    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, ratings[k]) for i, k in enumerate(keys)))
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="#B3261E"/>'
        for x, y in (pt(i, ratings[k]) for i, k in enumerate(keys))
    )

    labels = ""
    for i, k in enumerate(keys):
        x, y = pt(i, 11.9)
        anchor = "start" if x > cx + 4 else ("end" if x < cx - 4 else "middle")
        labels += (
            f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" dominant-baseline="middle" '
            f'font-size="10.5" fill="#817A70" font-family="PingFang SC, sans-serif">'
            f'{html_lib.escape(k)}</text>'
        )

    return (
        f'<svg class="radar" viewBox="0 0 {size} {size}" role="img" '
        f'aria-label="各维度评分雷达图">{rings}{spokes}'
        f'<polygon points="{poly}" fill="rgba(179,38,30,.14)" stroke="#B3261E" stroke-width="1.6"/>'
        f"{dots}{labels}</svg>"
    )


def rating_bars(ratings: dict) -> str:
    if not ratings:
        return ""
    items = "".join(
        f'<li class="bar"><span class="bar__k">{html_lib.escape(k)}</span>'
        f'<span class="bar__track"><i style="width:{max(0, min(100, v / 10 * 100)):.1f}%"></i></span>'
        f'<span class="bar__v">{v:g}</span></li>'
        for k, v in ratings.items()
    )
    return f'<ul class="bars">{items}</ul>'


def spec_table(spec: dict) -> str:
    if not spec:
        return ""
    rows = "".join(
        f"<tr><th>{html_lib.escape(str(k))}</th><td>{html_lib.escape(str(v))}</td></tr>"
        for k, v in spec.items()
    )
    return f'<table class="spec"><tbody>{rows}</tbody></table>'


# ---------------------------------------------------------------
# 片段（prefix = 相对 dist 根目录的路径前缀，保证 file:// 直接打开也能用）
# ---------------------------------------------------------------
def card_html(p: dict, prefix: str = "", size: str = "") -> str:
    score = f'<span class="card__score">{p["score"]:g}<i>分</i></span>' if p["score"] else ""
    tags = "".join(f"<li>#{html_lib.escape(t)}</li>" for t in p["tags"][:3])
    return (
        f'<article class="card {size}" data-brand="{html_lib.escape(p["brand"])}"'
        f' data-cat="{html_lib.escape(p["category"])}" data-year="{p["year"]}"'
        f' data-title="{html_lib.escape(p["title"])}"'
        f' data-tags="{html_lib.escape(",".join(p["tags"]))}"'
        f' data-score="{p["score"] or 0}" data-date="{p["date_iso"]}">'
        f'<a class="card__link" href="{prefix}posts/{quote(p["slug"])}.html">'
        f"{cover_block(p, prefix=prefix)}"
        f'<div class="card__body">'
        f'<p class="card__kicker"><span>{html_lib.escape(p["category"])}</span>'
        f'<em>{html_lib.escape(p["brand"])} {html_lib.escape(p["model"])}</em></p>'
        f'<h3 class="card__title">{html_lib.escape(p["title"])}</h3>'
        f'<p class="card__excerpt">{html_lib.escape(p["excerpt"])}</p>'
        f'<p class="card__meta"><time>{p["date_iso"]}</time> · {p["minutes"]} 分钟读完 {score}</p>'
        f'<ul class="card__tags">{tags}</ul>'
        f"</div></a></article>"
    )


def chips_html(filters: dict, kind: str, prefix: str = "") -> str:
    key = "brands" if kind == "brand" else "cats"
    label = "全部品牌" if kind == "brand" else "全部栏目"
    out = [f'<button class="chip is-on" data-filter="{kind}" data-value="">{label}</button>']
    for v in filters[key]:
        out.append(
            f'<button class="chip" data-filter="{kind}"'
            f' data-value="{html_lib.escape(v)}">{html_lib.escape(v)}</button>'
        )
    return "".join(out)


def rows_html(posts: list[dict], prefix: str = "", show_model: bool = True) -> str:
    return "".join(
        f'<li><a href="{prefix}posts/{quote(p["slug"])}.html">'
        f'<span class="row__date">{p["date_iso"]}</span>'
        f'<span class="row__title">{html_lib.escape(p["title"])}</span>'
        f'<span class="row__meta">{html_lib.escape(p["model"] if show_model else p["brand"])}</span>'
        + (f'<span class="row__score">{p["score"]:g}</span>' if p["score"] else "<span></span>")
        + "</a></li>"
        for p in posts
    )


def nav_html(site: dict, prefix: str = "") -> str:
    items = "".join(
        f'<a href="{prefix}{n["href"]}">{html_lib.escape(n["label"])}</a>'
        for n in (site.get("nav") or [])
    )
    return f'<nav class="mast__nav">{items}</nav>' if items else ""


def avatar_block(site: dict, avatar: str, prefix: str = "", big: bool = False) -> str:
    cls = "avatar__img avatar__img--big" if big else "avatar__img"
    if avatar:
        return f'<img class="{cls}" src="{prefix}{avatar}" alt="{html_lib.escape(site["author"])}">'
    initial = html_lib.escape(site["author"][:1] or "K")
    return f'<span class="{cls} avatar__mono" aria-hidden="true">{initial}</span>'


def links_html(site: dict) -> str:
    return "".join(
        f'<a href="{html_lib.escape(l["url"])}" rel="noopener">{html_lib.escape(l["label"])}</a>'
        for l in (site.get("links") or [])
        if l.get("url")
    )


def head_html(site: dict, title: str, desc: str, prefix: str, jsonld: str = "") -> str:
    return render(
        tpl("partials/head.html"),
        TITLE=title,
        SITE=site["title"],
        DESC=desc or site.get("tagline", ""),
        P=prefix,
        JSONLD=jsonld,
    )


def footer_html(site: dict, prefix: str) -> str:
    return render(
        tpl("partials/footer.html"),
        P=prefix,
        AUTHOR=site["author"],
        YEAR=dt.date.today().year,
        TITLE=site["title"],
        SUBTITLE=site.get("subtitle", ""),
        LINKS=links_html(site),
        SINCE=site.get("since_year", ""),
    )


def top_scores_html(posts: list[dict], prefix: str = "") -> str:
    ranked = sorted([p for p in posts if p["score"]], key=lambda x: -x["score"])[:5]
    return "".join(
        f'<li><a href="{prefix}posts/{quote(p["slug"])}.html">'
        f'<span class="rank__n">{i + 1:02d}</span>'
        f'<span class="rank__t">{html_lib.escape(p["title"])}</span>'
        f'<span class="rank__v">{p["score"]:g}</span></a></li>'
        for i, p in enumerate(ranked)
    )


def latest_list_html(posts: list[dict], prefix: str = "") -> str:
    return "".join(
        f'<li><a href="{prefix}posts/{quote(p["slug"])}.html">'
        f"<time>{p['date_iso']}</time>"
        f'<em>{html_lib.escape(p["title"])}</em></a></li>'
        for p in posts
    )


# ---------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------
def build() -> None:
    site = yaml.safe_load(read_text(ROOT / "site.yaml"))
    base_tpl = tpl("base.html")

    posts = []
    # 扫描 content/*.md（现有 7 篇 + _about）
    for md_file in sorted(CONTENT.glob("*.md")):
        if md_file.name.startswith("_"):
            continue
        p = parse_post(md_file)
        if p:
            posts.append(p)
    # 同时扫描仓库根目录的 posts/*.md（Sveltia CMS 写入位置）
    for md_file in sorted((ROOT / "posts").glob("*.md")):
        if md_file.name.startswith("_"):
            continue
        p = parse_post(md_file)
        if p:
            posts.append(p)

    drafts = [p for p in posts if p["draft"]]
    posts = [p for p in posts if not p["draft"]]
    posts.sort(key=lambda x: x["date_iso"], reverse=True)
    total = len(posts)
    print(f"· 载入文章 {total} 篇" + (f"（另有 {len(drafts)} 篇草稿未发布）" if drafts else ""))

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "assets").mkdir(parents=True)

    write_text(DIST / "assets" / "app.css", read_text(ASSETS / "app.css"))
    write_text(DIST / "assets" / "app.js", read_text(ASSETS / "app.js"))
    compose_js = ASSETS / "compose.js"
    if compose_js.exists():
        write_text(DIST / "assets" / "compose.js", read_text(compose_js))

    cov_src = ASSETS / "covers"
    if cov_src.exists():
        shutil.copytree(cov_src, DIST / "assets" / "covers")

    # Sveltia CMS 上传的图片目录（与 admin/index.html 的 media_folder 对齐）
    img_src = ASSETS / "images"
    if img_src.exists():
        shutil.copytree(img_src, DIST / "assets" / "images")

    # Sveltia CMS admin/ 目录（演示用，Git-based WYSIWYG 编辑器）
    admin_src = ROOT / "admin"
    if admin_src.exists():
        shutil.copytree(admin_src, DIST / "admin")

    for p in posts:
        if p["cover"]:
            src = ASSETS / p["cover"]
            if src.exists():
                dst = DIST / "assets" / Path(p["cover"]).parent
                dst.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst / src.name)
                p["cover_resolved"] = f'assets/{Path(p["cover"]).as_posix()}'

    avatar = ""
    if site.get("author_avatar"):
        av = ASSETS / site["author_avatar"]
        if av.exists():
            shutil.copy2(av, DIST / "assets" / Path(site["author_avatar"]).name)
            avatar = f'assets/{Path(site["author_avatar"]).name}'

    filters = {
        "brands": sorted({p["brand"] for p in posts if p["brand"]}),
        "cats": sorted({p["category"] for p in posts if p["category"]}),
        "tags": sorted({t for p in posts for t in p["tags"]}),
    }

    def mast(prefix: str) -> str:
        return render(
            tpl("partials/masthead.html"),
            P=prefix,
            SITE_TITLE=site["title"],
            SUBTITLE=site.get("subtitle", ""),
            AUTHOR=site["author"],
            ISSUE=site.get("issue_label", ""),
            DATE_TODAY=dt.date.today().strftime("%Y.%m.%d"),
            TAGLINE=site.get("tagline", ""),
            NAV=nav_html(site, prefix),
        )

    def page(body: str, title: str, desc: str = "", prefix: str = "", jsonld: str = "") -> str:
        return render(
            base_tpl,
            HEAD=head_html(site, title, desc, prefix, jsonld),
            NAV=nav_html(site, prefix),
            MASTHEAD=mast(prefix),
            FOOTER=footer_html(site, prefix),
            BODY=body,
            P=prefix,
        )

    # ---------- 首页 ----------
    # 首屏轮播：优先 featured_slug → featured: true 的文章 → 最新的几篇
    slides: list[dict] = []
    if site.get("featured_slug"):
        hit = next((p for p in posts if p["slug"] == site["featured_slug"]), None)
        if hit:
            slides.append(hit)
    slides += [p for p in posts if p["featured"] and p not in slides]
    slides += [p for p in posts if p not in slides]
    slides = slides[:3]

    slide_html, dot_html = "", ""
    for i, p in enumerate(slides):
        slide_html += render(
            tpl("partials/hero-slide.html"),
            ACTIVE=" is-active" if i == 0 else "",
            COVER=cover_block(p, "is-hero"),
            HREF=f'posts/{quote(p["slug"])}.html',
            KICKER=f'{p["category"]} · {p["brand"]} {p["model"]}',
            TITLE=p["title"],
            EXCERPT=p["excerpt"],
            DATE=p["date_iso"],
            MINUTES=p["minutes"],
            SCORE=f'{p["score"]:g}' if p["score"] else "",
        )
        dot_html += (
            f'<button class="hero__dot{" is-on" if i == 0 else ""}" data-go="{i}" '
            f'aria-label="第 {i + 1} 篇">{p["brand"]} {html_lib.escape(p["model"])}</button>'
        )

    hero = ""
    if slide_html:
        hero = render(
            tpl("partials/hero.html"),
            SLIDES=slide_html,
            DOTS=dot_html,
            N=len(slides),
        )

    used = {p["slug"] for p in slides}
    rest = [p for p in posts if p["slug"] not in used]
    cards = "".join(card_html(p, "", "card--wide" if i < 2 else "") for i, p in enumerate(rest))
    years = sorted({p["year"] for p in posts})

    index_body = render(
        tpl("index.html"),
        AUTHOR=site["author"],
        TAGLINE=site.get("tagline", ""),
        TOTAL=total,
        STAT_BRANDS=len(filters["brands"]),
        STAT_YEARS=len(years),
        STAT_WORDS=round(sum(p["words"] for p in posts) / 10000, 1),
        HERO=hero,
        CARDS=cards or '<p class="empty">还没有文章。把 Word 丢进 inbox/ 后运行 python3 import_docs.py。</p>',
        CHIPS_BRAND=chips_html(filters, "brand"),
        CHIPS_CAT=chips_html(filters, "cat"),
        AUTHOR_BIO=site.get("author_bio", ""),
        AVATAR=avatar,
        RANK_PANEL=(
            '<section class="panel"><h3 class="panel__t">评分榜 <span>Scoreboard</span></h3>'
            f'<ol class="rank">{top_scores_html(posts)}</ol>'
            f'<p class="panel__note">{html_lib.escape(site.get("rating_hint", ""))}</p></section>'
            if any(p["score"] for p in posts)
            else ""
        ),
        LATEST_LIST=latest_list_html(posts[:6]),
        BRAND_LIST="".join(
            f'<a class="pill" href="brands/{quote(b)}.html">{html_lib.escape(b)}'
            f'<i>{len([p for p in posts if p["brand"] == b])}</i></a>'
            for b in filters["brands"]
        ),
    )
    write_text(
        DIST / "index.html",
        page(index_body, f'{site["title"]} · {site.get("tagline", "")}', site.get("tagline", "")),
    )

    # ---------- 归档 ----------
    by_year: dict[int, list] = {}
    for p in posts:
        by_year.setdefault(p["year"], []).append(p)
    years_desc = sorted(by_year, reverse=True)
    year_blocks = "".join(
        f'<section class="yeargroup" id="y{y}">'
        f'<h2 class="yeargroup__n">{y}<i>{len(by_year[y])} 篇</i></h2>'
        f'<ul class="rows">{rows_html(by_year[y])}</ul></section>'
        for y in years_desc
    )
    year_nav = "".join(
        f'<a href="#y{y}">{y}<i>{len(by_year[y])}</i></a>' for y in years_desc
    )
    archive_body = render(
        tpl("archive.html"),
        TOTAL=total,
        HEADING="全部文章",
        SUB=f"按发表年份倒序，共 {total} 篇",
        ROWS=year_blocks or '<p class="empty">还没有文章。</p>',
        YEAR_NAV=year_nav,
        CHIPS_BRAND=chips_html(filters, "brand"),
        ROWS_FLAT="",
    )
    write_text(
        DIST / "archive.html",
        page(archive_body, f'全部文章 · {site["title"]}'),
    )

    # ---------- 品牌页 / 标签页 ----------
    for b in filters["brands"]:
        sub = [p for p in posts if p["brand"] == b]
        body = render(
            tpl("archive.html"),
            TOTAL=len(sub),
            HEADING=b,
            SUB=f"共 {len(sub)} 篇评测",
            ROWS=f'<section class="yeargroup"><ul class="rows">{rows_html(sub, "../", show_model=True)}</ul></section>',
            CHIPS_BRAND=chips_html(filters, "brand", "../"),
            ROWS_FLAT="",
        )
        write_text(
            DIST / "brands" / f"{b}.html",
            page(body, f"{b} · {site['title']}", "", "../"),
        )

    for t in filters["tags"]:
        sub = [p for p in posts if t in p["tags"]]
        body = render(
            tpl("archive.html"),
            TOTAL=len(sub),
            HEADING=f"#{t}",
            SUB=f"共 {len(sub)} 篇",
            ROWS=f'<section class="yeargroup"><ul class="rows">{rows_html(sub, "../", show_model=False)}</ul></section>',
            CHIPS_BRAND=chips_html(filters, "brand", "../"),
            ROWS_FLAT="",
        )
        write_text(
            DIST / "tags" / f"{t}.html",
            page(body, f"#{t} · {site['title']}", "", "../"),
        )

    # ---------- 文章页 ----------
    for i, p in enumerate(posts):
        prev_p = posts[i + 1] if i + 1 < len(posts) else None
        next_p = posts[i - 1] if i - 1 >= 0 else None
        # 相关阅读：同品牌优先 → 同标签次之 → 同栏目兜底
        related = [q for q in posts if q["slug"] != p["slug"] and q["brand"] == p["brand"]][:3]
        if len(related) < 3:
            same_tag = [
                q for q in posts
                if q["slug"] != p["slug"] and q not in related
                and set(q["tags"]) & set(p["tags"])
            ]
            related += same_tag[: 3 - len(related)]
        if len(related) < 3:
            same_cat = [
                q for q in posts
                if q["slug"] != p["slug"] and q not in related and q["category"] == p["category"]
            ]
            related += same_cat[: 3 - len(related)]

        nav_links = ""
        if next_p:
            nav_links += (
                f'<a class="pn__item" href="{quote(next_p["slug"])}.html">'
                f'<span>更新的一篇</span><em>{html_lib.escape(next_p["title"])}</em></a>'
            )
        if prev_p:
            nav_links += (
                f'<a class="pn__item pn--next" href="{quote(prev_p["slug"])}.html">'
                f'<span>更早的一篇</span><em>{html_lib.escape(prev_p["title"])}</em></a>'
            )

        tag_links = "".join(
            f'<a class="tag" href="../tags/{quote(t)}.html">#{html_lib.escape(t)}</a>'
            for t in p["tags"]
        )

        scorecard = ""
        if p["score"]:
            scorecard = (
                f'<div class="scorecard">'
                f'<p class="scorecard__k">综合评分</p>'
                f'<p class="scorecard__v">{p["score"]:g}<i>/10</i></p>'
                f'{radar_svg(p["ratings"])}'
                f"{rating_bars(p['ratings'])}"
                f'<p class="scorecard__hint">{html_lib.escape(site.get("rating_hint", ""))}</p>'
                f"</div>"
            )

        verdict_box = ""
        if p["verdict"]:
            verdict_box = (
                f'<div class="verdict"><p class="verdict__k">一句话</p>'
                f'<p class="verdict__t">{html_lib.escape(p["verdict"])}</p></div>'
            )

        toc_box = (
            f'<details class="tocbox" open><summary>本文目录</summary>{p["toc"]}</details>'
            if p["toc"].strip()
            else ""
        )

        # 正文里的配图路径：Markdown 里写 covers/xxx.jpg（相对 assets/），
        # 这里按页面层级补上前缀，保证 file:// 打开也不失效
        body_html = re.sub(
            r'(<img[^>]+src=")(?!https?:|//|/|\.\./)([^"]+)"',
            r'\g<1>../assets/\g<2>"',
            p["body"],
        )

        post_body = render(
            tpl("post.html"),
            TITLE=p["title"],
            KICKER=f'{p["category"]} · {p["brand"]} {p["model"]}',
            EXCERPT=p["excerpt"],
            DATE=p["date_str"],
            AUTHOR=p["author"] or site["author"],
            MINUTES=p["minutes"],
            WORDS=p["words"],
            COVER=cover_block(p, "is-post", "../"),
            SCORECARD=scorecard,
            SPEC=spec_table(p["spec"]),
            VERDICT_BOX=verdict_box,
            TOC_BOX=toc_box,
            BODY=body_html,
            TAGS=tag_links,
            BRAND=p["brand"],
            BRAND_HREF=f'../brands/{quote(p["brand"])}.html' if p["brand"] else "#",
            NAV_LINKS=nav_links,
            RELATED="".join(card_html(r, "../") for r in related),
            RATING_HINT=site.get("rating_hint", ""),
            TOC=p["toc"],
        )
        base = str(site.get("base_url", "")).rstrip("/")
        jsonld = json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": p["title"],
                "datePublished": p["date_iso"],
                "author": {"@type": "Person", "name": p["author"] or site["author"]},
                "description": p["excerpt"],
                "articleSection": p["category"],
                "keywords": ", ".join(p["tags"]),
                "url": f"{base}/posts/{quote(p['slug'])}.html",
            },
            ensure_ascii=False,
        )
        write_text(
            DIST / "posts" / f"{p['slug']}.html",
            page(
                post_body,
                f'{p["title"]} · {site["title"]}',
                p["excerpt"],
                "../",
                f'<script type="application/ld+json">{jsonld}</script>',
            ),
        )

    # ---------- 关于页 ----------
    about_md = CONTENT / "_about.md"
    about_md_html = ""
    if about_md.exists():
        about_md_html = markdown.Markdown(extensions=["extra", "smarty"]).convert(read_text(about_md))
    about_body = render(
        tpl("about.html"),
        AUTHOR=site["author"],
        BIO=site.get("author_bio", ""),
        AVATAR_BLOCK=avatar_block(site, avatar, big=True),
        SITE=site["title"],
        SUBTITLE=site.get("subtitle", ""),
        SINCE=site.get("since_year", ""),
        TOTAL=total,
        BRANDS=len(filters["brands"]),
        ABOUT_MD=about_md_html,
        LINKS=links_html(site),
        LINKS2=links_html(site),
        LATEST_LIST=latest_list_html(posts[:8]),
    )
    write_text(DIST / "about.html", page(about_body, f'关于 {site["author"]} · {site["title"]}'))

    # ---------- 撰稿页 compose ----------
    compose_body = render(tpl("compose.html"))
    write_text(DIST / "compose.html", page(compose_body, f'撰稿 · {site["title"]}'))

    # ---------- 搜索索引（file:// 直接打开也能搜索） ----------
    index_data = [
        {
            "t": p["title"],
            "u": f'posts/{quote(p["slug"])}.html',
            "d": p["date_iso"],
            "b": p["brand"],
            "m": p["model"],
            "c": p["category"],
            "g": p["tags"],
            "e": p["excerpt"],
            "v": p["score"] or 0,
            "x": p["plain"][:700],
        }
        for p in posts
    ]
    write_text(
        DIST / "search-index.js",
        "window.__POSTS__=" + json.dumps(index_data, ensure_ascii=False) + ";",
    )

    # ---------- RSS ----------
    if site.get("rss"):
        base = str(site.get("base_url", "")).rstrip("/")
        items = "".join(
            "<item><title>{}</title><link>{}/posts/{}.html</link><guid>{}/posts/{}.html</guid>"
            "<pubDate>{}</pubDate><description>{}</description></item>".format(
                html_lib.escape(p["title"]),
                base,
                quote(p["slug"]),
                base,
                quote(p["slug"]),
                p["date"].strftime("%a, %d %b %Y 00:00:00 +0800"),
                html_lib.escape(p["excerpt"]),
            )
            for p in posts[:30]
        )
        write_text(
            DIST / "rss.xml",
            '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            f"<title>{html_lib.escape(site['title'])}</title><link>{base}/</link>"
            f"<description>{html_lib.escape(site.get('tagline', ''))}</description>"
            f"{items}</channel></rss>",
        )

    print(f"· 生成完毕 → {DIST}")
    print(
        f"  首页 index.html ｜ 文章 {total} 篇 ｜ 品牌 {len(filters['brands'])} 个"
        f" ｜ 标签 {len(filters['tags'])} 个 ｜ 页面 {total + 3 + len(filters['brands']) + len(filters['tags'])} 个（含 compose.html）"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true", help="构建后启动本地预览服务")
    a = ap.parse_args()
    build()
    if a.serve:
        import http.server
        import socketserver

        os.chdir(DIST)
        PORT = 8765
        socketserver.TCPServer.allow_reuse_address = True
        print(f"· 预览地址： http://localhost:{PORT}/")
        with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
            httpd.serve_forever()
