# 引擎笔记 · ENGINE NOTES

车评人个人文章站。纯静态，无需数据库、无需服务器，生成出来的 `dist/` 可以直接双击打开，也可以丢到任何静态托管上。

## 三个动作

| 我想做什么 | 命令 |
|---|---|
| 写一篇新文章（手写） | 在 `content/` 里新建 `xxx.md`，复制任意一篇的头部字段，写完后 `python3 build.py` |
| 导入 Word / 旧稿 | 文件丢进 `inbox/`，跑 `python3 import_docs.py`，补全生成的字段，再 `python3 build.py` |
| 本地看效果 | `python3 build.py --serve`，打开 http://localhost:8765 |

## 改名字、改署名

只改 `site.yaml` 一个文件：署名、刊名、导航、社交链接、评分说明、RSS 域名，全在里面。

## 文章格式

每篇文章顶部是 YAML frontmatter，字段都能省（除了 title）：

```yaml
---
title: "小米 SU7 Ultra：赛道上这台车，比参数表更吓人"
slug: xiaomi-su7-ultra-track      # URL，省略则用文件名
date: 2026-06-12                   # 省略则用今天
brand: 小米                         # → 自动生成品牌归档页
model: SU7 Ultra
category: 赛道评测                  # → 首页栏目筛选
tags: [性能车, 纯电, 赛道]          # → 自动生成标签页
excerpt: "一句话导语"               # 卡片的摘要
verdict: "一句话结论"               # 文章页右侧高亮框
cover: covers/su7.jpg              # 可选，放到 assets/covers/ 下；留空则用排版封面
featured: true                     # 可选，指定首页首屏
draft: true                        # 草稿，不会发布
spec:                              # 参数表，随意增删
  动力形式: 纯电双电机四驱
  零百加速: 2.1 s
ratings:                           # 满分 10，综合分自动取平均
  动力: 9.5
  操控: 8.8
---
```

正文用 Markdown 写。`##` 二级标题会自动生成文章页右侧目录。

## 站点自带的功能

- **首屏轮播**：取 `featured: true` 的文章（最多 3 篇），自动播放 6.5 秒切换，支持点选、左右方向键、手机滑动
- **全站搜索**：输入即搜标题、摘要和正文关键词，下拉结果可直接跳转；按 `/` 聚焦，`Esc` 清空
- **筛选状态写进网址**：`?brand=小米&cat=长测报告&sort=score` 这样的链接可以直接分享
- **文章页**：顶部阅读进度条、右侧目录自动高亮当前小节、评分雷达图（自动生成 SVG）、参数表、一句话结论、图片点击放大、回到顶部
- **归档页**：按年份分组 + 年份快捷跳转
- **相关阅读**：同品牌 → 同标签 → 同栏目，三级兜底
- **SEO**：每篇文章带 Article 结构化数据（JSON-LD）、OG 描述、RSS 订阅

## 稿件里的图片

`import_docs.py` 会把 Word 里嵌入的图片按**原文顺序**抽出来，存到 `assets/covers/<slug>-01.jpg`、`-02.jpg`…，并在 Markdown 正文对应位置插入 `![配图](covers/xxx.jpg)`，首图自动设为封面。小于 12KB 的图（多半是图标）会忽略。

在 Markdown 里写图片路径时，用**相对 `assets/`** 的路径（如 `covers/xxx.jpg`），构建时会自动补上页面层级前缀。

## 示例文章

`content/sample/` 里放了一批演示用的示例车评（构建时不收录，因为构建只扫 `content/*.md`）。需要参考写法时打开看看，不需要就整个删掉。

## 封面图

- 有实拍图：放进 `assets/covers/`，在 frontmatter 写 `cover: covers/你的图.jpg`
- 没有图：自动生成排版封面（品牌 + 车型 + 栏目），色调按 slug 哈希，每篇不重样

## 目录结构

```
site.yaml          站点配置（唯一需要常改的文件）
build.py           生成器
import_docs.py     稿件导入（docx / doc / txt / md / 网页导出）
content/           文章（Markdown + frontmatter）
assets/app.css     浅色杂志风主题
assets/app.js      首页搜索 / 筛选 / 排序
templates/         HTML 模板（{{占位符}}）
inbox/             待导入的稿件
dist/              生成的站点 ← 这个就是成品
```

## 依赖

```bash
pip install markdown pyyaml python-docx
```

Python 3.9+ 即可，无前端构建步骤。
