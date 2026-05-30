#!/usr/bin/env python3
"""
generate_pdf.py — 将 TECHNICAL_REPORT.md + SVG 图表生成科研配色 PDF
依赖: pandoc (系统), cairosvg (pip), reportlab (pip)

用法:
    cd my_game
    python3 generate_pdf.py
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

HERE = Path(__file__).parent
REPORT_MD = HERE / "TECHNICAL_REPORT.md"
FIGURES_DIR = HERE / "figures"
OUTPUT_PDF = HERE / "engine_coverage_academic.pdf"
LATEX_TEMPLATE = HERE / "_report_template.tex"

# ─────────────────────────────────────────────
# 1. 将 SVG 转换为 PNG（pandoc LaTeX 不支持 SVG）
# ─────────────────────────────────────────────
def convert_svgs_to_png():
    """将 figures/ 下所有 SVG 转为 PNG（300dpi）"""
    try:
        import cairosvg
        has_cairo = True
    except ImportError:
        has_cairo = False

    png_dir = FIGURES_DIR / "png"
    png_dir.mkdir(exist_ok=True)

    for svg_file in sorted(FIGURES_DIR.glob("*.svg")):
        png_file = png_dir / (svg_file.stem + ".png")
        if has_cairo:
            import cairosvg
            cairosvg.svg2png(
                url=str(svg_file),
                write_to=str(png_file),
                dpi=150,
                scale=1.5,
            )
            print(f"  [cairosvg] {svg_file.name} → {png_file.name}")
        else:
            # 尝试 rsvg-convert
            result = subprocess.run(
                ["rsvg-convert", "-d", "150", "-p", "150", "-f", "png",
                 "-o", str(png_file), str(svg_file)],
                capture_output=True
            )
            if result.returncode == 0:
                print(f"  [rsvg] {svg_file.name} → {png_file.name}")
            else:
                # 尝试 inkscape
                result2 = subprocess.run(
                    ["inkscape", "--export-type=png", "--export-dpi=150",
                     f"--export-filename={png_file}", str(svg_file)],
                    capture_output=True
                )
                if result2.returncode == 0:
                    print(f"  [inkscape] {svg_file.name} → {png_file.name}")
                else:
                    print(f"  [WARN] 无法转换 {svg_file.name}，跳过")
    return png_dir


# ─────────────────────────────────────────────
# 2. 生成修改后的 Markdown（SVG 引用 → PNG 引用）
# ─────────────────────────────────────────────
def patch_markdown_for_latex(png_dir: Path) -> Path:
    """将 MD 中的 SVG 路径替换为 PNG 路径"""
    content = REPORT_MD.read_text(encoding="utf-8")
    # 替换图片路径
    content = content.replace("figures/fig1_architecture.svg",
                               f"figures/png/fig1_architecture.png")
    content = content.replace("figures/fig2_render_pipeline.svg",
                               f"figures/png/fig2_render_pipeline.png")
    content = content.replace("figures/fig3_scene_graph.svg",
                               f"figures/png/fig3_scene_graph.png")
    content = content.replace("figures/fig4_animation.svg",
                               f"figures/png/fig4_animation.png")
    content = content.replace("figures/fig5_collision_physics.svg",
                               f"figures/png/fig5_collision_physics.png")

    patched = HERE / "_report_patched.md"
    patched.write_text(content, encoding="utf-8")
    return patched


# ─────────────────────────────────────────────
# 3. 生成 LaTeX 模板（科研配色）
# ─────────────────────────────────────────────
LATEX_TEMPLATE_CONTENT = r"""
\documentclass[11pt,a4paper]{article}

% ── 字体与编码 ──
\usepackage{fontspec}
\usepackage{xeCJK}
\setCJKmainfont{PingFang SC}
\setmainfont{Helvetica Neue}
\setmonofont{Menlo}

