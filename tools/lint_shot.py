#!/usr/bin/env python3
"""Check a shot's text and local references; never call Muse or assess video."""
import argparse
import json
from pathlib import Path
import re
import sys

INPUT_HEADING = "### 模型输入（原样转交）"


BEAT_SPLIT = re.compile(r"然后|接着|随后|，再|并且|；|;")
HOLD_LINE = re.compile(r"保持|静止|不动")
END_POSE = re.compile(r"停在|停下|松手|回到|退回")
TIMED_LINE = re.compile(r"^(\d+(?:\.\d+)?)\s*[-–—~～]\s*(\d+(?:\.\d+)?)\s*秒[：:]\s*(\S.*?)$", re.M)


def action_beats(text):
    return len([part for part in BEAT_SPLIT.split(text) if part.strip()])


def shot_beat_count(body):
    """Count story beats. Start pose, end pose and hold are not extra beats."""
    segments = TIMED_LINE.findall(body)
    if segments:
        total = 0
        for index, (_, _, action) in enumerate(segments):
            beats = action_beats(action)
            scaffolding = beats <= 1 and (
                (index == 0 and len(segments) > 1)
                or HOLD_LINE.search(action)
                or END_POSE.search(action)
            )
            if not scaffolding:
                total += beats
        return total
    return sum(action_beats(item) for item in re.findall(r"^动作：[ \t]*(.*)$", body, re.M))


def positive_occurrence(text, pattern):
    """Conservative text heuristic; not a semantic prohibition classifier."""
    for clause in re.split(r"[，,。.;；\n]", text):
        for match in re.finditer(pattern, clause, re.I):
            prefix = clause[:match.start()]
            if not re.search(r"(?:无|没有|不要|禁止|不含|不使用|不加|no\s+|without\s+)[^、：:]{0,12}$", prefix, re.I):
                return True
    return False


