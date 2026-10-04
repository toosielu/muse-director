#!/usr/bin/env python3
"""Check required files, guide structure, genre length, test set and local links."""
import json
from pathlib import Path
import re
import sys

REQUIRED = [
    "README.md", "SKILL.md", "muse-idea-to-short.md", "agents/openai.yaml",
    "genres/healing-ip.md", "drafts/beauty-oncamera.md", "drafts/guofeng-live.md",
    "examples/one-line.md", "examples/detailed-prompt.md", "examples/dialogue-scene.md",
    "examples/case-2026-10-03-healing-45s.md", "examples/case-2026-10-04-capability-test.md",
    "testing/test-set.md", "testing/scorecard.md", "testing/results.csv",
    "testing/edit-and-budget.md", "testing/dialogue-audio.md", "testing/multi-reference.md",
    "tools/u0_check.py",
]
GENRE_CAP = 1500
GUIDE_SECTIONS = ["0", "1", "2", "3", "4", "5", "6", "7", "8"]
GUIDE_PHRASES = ("拼接", "一致", "说话", "剧本", "分镜表", "资产", "锁定", "锚点", "首帧图", "原生对白", "拼音",
                 "自主成片", "画幅", "过渡", "一次只改一处", "上一版提示词")
# Words from the old audit-style guide that pushed Muse into bookkeeping instead of directing.
AUDIT_JARGON = ("UNVERIFIED", "U0", "3+2", "扣费", "台账", "R9", "主控", "分母")
TEST_IDS = [f"T{i}" for i in range(1, 9)]


def check(root):
    root = Path(root)
    errors = ["missing: " + name for name in REQUIRED if not (root / name).is_file()]
    lengths = {}

    def read(name):
        path = root / name
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    for name in REQUIRED:
        if name == "muse-idea-to-short.md" or name.startswith("genres/"):
            text = read(name)
            lengths[name] = len(text)
            if name.startswith("genres/") and len(text) > GENRE_CAP:
                errors.append(f"{name}: {len(text)} > {GENRE_CAP} characters")

    guide = read("muse-idea-to-short.md")
    if re.findall(r"^## (\d+)\.", guide, re.M) != GUIDE_SECTIONS:
        errors.append("guide must have numbered sections 0–8")
    for phrase in GUIDE_PHRASES:
        if phrase not in guide:
            errors.append("guide missing: " + phrase)
    for name in ["muse-idea-to-short.md"] + [n for n in REQUIRED if n.startswith("genres/")]:
        for word in AUDIT_JARGON:
            if word in read(name):
                errors.append(f"audit jargon in {name}: {word}")

    tests = read("testing/test-set.md")
    found = re.findall(r"^### (T\d+) ", tests, re.M)
    if found != TEST_IDS:
        errors.append("test set must list T1–T8 in order, found " + ",".join(found))
    if tests.count("```") != 2 * len(TEST_IDS):
        errors.append("each test needs exactly one fenced input block")
    header = read("testing/results.csv").splitlines()[:1]
    if not header or not {"test_id", "group", "looks", "consistency", "cuts", "speech"}.issubset(header[0].split(",")):
        errors.append("results.csv header missing score columns")

    skill = read("SKILL.md")
    if not re.search(r"^name: muse-idea-to-short$", skill, re.M):
        errors.append("skill name differs")
    if "muse-idea-to-short.md" not in skill:
        errors.append("SKILL route missing main guide")
    readme = read("README.md")
    for phrase in ("什么时候用", "什么时候别用", "怎么发", "拿到片子先看", "testing/test-set.md"):
        if phrase not in readme:
            errors.append("README missing: " + phrase)

    links = 0
    for path in sorted(root.rglob("*.md")):
        if ".git" in path.relative_to(root).parts:
            continue
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
                errors.append("broken link: " + path.relative_to(root).as_posix() + " -> " + target)
            links += 1
    return {"status": "FAIL" if errors else "PASS", "lengths": lengths, "relative_links": links, "errors": errors}


if __name__ == "__main__":
    report = check(Path(__file__).resolve().parent.parent)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(1 if report["errors"] else 0)
