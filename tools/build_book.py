#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a self-contained orange-book HTML + PDF from the analysis chapters."""
import os, re, shutil, subprocess
from pathlib import Path

ROOT = Path(r"E:/GitHub/deepseek-harness-source-analysis")
BUILD = ROOT / "build"
COMBINED = ROOT / "combined"
PANDOC = r"C:/Users/li-qzh/.workbuddy/binaries/pandoc-bin/pandoc-3.6.4/pandoc.exe"
CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"

# Flat chapter order — mirrors the original combined HTML exactly (parts 1-19),
# then the new resources chapter continues as part 20.
# No group headers, no heading demotion: each file is its own top-level H1 so
# pandoc --number-sections reproduces the original 1..19 numbering.
CHAPTERS = [
    "01-overview/project-overview.md",
    "02-architecture/system-architecture.md",
    "03-layers/01-application-and-boot.md",
    "03-layers/02-host-client.md",
    "03-layers/03-core-api.md",
    "03-layers/04-capability-seams.md",
    "03-layers/05-persistence.md",
    "03-layers/06-protocol-integration.md",
    "04-core-modules/core-agent-loop/README.md",
    "04-core-modules/core-session/README.md",
    "04-core-modules/core-tools/README.md",
    "04-core-modules/core-tools/tool-execution-pipeline/00-overview.md",
    "05-data-architecture/README.md",
    "05-data-architecture/data-architecture.md",
    "06-ThirdParty/README.md",
    "06-ThirdParty/01-llm-integration.md",
    "06-ThirdParty/02-sandbox-execution.md",
    "06-ThirdParty/03-protocols.md",
    "06-ThirdParty/04-framework-vendor.md",
    "07-resources/related-resources.md",
]

IMG_RE = re.compile(r"(!\[[^\]]*\]\()(images/[^)]+)(\))")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)$")

def demote(text):
    out, in_fence = [], False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(line); continue
        if not in_fence:
            m = HEAD_RE.match(line)
            if m:
                level = m.group(1)
                if len(level) < 6:
                    line = "#" + line
        out.append(line)
    return "\n".join(out)

def rewrite_images(text, rel_md, assets):
    chap_dir = (ROOT / rel_md).parent
    key = str(chap_dir.relative_to(ROOT)).replace("/", "__")
    def repl(m):
        name = Path(m.group(2)).name
        src = chap_dir / "images" / name
        if not src.exists():
            print("  IMG MISSING", src); return m.group(0)
        destdir = assets / key
        destdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, destdir / name)
        return f"{m.group(1)}assets/{key}/{name}{m.group(3)}"
    return IMG_RE.sub(repl, text)

# Strip pre-existing manual numbering prefixes from every heading's text.
# The original combined build did this globally (so pandoc's --number-sections
# doesn't double up: "1. 项目基本信息" -> "项目基本信息", "05 - 数据架构" ->
# "数据架构", "3.1 核心 API" -> "核心 API"). Keeps heading text consistent with
# the original. Code fences are skipped.
MANUAL_NUM = re.compile(r"^(#{1,6}\s*)\d{1,3}(?:\.\d{1,3})*\s*[-–—.、]?\s+")
def strip_manual_numbers(text):
    out, in_fence = [], False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(line); continue
        if not in_fence and stripped.startswith("#"):
            line = MANUAL_NUM.sub(r"\1", line)
        out.append(line)
    return "\n".join(out)

def build():
    if BUILD.exists(): shutil.rmtree(BUILD)
    BUILD.mkdir(); (BUILD / "assets").mkdir()
    combined = []
    for rel in CHAPTERS:
        p = ROOT / rel
        text = p.read_text(encoding="utf-8")
        text = strip_manual_numbers(text)
        text = rewrite_images(text, rel, BUILD / "assets")
        combined.append(text.rstrip() + "\n\n---\n\n")
    (BUILD / "combined.md").write_text("\n".join(combined), encoding="utf-8")
    # copy css
    shutil.copy2(ROOT / "tools" / "orange.css", BUILD / "orange.css")
    # pandoc
    out_html = BUILD / "combined.html"
    cmd = [PANDOC, "combined.md", "-s", "--toc", "--number-sections",
           "--embed-resources", "--css", "orange.css",
           "--metadata", "title=DeepSeek Harness 源码深度解析",
           "--metadata", "lang=zh", "-o", str(out_html)]
    r = subprocess.run(cmd, cwd=str(BUILD), capture_output=True, text=True)
    print("PANDOC rc", r.returncode)
    if r.returncode != 0:
        print(r.stderr); return
    size = out_html.stat().st_size
    print("HTML bytes", size)
    # copy html to combined/
    COMBINED.mkdir(exist_ok=True)
    html_dest = COMBINED / "deepseek-harness-source-analysis.html"
    shutil.copy2(out_html, html_dest)
    # chrome pdf
    pdf_dest = COMBINED / "deepseek-harness-source-analysis.pdf"
    url = out_html.as_uri()
    ccmd = [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
            "--no-pdf-header-footer", f"--print-to-pdf={pdf_dest}", url]
    cr = subprocess.run(ccmd, capture_output=True, text=True, timeout=300)
    print("CHROME rc", cr.returncode)
    if pdf_dest.exists():
        print("PDF bytes", pdf_dest.stat().st_size)
    else:
        print("PDF NOT created", cr.stderr[-500:])

if __name__ == "__main__":
    build()
