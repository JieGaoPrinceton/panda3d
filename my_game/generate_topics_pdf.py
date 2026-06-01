#!/usr/bin/env python3
"""
生成 Panda3D 专题整合 PDF
科研配色 + 白色底图表 + 打印友好
"""

import os
import re
import sys
import subprocess

# ── 依赖检查 ──────────────────────────────────────────────────────────────────
try:
    import markdown
    from markdown.extensions.tables import TableExtension
    from markdown.extensions.fenced_code import FencedCodeExtension
    from markdown.extensions.codehilite import CodeHiliteExtension
    from markdown.extensions.toc import TocExtension
except ImportError:
    print("安装依赖: pip install markdown pygments")
    sys.exit(1)

# ── 路径配置 ──────────────────────────────────────────────────────────────────
TOPICS_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "topics")
OUTPUT_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panda3d_topics_integrated.html")
OUTPUT_PDF  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panda3d_topics_integrated.pdf")

topic_files = sorted([f for f in os.listdir(TOPICS_DIR) if f.endswith(".md")])
print(f"找到 {len(topic_files)} 个专题文件")

# ── 预处理 Markdown ────────────────────────────────────────────────────────────
def preprocess_md(content: str) -> str:
    lines = content.split("\n")
    result = []
    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            result.append("## " + line[2:].strip())
        else:
            result.append(line)
    return "\n".join(result)