% ── 页面布局 ──
\usepackage[a4paper, margin=2.2cm, top=2.5cm, bottom=2.5cm]{geometry}
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\color{headcolor}Panda3D 引擎代码结构技术报告}
\fancyhead[R]{\small\color{headcolor}\thepage}
\fancyfoot[C]{\small\color{headcolor}Carnegie Mellon University · Panda3D master branch}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0.2pt}

% ── 颜色（科研配色：深蓝主色调）──
\usepackage{xcolor}
\definecolor{primary}{HTML}{1565C0}
\definecolor{secondary}{HTML}{0277BD}
\definecolor{accent}{HTML}{00838F}
\definecolor{headcolor}{HTML}{37474F}
\definecolor{codebg}{HTML}{F5F7FA}
\definecolor{codefg}{HTML}{263238}
\definecolor{linkcolor}{HTML}{1565C0}
\definecolor{tableheadbg}{HTML}{1565C0}
\definecolor{tablerowbg}{HTML}{E3F2FD}
\definecolor{blockquotebg}{HTML}{E8F5E9}
\definecolor{blockquotebar}{HTML}{2E7D32}

% ── 超链接 ──
\usepackage[colorlinks=true, linkcolor=linkcolor, urlcolor=accent, citecolor=secondary]{hyperref}

% ── 图片 ──
\usepackage{graphicx}
\usepackage{float}
\usepackage[font=small,labelfont=bf,labelsep=period,textfont=it]{caption}

% ── 代码块 ──
\usepackage{listings}
\lstset{
  backgroundcolor=\color{codebg},
  basicstyle=\ttfamily\footnotesize\color{codefg},
  breaklines=true,
  frame=single,
  framerule=0.4pt,
  rulecolor=\color{secondary!40},
  xleftmargin=8pt,
  xrightmargin=8pt,
  aboveskip=8pt,
  belowskip=8pt,
  showstringspaces=false,
}

% ── 表格 ──
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{colortbl}
\usepackage{tabularx}

% ── 标题样式 ──
\usepackage{titlesec}
\titleformat{\section}{\Large\bfseries\color{primary}}{}{0em}{}[\color{primary}\titlerule]
\titleformat{\subsection}{\large\bfseries\color{secondary}}{}{0em}{}
\titleformat{\subsubsection}{\normalsize\bfseries\color{accent}}{}{0em}{}
\titlespacing{\section}{0pt}{18pt}{8pt}
\titlespacing{\subsection}{0pt}{12pt}{4pt}

% ── 引用块 ──
\usepackage{mdframed}
\newmdenv[
  backgroundcolor=blockquotebg,
  linecolor=blockquotebar,
  linewidth=3pt,
  topline=false,
  bottomline=false,
  rightline=false,
  innerleftmargin=10pt,
  innerrightmargin=10pt,
  innertopmargin=6pt,
  innerbottommargin=6pt,
]{blockquote}

% ── 其他 ──
\usepackage{microtype}
\usepackage{parskip}
\setlength{\parskip}{6pt}
\usepackage{enumitem}
\setlist{noitemsep, topsep=4pt}

% ── 封面 ──
\title{
  \vspace{-1cm}
  {\color{primary}\rule{\linewidth}{2pt}}\\[0.4cm]
  {\Huge\bfseries\color{primary} Panda3D 引擎代码结构技术报告}\\[0.3cm]
  {\large\color{secondary} Code Architecture Technical Report}\\[0.2cm]
  {\color{primary}\rule{\linewidth}{0.8pt}}
}
\author{
  \large Zoo（AI 代码分析）\\
  \normalsize\color{headcolor} Carnegie Mellon University · Panda3D master branch
}
\date{\normalsize 2026-05-30}

$if(highlighting-macros)$
$highlighting-macros$
$endif$

\begin{document}

\maketitle
\thispagestyle{empty}

