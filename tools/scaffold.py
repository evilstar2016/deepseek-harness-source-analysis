#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scaffold the standalone orange-book repo: copy analysis chapters + images
locally and rewrite absolute image refs to relative paths."""
import os, re, shutil
from pathlib import Path

SRC = Path(r"E:/GitHub/awesome-ai-projects-analysis/deepseek-harness-analysis")
DST = Path(r"E:/GitHub/deepseek-harness-source-analysis")

# chapter groups to copy (exclude combined/, html/, pdf/)
CHAPTER_DIRS = [
    "01-overview",
    "02-architecture",
    "03-layers",
    "04-core-modules",
    "05-data-architecture",
    "06-ThirdParty",
]

IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

def copy_chapters():
    copied_md, copied_img, copied_puml = 0, 0, 0
    for ch in CHAPTER_DIRS:
        src_ch = SRC / ch
        if not src_ch.exists():
            print("MISSING", src_ch)
            continue
        for path in sorted(src_ch.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(SRC)
            dest = DST / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".md":
                text = path.read_text(encoding="utf-8")
                # rewrite image refs
                def repl(m):
                    nonlocal copied_img
                    img_src = m.group(1).strip()
                    # only handle local file refs (absolute or relative, not http)
                    if img_src.startswith("http"):
                        return m.group(0)
                    p = Path(img_src)
                    if not p.is_absolute():
                        p = (path.parent / img_src).resolve()
                    if not p.exists():
                        print("  IMG MISSING:", img_src, "in", path)
                        return m.group(0)
                    imgdest = dest.parent / "images" / p.name
                    imgdest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, imgdest)
                    copied_img += 1
                    return f"![{m.group(0).split('![',1)[1].split(']',1)[0]}](images/{p.name})"
                text = IMG_RE.sub(repl, text)
                dest.write_text(text, encoding="utf-8")
                copied_md += 1
            elif path.suffix in (".puml",):
                shutil.copy2(path, dest)
                copied_puml += 1
            # other files ignored
    print(f"copied md={copied_md} img={copied_img} puml={copied_puml}")

if __name__ == "__main__":
    copy_chapters()
