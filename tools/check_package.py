#!/usr/bin/env python3
"""Check the single canonical guide, routing, lengths, names and local links."""
import json
from pathlib import Path
import re
import sys


def check(root):
    root = Path(root)
    required = ["README.md", "SKILL.md", "muse-idea-to-short.md", "agents/openai.yaml",
                "genres/healing-ip.md", "genres/beauty-oncamera.md", "genres/guofeng-live.md",
                "examples/one-line-to-30s.md", "examples/prompt-merge.md", "tools/u0_check.py",
                "tools/lint_shot.py", "tools/test-log.csv", "tools/refactor-review.md"]
    errors = ["missing: " + name for name in required if not (root/name).is_file()]
    lengths = {}
    for name, cap in [("muse-idea-to-short.md",3000)] + [(p,1500) for p in required if p.startswith("genres/")]:
        if (root/name).is_file():
            text = (root/name).read_text(encoding="utf-8")
            lengths[name] = len(text)
            if len(text) > cap:
                errors.append(f"{name}: {len(text)} > {cap} Unicode characters including Markdown/whitespace")
    main = (root/"muse-idea-to-short.md").read_text(encoding="utf-8") if (root/"muse-idea-to-short.md").is_file() else ""
    headings = re.findall(r"^## (\d+)\.", main,re.M)
    if headings != [str(i) for i in range(1,11)]:
        errors.append("canonical guide must have numbered sections 1–10")
    for phrase in ("**A", "**B", "待测", "可复制", "3+2", "一镜一确认", "自主成片", "UNVERIFIED"):
        if phrase not in main:
            errors.append("guide missing: " + phrase)
    for directory in ("references", "assets", "scripts"):
        if (root/directory).exists():
            errors.append("old parallel/generated rules remain: " + directory)
    links = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.relative_to(root).parts or path.suffix not in (".md", ".yaml", ".py", ".csv"):
            continue
        text = path.read_text(encoding="utf-8-sig")
        if "muse-" + "director" in text:
            errors.append("old invocation/name remains in: " + path.relative_to(root).as_posix())
        if path.suffix != ".md":
            continue
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if "://" in target or target.startswith("#"):
                continue
            resolved = (path.parent/target.split("#",1)[0]).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
                errors.append("broken/escaping link: " + str(path.relative_to(root)) + " -> " + target)
            links += 1
    skill = (root/"SKILL.md").read_text(encoding="utf-8") if (root/"SKILL.md").is_file() else ""
    if not re.search(r"^name: muse-idea-to-short$",skill,re.M):
        errors.append("skill name differs")
    if "muse-idea-to-short.md" not in skill:
        errors.append("SKILL route missing canonical file")
    readme = (root/"README.md").read_text(encoding="utf-8") if (root/"README.md").is_file() else ""
    first_screen = readme.split("## 按需补充",1)[0]
    for phrase in ("什么时候用","什么时候别用","怎么发","拿到片子先看"):
        if phrase not in first_screen:
            errors.append("README first screen missing: " + phrase)
    review = (root/"tools/refactor-review.md").read_text(encoding="utf-8") if (root/"tools/refactor-review.md").is_file() else ""
    for i in range(1,9):
        if not re.search(r"\|C"+str(i)+r"[^\n]*\|[^\n]+\|[^\n]+\|",review):
            errors.append("C"+str(i)+" resolution/reason missing")
    return {"status":"FAIL" if errors else "PASS","lengths":lengths,"relative_links":links,"errors":errors,"muse_validation":"not run / 待测"}


if __name__ == "__main__":
    report = check(Path(__file__).resolve().parent.parent)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    sys.exit(1 if report["errors"] else 0)