def lint(shot_path, card_paths, max_clip_seconds=None):
    shot_path = Path(shot_path)
    text = shot_path.read_text(encoding="utf-8-sig")
    inputs = list(re.finditer(r"^(#{2,6})[ \t]+模型输入（原样转交）[ \t]*$", text, re.M))
    tasks = list(re.finditer(r"^(#{2,6})[ \t]+制作任务[ \t]*$", text, re.M))
    if len(inputs) != 1 or len(tasks) != 1 or inputs[0].start() <= tasks[0].start() or inputs[0].group(1) != tasks[0].group(1):
        raise ValueError("Exactly one task and one model-input section are required")
    task_text = text[tasks[0].end():inputs[0].start()]
    body = text[inputs[0].end():]
    blocks = re.findall(r"```json\s*\n(.*?)\n```", task_text, re.S)
    if len(blocks) != 1:
        raise ValueError("Task requires one JSON metadata block")
    meta = json.loads(blocks[0])
    if not isinstance(meta, dict):
        raise ValueError("Task metadata must be an object")
    level = len(inputs[0].group(1))
    body = re.split(r"^#{1," + str(level) + r"}[ \t]+", body, maxsplit=1, flags=re.M)[0].strip()
    cards = [json.loads(Path(path).read_text(encoding="utf-8-sig")) for path in card_paths]
    if any(not isinstance(card, dict) for card in cards):
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
        constraint = card.get("constraint_block", "")
        if not isinstance(constraint, str):
            raise ValueError("Card constraint_block must be a string")
        if constraint and constraint not in body:
            add("constraint_block", "FAIL", "Selected card constraint block differs")
    if not cards and isinstance(meta.get("style_prefix"), str) and meta["style_prefix"].strip():
        styles.add(meta["style_prefix"])
    style_lines = re.findall(r"^风格：[ \t]*(.*)$", body, re.M)
    if len(styles) != 1 or len(style_lines) != 1 or style_lines[0].strip() not in styles:
        add("style", "FAIL", "One shared style line must exactly match the selected cards")
    count = meta.get("subject_count")
    counts = re.findall(r"^主体数：[ \t]*(\d+)[。.]?[ \t]*$", body, re.M)
    constraint_counts = re.findall(r"画面中恰好\s*(\d+)\s*个角色", "\n".join(re.findall(r"^约束：[ \t]*(.*)$", body, re.M)))
    count_matches = counts == [str(count)] or (not counts and constraint_counts == [str(count)])
    if type(count) is not int or count < len(cards) or not count_matches or (constraint_counts and constraint_counts != [str(count)]):
        add("subject_count", "FAIL", "Subject count is inconsistent with text or selected cards")
    refs = meta.get("references")
    if type(meta.get("text_only", False)) is not bool:
        raise ValueError("text_only must be a boolean")
    if not isinstance(refs, list) or any(not isinstance(ref, dict) for ref in refs):
        raise ValueError("references must be a list of objects")
    if not refs and not meta.get("text_only", False):
        add("reference_missing", "FAIL", "Empty references require explicit text_only mode")
    if refs and meta.get("text_only", False):
        add("reference_mode", "FAIL", "text_only mode cannot contain image references")
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
        if (not card_sources and not meta.get("text_only", False)) or -1 in positions or positions != sorted(set(positions)):
            add("card_references", "FAIL", "Required card references are missing or reordered")
    budget = meta.get("prompt_budget_seconds")
    window = meta.get("usable_window")
    if type(budget) not in (int, float) or not 0 < budget < float("inf"):
        add("planning_capacity", "FAIL", "Positive finite planning capacity required")
    else:
        # The provisional planning default follows the canonical main file;
        # explicit adopted capacity overrides it. It is not a measured limit.
        effective_limit = max_clip_seconds if max_clip_seconds is not None else meta.get("planning_limit_seconds", 10)
        for limit in (effective_limit,):
            if limit is not None and (type(limit) not in (int, float) or not 0 < limit < float("inf") or budget > limit):
                add("planning_capacity", "FAIL", "Planning capacity exceeds the supplied project limit")
        if not isinstance(window, list) or len(window) != 2 or any(type(value) not in (int, float) for value in window) or not 0 <= window[0] < window[1] <= budget:
            add("usable_window", "FAIL", "Target window must fit the planning capacity")
    for field in ("场景", "镜头", "声音"):
        if not re.search(r"^" + field + r"：[ \t]*\S", body, re.M):
            add("input_field", "FAIL", f"Missing {field} field")
    full_action = all(re.search(r"^" + field + r"：[ \t]*\S", body, re.M) for field in ("起点", "动作", "终点"))
    if not full_action:
        segments = re.findall(r"^(\d+(?:\.\d+)?)\s*[-–—~～]\s*(\d+(?:\.\d+)?)\s*秒[：:]\s*(\S[^\n]*)$", body, re.M)
        valid = bool(segments)
        previous = None
        for start, end, action in segments:
            start, end = float(start), float(end)
            if not 0 <= start < end or (previous is not None and abs(start - previous) > 1e-6) or type(budget) not in (int, float) or end > budget:
                valid = False
            previous = end
        if not valid:
            add("action_structure", "FAIL", "Use start/action/end fields or consecutive timed action segments within capacity")
    policies = meta.get("policies", {})
    if not isinstance(policies, dict):
        raise ValueError("policies must be an object")
    mode = meta.get("mode", "idea")
    if mode not in ("idea", "detailed", "test"):
        raise ValueError("mode must be idea, detailed or test")
    frozen = meta.get("frozen_blocks", {})
    if not isinstance(frozen, dict) or any(not isinstance(value, str) or not value.strip() for value in frozen.values()):
        raise ValueError("frozen_blocks must map names to non-empty original strings")
    if mode == "detailed" and not frozen:
        add("original_blocks", "FAIL", "Detailed mode requires extracted original frozen blocks")
    for name, original in frozen.items():
        if original not in body:
            add("original_blocks", "FAIL", "Original adopted block changed or missing: " + name)
    for key in ("scene_block", "constraint_block"):
        block = meta.get(key, "")
        if not isinstance(block, str):
            raise ValueError(key + " must be a string")
        if block and block not in body:
            add(key, "FAIL", "Frozen project block differs")
    adopted_constraint = frozen.get("constraint") or meta.get("constraint_block")
    required_default = [adopted_constraint] if mode == "detailed" and adopted_constraint else ["无文字", "无字幕", "无水印"]
    for key in ("required_literals", "forbidden_literals"):
        literals = policies.get(key, required_default if key == "required_literals" else [])
        if not isinstance(literals, list) or any(not isinstance(item, str) or not item for item in literals):
            raise ValueError(key + " must be a list of non-empty strings")
        for literal in literals:
            if (literal not in body) if key == "required_literals" else positive_occurrence(body, re.escape(literal)):
                add("project_policy", "FAIL", key + ": " + literal)
    sound = "\n".join(re.findall(r"^声音：[ \t]*(.*)$", body, re.M))
    for key, pattern in (("allow_music", r"音乐|配乐|BGM|music"), ("allow_dialogue", r"对白|旁白|台词|说话|dialogue|narration")):
        setting = meta.get(key, policies.get(key, False))
        if setting is not None and type(setting) is not bool:
            raise ValueError(key + " must be a boolean")
        if setting is False and positive_occurrence(sound, pattern):
            add("sound_policy", "FAIL", key + " contradicts sound input")
    max_beats = policies.get("max_beats", 2)
    if max_beats is not None:
        if type(max_beats) is not int or max_beats < 0:
            raise ValueError("max_beats must be a nonnegative integer")
        if shot_beat_count(body) > max_beats:
            add("beat_limit", "FAIL", "Action beats exceed the adopted per-shot limit")
    allow_timed_negation = policies.get("allow_timed_negation", False)
    if type(allow_timed_negation) is not bool:
        raise ValueError("allow_timed_negation must be a boolean")
    timed_actions = [action for _, _, action in TIMED_LINE.findall(body)]
    if not allow_timed_negation and any("不要" in action for action in timed_actions):
        add("timed_negation", "FAIL", "Rewrite 不要 inside timed lines as the visible action; keep real bans in the constraint line")
    camera_limit = policies.get("max_camera_moves", 1)
    if camera_limit is not None:
        if type(camera_limit) is not int or camera_limit < 0:
            raise ValueError("max_camera_moves must be a nonnegative integer")
        camera = "\n".join(re.findall(r"^镜头：[ \t]*(.*)$", body, re.M))
        groups = (r"固定|static|locked", r"推镜|推近|推进|push|dolly.?in", r"拉镜|拉远|pull|dolly.?out", r"横移|摇镜|摇摄|pan|truck", r"环绕|orbit", r"跟随|跟拍|track", r"升降|crane")
        if sum(positive_occurrence(camera, pattern) for pattern in groups) > camera_limit:
            add("camera_policy", "FAIL", "Recognized camera move types exceed explicit project limit")
        if camera_limit == 1 and re.search(r"然后|再", camera):
            add("camera_policy", "FAIL", "Sequential camera instructions conflict with adopted single-camera policy")
    management = r"请用下面|原样使用|贴给我|先查能力|逐镜批准|返回.*Task ID|回传.*版本|生成后.*质检"
    if positive_occurrence(body, management):
        add("management_in_model_input", "FAIL" if policies.get("forbid_management_text", True) is True else "WARN", "Keep orchestration outside the visual model input")
    visual = "\n".join(re.findall(r"^(?:起点|动作|终点|镜头|场景)：[ \t]*(.*)$", body, re.M))
    if re.search(r"不要|禁止", visual):
        add("visual_negation", "WARN", "Compare positive visual states without deleting adopted prohibitions; effectiveness untested")
    if not meta.get("required_event") or str(meta["required_event"]).startswith("待"):
        add("required_event", "FAIL", "Actual necessary event must be recorded")
    add("manual_review", "WARN", "Check real uploads, visual/text consistency, causal action, continuity and actual permissions separately")
    return {"status": "needs_fix" if any(item["status"] == "FAIL" for item in findings) else "text_checked",
            "findings": findings, "model_input": body,
            "semantic_review": "unverified", "platform_binding": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shot", type=Path, required=True)
    parser.add_argument("--card", type=Path, action="append", default=[])
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