\vspace{0.5cm}
\begin{mdframed}[backgroundcolor=tablerowbg, linecolor=primary, linewidth=1pt]
\small
\textbf{摘要：}本报告对 Panda3D 游戏引擎 master 分支进行系统性代码结构分析，
覆盖 dtool（基础工具层）、panda/src（C++ 引擎核心）、direct（Python 框架层）、
pandatool（资产工具链）共四大模块，约 20 万行代码。
报告重点分析场景图、渲染管线、动画系统、碰撞检测、Bullet 物理集成等核心算法，
并通过 5 张架构图直观展示模块间的分层关系与函数调用链。
\end{mdframed}

\vspace{0.3cm}
\tableofcontents
\newpage

$body$

\end{document}
"""


# ─────────────────────────────────────────────
# 4. 调用 pandoc 生成 PDF
# ─────────────────────────────────────────────
def run_pandoc(patched_md: Path):
    """使用 pandoc + xelatex 生成 PDF"""
    LATEX_TEMPLATE.write_text(LATEX_TEMPLATE_CONTENT, encoding="utf-8")

    cmd = [
        "pandoc",
        str(patched_md),
        "--pdf-engine=xelatex",
        f"--template={LATEX_TEMPLATE}",
        "--highlight-style=tango",
        "--toc",
        "--toc-depth=3",
        "--number-sections",
        "-V", "geometry:margin=2.2cm",
        "--resource-path", str(HERE),
        "-o", str(OUTPUT_PDF),
    ]

    print(f"\n[pandoc] 生成 PDF: {OUTPUT_PDF}")
    print("  命令:", " ".join(cmd[:6]), "...")
    result = subprocess.run(cmd, cwd=str(HERE), capture_output=True, text=True)

    if result.returncode == 0:
        size_mb = OUTPUT_PDF.stat().st_size / 1024 / 1024
        print(f"  ✓ 成功！文件大小: {size_mb:.2f} MB")
    else:
        print(f"  ✗ 失败！stderr:\n{result.stderr[-2000:]}")
        # 尝试不用自定义模板
        print("\n[pandoc] 尝试简化模式（无自定义模板）...")
        cmd2 = [
            "pandoc",
            str(patched_md),
            "--pdf-engine=xelatex",
            "-V", "CJKmainfont=PingFang SC",
            "-V", "mainfont=Helvetica Neue",
            "-V", "monofont=Menlo",
            "-V", "geometry:margin=2cm",
            "-V", "colorlinks=true",
            "-V", "linkcolor=blue",
            "--highlight-style=tango",
            "--toc",
            "--number-sections",
            "--resource-path", str(HERE),
            "-o", str(OUTPUT_PDF),
        ]
        result2 = subprocess.run(cmd2, cwd=str(HERE), capture_output=True, text=True)
        if result2.returncode == 0:
            size_mb = OUTPUT_PDF.stat().st_size / 1024 / 1024
            print(f"  ✓ 简化模式成功！文件大小: {size_mb:.2f} MB")
        else:
            print(f"  ✗ 简化模式也失败:\n{result2.stderr[-1000:]}")
            sys.exit(1)


# ─────────────────────────────────────────────
# 5. 清理临时文件
# ─────────────────────────────────────────────
def cleanup():
    for f in [HERE / "_report_patched.md", LATEX_TEMPLATE]:
        if f.exists():
            f.unlink()


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Panda3D 技术报告 PDF 生成器")
    print("=" * 60)

    print("\n[1/4] 转换 SVG → PNG ...")
    png_dir = convert_svgs_to_png()

    print("\n[2/4] 修补 Markdown 图片路径 ...")
    patched = patch_markdown_for_latex(png_dir)

    print("\n[3/4] 调用 pandoc 生成 PDF ...")
    run_pandoc(patched)

    print("\n[4/4] 清理临时文件 ...")
    cleanup()

    print(f"\n✓ 完成！输出文件: {OUTPUT_PDF}")