chapters = []
for fname in topic_files:
    fpath = os.path.join(TOPICS_DIR, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.match(r"(\d+)_", fname)
    num = int(m.group(1)) if m else 0
    chapters.append((num, fname, content))

full_md_parts = []
for num, fname, content in chapters:
    full_md_parts.append(preprocess_md(content))
    full_md_parts.append("\n\n---\n\n")

full_md = "\n\n".join(full_md_parts)

# ── Markdown → HTML ───────────────────────────────────────────────────────────
md_proc = markdown.Markdown(extensions=[
    TableExtension(),
    FencedCodeExtension(),
    CodeHiliteExtension(linenums=False, css_class="highlight", guess_lang=False),
    TocExtension(toc_depth="2-3"),
    "extra",
    "sane_lists",
])

body_html = md_proc.convert(full_md)

# ── CSS 样式 ──────────────────────────────────────────────────────────────────
CSS = """
:root {
  --color-primary:      #1a3a5c;
  --color-primary-light:#2c5f8a;
  --color-primary-pale: #e8f0f8;
  --color-accent:       #c0392b;
  --color-text:         #1a1a2e;
  --color-text-muted:   #4a5568;
  --color-border:       #c8d6e5;
  --color-bg:           #ffffff;
  --color-bg-alt:       #f7f9fc;
  --font-serif:   "Georgia", "Times New Roman", serif;
  --font-sans:    "Helvetica Neue", "Arial", sans-serif;
  --font-mono:    "Consolas", "Monaco", "Courier New", monospace;
  --line-height:  1.75;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--font-sans);
  font-size: 10.5pt;
  line-height: var(--line-height);
  color: var(--color-text);
  background: var(--color-bg);
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem 2.5rem;
}

/* ── 封面页 ── */
.cover-page {
  page-break-after: always;
  text-align: center;
  border: 3px solid var(--color-primary);
  padding: 5rem 3rem;
  margin-bottom: 3rem;
  background: linear-gradient(160deg, var(--color-primary-pale) 0%, #ffffff 60%);
}
.cover-title {
  font-family: var(--font-serif);
  font-size: 2.2rem;
  font-weight: 700;
  color: var(--color-primary);
  line-height: 1.3;
  margin-bottom: 1rem;
}
.cover-subtitle {
  font-size: 1.05rem;
  color: var(--color-text-muted);
  margin-bottom: 2rem;
}
.cover-badge {
  display: inline-block;
  background: var(--color-primary);
  color: white;
  padding: 0.25rem 0.8rem;
  border-radius: 2px;
  font-size: 0.8rem;
  margin: 0.25rem;
  font-family: var(--font-mono);
}
.cover-meta {
  font-size: 0.88rem;
  color: var(--color-text-muted);
  border-top: 1px solid var(--color-border);
  padding-top: 1.5rem;
  margin-top: 2rem;
}

/* ── 目录页 ── */
.toc-section {
  page-break-after: always;
  margin-bottom: 3rem;
}
.toc-section h1 {
  font-family: var(--font-serif);
  font-size: 1.6rem;
  color: var(--color-primary);
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: 0.5rem;
  margin-bottom: 1.5rem;
}
.toc-list { list-style: none; padding: 0; }
.toc-list li {
  padding: 0.45rem 0;
  border-bottom: 1px dotted var(--color-border);
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}
.toc-list a {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 600;
  font-size: 0.95rem;
}
.toc-num {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 0.82rem;
  min-width: 5rem;
}

/* ── 标题 ── */
h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-serif);
  color: var(--color-primary);
  line-height: 1.3;
  margin-top: 2rem;
  margin-bottom: 0.8rem;
}
h2 {
  font-size: 1.5rem;
  font-weight: 700;
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: 0.4rem;
  margin-top: 3rem;
  page-break-before: always;
}
h2:first-of-type { page-break-before: avoid; }
h3 {
  font-size: 1.12rem;
  font-weight: 600;
  border-left: 4px solid var(--color-primary-light);
  padding-left: 0.75rem;
  margin-top: 1.8rem;
  color: var(--color-primary-light);
}
h4 { font-size: 1rem; font-weight: 600; color: var(--color-text); margin-top: 1.4rem; }
h5, h6 { font-size: 0.95rem; font-weight: 600; color: var(--color-text-muted); }

/* ── 段落 ── */
p { margin-bottom: 0.9rem; text-align: justify; }

/* ── 链接 ── */
a { color: var(--color-primary-light); text-decoration: none; }
a:hover { color: var(--color-accent); }

/* ── 代码块（白色底） ── */
pre {
  background: #ffffff !important;
  border: 1px solid var(--color-border);
  border-left: 4px solid var(--color-primary-light);
  border-radius: 3px;
  padding: 1rem 1.2rem;
  overflow-x: auto;
  margin: 1rem 0 1.2rem;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  line-height: 1.55;
  page-break-inside: avoid;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
code {
  font-family: var(--font-mono);
  font-size: 0.85em;
  background: #f0f4f8;
  padding: 0.1em 0.35em;
  border-radius: 2px;
  color: var(--color-primary);
}
pre code {
  background: transparent !important;
  padding: 0;
  color: var(--color-text);
  font-size: inherit;
}
.highlight { background: #ffffff !important; }
.highlight .c, .highlight .cm, .highlight .c1, .highlight .cs { color: #6a737d; font-style: italic; }
.highlight .k, .highlight .kn, .highlight .kd, .highlight .kw { color: #0550ae; font-weight: bold; }
.highlight .nb { color: #0550ae; }
.highlight .nc { color: #116329; font-weight: bold; }
.highlight .nf { color: #8250df; }
.highlight .s, .highlight .s1, .highlight .s2, .highlight .sa { color: #0a3069; }
.highlight .mi, .highlight .mf, .highlight .mh { color: #0550ae; }
.highlight .o, .highlight .p { color: #24292f; }
.highlight .n, .highlight .na { color: #24292f; }
.highlight .nt { color: #116329; }
.highlight .cp { color: #6a737d; }
.highlight .err { color: #c0392b; }
.highlight .ge { font-style: italic; }
.highlight .gs { font-weight: bold; }

/* ── 表格（白色底） ── */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.2rem 0;
  font-size: 0.88rem;
  background: #ffffff !important;
  page-break-inside: avoid;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
thead {
  background: var(--color-primary) !important;
  color: white;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
thead th {
  padding: 0.6rem 0.9rem;
  text-align: left;
  font-weight: 600;
  font-size: 0.85rem;
  color: white !important;
  border: none;
}
tbody tr:nth-child(even) {
  background: var(--color-bg-alt) !important;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
tbody tr:nth-child(odd) { background: #ffffff !important; }
td, th {
  padding: 0.5rem 0.9rem;
  border-bottom: 1px solid var(--color-border);
  vertical-align: top;
}

/* ── 引用块 ── */
blockquote {
  border-left: 4px solid var(--color-primary-light);
  background: var(--color-primary-pale);
  padding: 0.8rem 1.2rem;
  margin: 1rem 0;
  border-radius: 0 3px 3px 0;
  font-style: italic;
  color: var(--color-text-muted);
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
blockquote p { margin-bottom: 0; }

/* ── 列表 ── */
ul, ol { padding-left: 1.8rem; margin-bottom: 0.9rem; }
li { margin-bottom: 0.3rem; }

/* ── 分割线 ── */
hr { border: none; border-top: 1px solid var(--color-border); margin: 2rem 0; }

/* ── 页脚 ── */
.doc-footer {
  margin-top: 4rem;
  padding-top: 1.5rem;
  border-top: 2px solid var(--color-primary);
  text-align: center;
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

/* ══ 打印样式 ══ */
@media print {
  body {
    padding: 0;
    margin: 0;
    max-width: 100%;
    font-size: 9.5pt;
    color: #000000;
    background: #ffffff;
  }
  .cover-page {
    page-break-after: always;
    padding: 3cm 2cm;
    border: 2pt solid #1a3a5c;
    background: #ffffff !important;
  }
  .toc-section { page-break-after: always; }
  h2 {
    page-break-before: always;
    page-break-after: avoid;
    font-size: 14pt;
    color: #1a3a5c;
    border-bottom: 1.5pt solid #1a3a5c;
  }
  h2:first-of-type { page-break-before: avoid; }
  h3 { page-break-after: avoid; font-size: 11pt; color: #2c5f8a; border-left: 3pt solid #2c5f8a; }
  h4 { page-break-after: avoid; font-size: 10pt; }
  pre {
    background: #ffffff !important;
    border: 0.5pt solid #c8d6e5 !important;
    border-left: 3pt solid #2c5f8a !important;
    font-size: 7.5pt;
    page-break-inside: avoid;
    box-shadow: none !important;
  }
  code { background: #f5f5f5 !important; color: #1a3a5c !important; }
  pre code { background: transparent !important; color: #000000 !important; }
  table {
    background: #ffffff !important;
    box-shadow: none !important;
    border: 0.5pt solid #c8d6e5 !important;
    font-size: 8.5pt;
    page-break-inside: avoid;
  }
  thead {
    background: #1a3a5c !important;
    color: #ffffff !important;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  thead th { color: #ffffff !important; }
  tbody tr:nth-child(even) {
    background: #f7f9fc !important;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  td, th { border: 0.5pt solid #c8d6e5 !important; padding: 0.3rem 0.6rem; }
  blockquote {
    background: #f7f9fc !important;
    border-left: 3pt solid #2c5f8a !important;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  a { color: #000000 !important; text-decoration: none !important; }
  p { orphans: 3; widows: 3; }
  @page {
    size: A4;
    margin: 2cm 2.2cm 2.5cm 2.2cm;
  }
}

/* ══ 屏幕阅读 ══ */
@media screen {
  body { background: #eef2f7; }
  .content-wrapper {
    background: #ffffff;
    padding: 3rem 4rem;
    border-radius: 4px;
    box-shadow: 0 2px 20px rgba(0,0,0,0.1);
    max-width: 900px;
    margin: 2rem auto;
  }
}
"""

# ── 目录 HTML ─────────────────────────────────────────────────────────────────
chapter_titles = [
    ("01", "渲染管线与状态管理"),
    ("02", "场景图与空间加速结构"),
    ("03", "变换系统与坐标空间"),
    ("04", "光照与阴影"),
    ("05", "透明度与混合"),
    ("06", "动画系统"),
    ("07", "物理与碰撞检测"),
    ("08", "纹理与内存管理"),
    ("09", "Shader 系统"),
    ("10", "多线程架构"),
    ("11", "后处理与离屏渲染"),
    ("12", "LOD 与流式加载"),
    ("13", "跨平台图形 API"),
    ("14", "精度与数值稳定性"),
]

toc_items_html = "\n".join([
    f'  <li><span class="toc-num">专题 {num}</span>'
    f'<a href="#">{title}</a></li>'
    for num, title in chapter_titles
])

# ── 完整 HTML ─────────────────────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Panda3D 引擎技术专题整合文档</title>
  <style>
{CSS}
  </style>
</head>
<body>
<div class="content-wrapper">

<!-- 封面页 -->
<div class="cover-page">
  <div class="cover-title">Panda3D 引擎技术专题<br>整合文档</div>
  <div class="cover-subtitle">Panda3D Engine Technical Topics — Integrated Reference</div>
  <div style="margin: 2rem 0; line-height: 2.2;">
    <span class="cover-badge">渲染管线</span>
    <span class="cover-badge">场景图</span>
    <span class="cover-badge">变换系统</span>
    <span class="cover-badge">光照阴影</span>
    <span class="cover-badge">透明混合</span>
    <span class="cover-badge">动画系统</span>
    <span class="cover-badge">物理碰撞</span>
    <span class="cover-badge">纹理内存</span>
    <span class="cover-badge">Shader</span>
    <span class="cover-badge">多线程</span>
    <span class="cover-badge">后处理</span>
    <span class="cover-badge">LOD流式</span>
    <span class="cover-badge">跨平台</span>
    <span class="cover-badge">精度稳定性</span>
  </div>
  <div class="cover-meta">
    <p>共 14 个专题 · 涵盖 Panda3D 引擎核心子系统</p>
    <p style="margin-top:0.5rem;">每个专题包含：问题背景 · 数学原理 · 工程实践 · 源码解析 · 代码演示 · 性能分析</p>
  </div>
</div>

<!-- 目录页 -->
<div class="toc-section">
  <h1>目录</h1>
  <ul class="toc-list">
{toc_items_html}
  </ul>
</div>

<!-- 正文 -->
{body_html}

<!-- 页脚 -->
<div class="doc-footer">
  <p>Panda3D 引擎技术专题整合文档 &nbsp;·&nbsp; 14 个专题 &nbsp;·&nbsp; 基于 Panda3D 源码分析</p>
</div>

</div>
</body>
</html>
"""

# ── 写入 HTML ─────────────────────────────────────────────────────────────────
with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"✅ HTML 已生成：{OUTPUT_HTML}")

# ── 转换 PDF ──────────────────────────────────────────────────────────────────
def try_weasyprint():
    try:
        from weasyprint import HTML as WP_HTML
        print("使用 WeasyPrint 转换 PDF...")
        WP_HTML(filename=OUTPUT_HTML).write_pdf(OUTPUT_PDF)
        print(f"✅ PDF 已生成：{OUTPUT_PDF}")
        return True
    except ImportError:
        print("WeasyPrint 未安装，尝试 Chromium...")
        return False
    except Exception as e:
        print(f"WeasyPrint 失败：{e}")
        return False

def try_chromium():
    candidates = [
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for chrome in candidates:
        try:
            result = subprocess.run(
                [
                    chrome,
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    f"--print-to-pdf={OUTPUT_PDF}",
                    "--print-to-pdf-no-header",
                    f"file://{os.path.abspath(OUTPUT_HTML)}",
                ],
                capture_output=True,
                timeout=120,
            )
            if result.returncode == 0:
                print(f"✅ PDF 已生成（Chromium）：{OUTPUT_PDF}")
                return True
            else:
                print(f"Chromium 返回码 {result.returncode}：{result.stderr.decode()[:200]}")
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            print(f"{chrome} 超时")
        except Exception as e:
            print(f"{chrome} 失败：{e}")
    return False

if not try_weasyprint():
    if not try_chromium():
        print("\n⚠️  无法自动生成 PDF。")
        print("请手动在浏览器中打开以下文件，然后使用 Ctrl+P 打印为 PDF：")
        print(f"  {OUTPUT_HTML}")
        print("\n或安装 WeasyPrint：")
        print("  pip install weasyprint")
