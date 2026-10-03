#!/usr/bin/env python3
"""Check a shot's text and local references; never call Muse or assess video."""
import argparse
import json
from pathlib import Path
import re
import sys

INPUT_HEADING = "### 模型输入（原样转交）"


def lint(shot_path, card_paths, max_clip_seconds=None):
    shot_path = Path(shot_path)
    text = shot_path.read_text(encoding="utf-8-sig")
    if text.count(INPUT_HEADING) != 1 or text.count("### 制作任务") != 1:
        raise ValueError("Exactly one task and one model-input section are required")
    task_text, body = text.split(INPUT_HEADING)
    task_text = task_text.split("### 制作任务", 1)[1]
    blocks = re.findall(r"```json\s*\n(.*?)\n```", task_text, re.S)
    if len(blocks) != 1:
        raise ValueError("Task requires one JSON metadata block")
    meta = json.loads(blocks[0])
    if not isinstance(meta, dict):
        raise ValueError("Task metadata must be an object")
    body = re.split(r"\n### ", body, maxsplit=1)[0].strip()
    cards = [json.loads(Path(path).read_text(encoding="utf-8-sig")) for path in card_paths]
    if not cards or any(not isinstance(card, dict) for card in cards):
        raise ValueError("Provide character-card JSON objects")
    findings = []

    def add(code, state, detail):
        findings.append({"code": code, "status": state, "detail": detail})

    selected = meta.get("cards")
    if not isinstance(selected, list) or any(not isinstance(item, dict) for item in selected):
        raise ValueError("cards metadata must be a list of objects")
    selected_ids = [(item.get("card_id"), item.get("version")) for item in selected]
    actual_ids = [(card.get("card_id"), card.get("version")) for card in cards]
    if selected_ids != actual_ids or any(not all(pair) for pair in actual_ids) or len(set(actual_ids)) != len(actual_ids):
        add("card_version", "FAIL", "Card identity/version/order differs or is duplicated")
    styles = set()
    for card in cards:
        locked = card.get("locked_text")
        style = card.get("style_prefix")
        if not isinstance(locked, str) or not locked.strip() or "待填写" in locked or locked not in body:
            add("locked_text", "FAIL", f"Missing actual frozen text for {card.get('card_id')}")
        if not isinstance(style, str) or not style.strip() or "待填写" in style:
            add("style", "FAIL", "Style is not adopted")
        else:
            styles.add(style)
        if not card.get("adoption_evidence"):
            add("adoption", "FAIL", "Record actual user specification or delegated director adoption")
    style_lines = re.findall(r"^风格：[ \t]*(.*)$", body, re.M)
    if len(styles) != 1 or len(style_lines) != 1 or style_lines[0].strip() not in styles:
        add("style", "FAIL", "One shared style line must exactly match the selected cards")
    count = meta.get("subject_count")
    counts = re.findall(r"^主体数：[ \t]*(\d+)[。.]?[ \t]*$", body, re.M)
    if type(count) is not int or count < len(cards) or counts != [str(count)]:
        add("subject_count", "FAIL", "Subject count is inconsistent with text or selected cards")
    refs = meta.get("references")
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, dict) for ref in refs):
        raise ValueError("references must be a non-empty list of objects")
    orders = [ref.get("order") for ref in refs]
    if any(type(order) is not int for order in orders) or orders != list(range(1, len(refs) + 1)):
        add("reference_order", "FAIL", "References must be numbered consecutively from 1")
    images = [int(value) for value in re.findall(r"\[图(\d+)：[^\]\n]+\]", body)]
    if images != list(range(1, len(refs) + 1)):
        add("reference_labels", "FAIL", "Model-input labels must match reference count/order")
    sources = [ref.get("source") for ref in refs]
    for ref in refs:
        source = ref.get("source")
        if not isinstance(source, str) or not source.strip() or source.startswith("待"):
            add("reference_missing", "FAIL", "Unprepared reference")
        elif source.startswith(("https://", "media_handle:")):
            add("reference_access", "WARN", "Remote reference/handle must be checked in the actual platform")
        elif not (shot_path.parent / source).is_file():
            add("reference_missing", "FAIL", f"Local reference file does not exist: {source}")
    for card in cards:
        required = card.get("reference_images", [])
        if not isinstance(required, list) or any(not isinstance(ref, dict) for ref in required):
            raise ValueError("Card reference_images must be a list of objects")
        card_sources = [ref.get("source") for ref in required if ref.get("required") is True]
        positions = [sources.index(source) if source in sources else -1 for source in card_sources]
        if not card_sources or -1 in positions or positions != sorted(set(positions)):
            add("card_references", "FAIL", "Required card references are missing or reordered")
    budget = meta.get("prompt_budget_seconds")
    window = meta.get("usable_window")
    if type(budget) not in (int, float) or not 0 < budget < float("inf"):
        add("planning_capacity", "FAIL", "Positive finite planning capacity required")
    else:
        if max_clip_seconds is not None and (not 0 < max_clip_seconds < float("inf") or budget > max_clip_seconds):
            add("planning_capacity", "FAIL", "Planning capacity exceeds the supplied project limit")
        if not isinstance(window, list) or len(window) != 2 or any(type(value) not in (int, float) for value in window) or not 0 <= window[0] < window[1] <= budget:
            add("usable_window", "FAIL", "Target window must fit the planning capacity")
    for field in ("场景", "起点", "动作", "终点", "镜头", "声音"):
        if not re.search(r"^" + field + r"：[ \t]*\S", body, re.M):
            add("input_field", "FAIL", f"Missing {field} field")
    if not meta.get("required_event") or str(meta["required_event"]).startswith("待"):
        add("required_event", "FAIL", "Actual necessary event must be recorded")
    add("manual_review", "WARN", "Check real uploads, visual/text consistency, causal action, continuity and actual permissions separately")
    return {"status": "needs_fix" if any(item["status"] == "FAIL" for item in findings) else "text_checked",
            "findings": findings, "model_input": body,
            "semantic_review": "unverified", "platform_binding": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shot", type=Path, required=True)
    parser.add_argument("--card", type=Path, action="append", required=True)
    parser.add_argument("--max-clip-seconds", type=float)
    args = parser.parse_args()
    try:
        report = lint(args.shot, args.card, args.max_clip_seconds)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "invalid_input", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "needs_fix" else 0


if __name__ == "__main__":
    sys.exit(main())
