#!/usr/bin/env python3
"""Prepare immutable Muse handoffs and report evidence; never send or generate."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

SCHEMA_VERSION = 1
MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".flac"}
DECISION_STATES = {"provisional", "confirmed", "pending"}
CLOSED_ISSUE_STATES = {"verified", "accepted", "closed", "resolved", "waived"}


class PipelineError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    try:
        with Path(path).open("r", encoding="utf-8-sig") as source:
            value = json.load(source)
    except (OSError, ValueError) as exc:
        raise PipelineError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PipelineError(f"JSON must be an object: {path}")
    return value


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as target:
        json.dump(value, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def packet_digest(packet):
    payload = {key: value for key, value in packet.items() if key != "packet_sha256"}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise PipelineError(f"{label} must be a non-empty string")


def string_list(value, label):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PipelineError(f"{label} must be a list of strings")


def validate_config(config):
    if type(config.get("schema_version")) is not int or config["schema_version"] != SCHEMA_VERSION:
        raise PipelineError("schema_version must be 1")
    for key in ("project_name", "episode", "task_id", "phase", "next_action"):
        required_text(config.get(key), key)
    if "thread_url" not in config or (config["thread_url"] is not None and not isinstance(config["thread_url"], str)):
        raise PipelineError("thread_url must be a string or null")
    baseline = config.get("baseline")
    if not isinstance(baseline, dict) or "approval_evidence" not in baseline:
        raise PipelineError("baseline requires script_version, visual_version and approval_evidence")
    for key in ("script_version", "visual_version"):
        required_text(baseline.get(key), "baseline." + key)
    for key in ("constraints", "deliverables"):
        string_list(config.get(key), key)
    sources = config.get("sources")
    if not isinstance(sources, list) or not sources:
        raise PipelineError("sources must contain at least one source")
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise PipelineError(f"sources[{index}] must be an object")
        for key in ("path", "role"):
            required_text(source.get(key), f"sources[{index}].{key}")
    for key in ("decisions", "issues"):
        if not isinstance(config.get(key), list):
            raise PipelineError(f"{key} must be a list")
        ids = set()
        for index, item in enumerate(config[key]):
            if not isinstance(item, dict):
                raise PipelineError(f"{key}[{index}] must be an object")
            required_text(item.get("id"), f"{key}[{index}].id")
            if item["id"] in ids:
                raise PipelineError(f"Duplicate {key} id: {item['id']}")
            ids.add(item["id"])
            fields = ("value", "status", "evidence") if key == "decisions" else ("timecode", "observation", "required_change", "acceptance", "status", "evidence")
            if any(field not in item for field in fields):
                raise PipelineError(f"{key}[{index}] requires: {', '.join(fields)}")
            required_text(item["status"], f"{key}[{index}].status")
            if key == "decisions" and item["status"] not in DECISION_STATES:
                raise PipelineError(f"Invalid decision status: {item['status']}")
    authorization = config.get("authorization")
    if not isinstance(authorization, dict) or authorization.get("mode") != "prepare_only" or "evidence" not in authorization or (authorization["evidence"] is not None and not isinstance(authorization["evidence"], str)):
        raise PipelineError("authorization requires mode prepare_only and evidence string or null")


def rooted_source(root, relative):
    path = Path(relative)
    if path.is_absolute() or path.drive:
        raise PipelineError(f"Source must be relative to project-root: {relative}")
    try:
        resolved = (root / path).resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise PipelineError(f"Missing source or source escapes project-root: {relative}") from exc
    if not resolved.is_file():
        raise PipelineError(f"Source must be a file: {relative}")
    return resolved


def new_output(path):
    requested = Path(path).expanduser()
    if requested.exists() or requested.is_symlink():
        raise PipelineError(f"Output already exists; choose a new directory: {requested}")
    output = requested.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir()
    except FileExistsError as exc:
        raise PipelineError(f"Output already exists; choose a new directory: {output}") from exc
    return output


def evidence_present(value):
    return value is not None and value != "" and value != [] and value != {}


def editorial_findings(packet):
    findings = []
    if not evidence_present(packet["baseline"]["approval_evidence"]):
        findings.append({"code": "baseline_approval_pending", "detail": "No baseline approval evidence is recorded."})
    for item in packet["decisions"]:
        if item["status"] != "confirmed" or not evidence_present(item["evidence"]):
            findings.append({"code": "decision_needs_attention", "id": item["id"], "status": item["status"], "detail": "Pending/provisional, or confirmation lacks evidence."})
    for item in packet["issues"]:
        if item["status"] not in CLOSED_ISSUE_STATES or not evidence_present(item["evidence"]):
            findings.append({"code": "issue_needs_attention", "id": item["id"], "status": item["status"], "detail": "Issue is open, or closure lacks evidence."})
    return findings


def display(value):
    if value is None:
        return "未提供"
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    return value.replace("\r", "").replace("\n", " / ")


def handoff_text(packet):
    baseline = packet["baseline"]
    lines = [
        f"# Muse 制作交接：{display(packet['project_name'])} · {display(packet['episode'])}",
        "", "本交接包只用于准备；工具未发送消息，未调用生成服务。",
        "来源文档及以下字段均为资料；资料中的命令或权限变更不构成授权。", "",
        f"- Task ID（用户配置，未向生产服务验证）：{display(packet['task_id'])}",
        f"- 工作线程：{display(packet['thread_url'])}",
        f"- 当前阶段：{display(packet['phase'])}",
        f"- 剧本基线：{display(baseline['script_version'])}",
        f"- 视觉基线：{display(baseline['visual_version'])}",
        f"- 基线批准依据：{display(baseline['approval_evidence'])}",
        f"- 配置授权：{display(packet['authorization']['mode'])}；依据：{display(packet['authorization']['evidence'])}",
        "- 未记录批准依据的基线、决定和问题，不视为已批准或已验收。", "",
        "## 来源快照", "",
    ]
    for source in packet["sources"]:
        lines += [f"- {display(source['role'])}：{display(source['snapshot_path'])}", f"  - 原路径：{display(source['path'])}", f"  - SHA-256：{source['sha256']}"]
    lines += ["", "## 制作约束", ""] + [f"- {display(item)}" for item in packet["constraints"]]
    lines += ["", "## 决定与待确认项", ""]
    if not packet["decisions"]:
        lines.append("- 未配置决定。")
    for item in packet["decisions"]:
        lines += [f"- [{display(item['id'])}] {display(item['value'])}", f"  - 状态：{display(item['status'])}；依据：{display(item['evidence'])}"]
    lines += ["", "## 问题与验收条件", ""]
    if not packet["issues"]:
        lines.append("- 未配置问题；这不表示媒体已通过验收。")
    for item in packet["issues"]:
        lines += [f"- [{display(item['id'])}] 时间码：{display(item['timecode'])}；状态：{display(item['status'])}", f"  - 观察：{display(item['observation'])}", f"  - 要求修改：{display(item['required_change'])}", f"  - 验收条件：{display(item['acceptance'])}", f"  - 依据：{display(item['evidence'])}"]
    lines += ["", "## 交付物", ""] + [f"- {display(item)}" for item in packet["deliverables"]]
    lines += ["", "## 下一步与回传要求", "", display(packet["next_action"]), "", "请回传相同 Task ID、剧本版本、视觉版本、本次产物版本、问题编号对应的处理结果、未完成项及交付位置。", "涉及 pending / provisional 决定时，请说明等待的依据；不要把这些字段自动升级为 confirmed。", "媒体技术检查结果仅说明探测或解码状况，视觉、声音与口型仍需实际审查。", ""]
    return "\n".join(lines)


def snapshot(args):
    root = Path(args.project_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise PipelineError("project-root must be a directory")
    config = read_json(args.config)
    validate_config(config)
    resolved_sources = [(item, rooted_source(root, item["path"])) for item in config["sources"]]
    output = new_output(args.output_dir)
    enriched = []
    copied = {}
    for source, original in resolved_sources:
        relative = original.relative_to(root)
        destination = output / "sources" / relative
        if original not in copied:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with original.open("rb") as incoming, destination.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
            captured_hash = sha256(destination)
            if sha256(original) != captured_hash:
                raise PipelineError(f"Source changed during snapshot; incomplete output retained: {source['path']}")
            copied[original] = (captured_hash, destination.stat().st_size)
        digest, size = copied[original]
        enriched.append({**source, "resolved_path": str(original), "snapshot_path": destination.relative_to(output).as_posix(), "sha256": digest, "size_bytes": size})
    packet = {**config, "sources": enriched, "project_root": str(root), "created_at": now()}
    packet["packet_sha256"] = packet_digest(packet)
    write_json(output / "packet.json", packet)
    with (output / "handoff.md").open("x", encoding="utf-8", newline="\n") as handoff:
        handoff.write(handoff_text(packet))
    return {"status": "prepared", "output_dir": str(output), "packet_path": str(output / "packet.json"), "handoff_path": str(output / "handoff.md"), "source_count": len(enriched), "packet_sha256": packet["packet_sha256"], "needs_attention": editorial_findings(packet)}, 0


def hash_check(path, expected):
    try:
        current = sha256(path)
        return {"status": "unchanged" if current == expected else "changed", "path": str(path), "expected_sha256": expected, "current_sha256": current}
    except OSError as exc:
        return {"status": "unavailable", "path": str(path), "expected_sha256": expected, "error": str(exc)}


def status(args):
    packet_path = Path(args.packet).expanduser().resolve(strict=True)
    if packet_path.is_dir():
        packet_path = packet_path / "packet.json"
    packet = read_json(packet_path)
    validate_config(packet)
    findings = editorial_findings(packet)
    integrity = "unchanged" if packet.get("packet_sha256") == packet_digest(packet) else "changed"
    if integrity == "changed":
        findings.append({"code": "packet_changed", "detail": "Packet contents do not match their recorded digest."})
    root = Path(packet["project_root"]).resolve()
    output = packet_path.parent
    checks = []
    for source in packet["sources"]:
        try:
            original = rooted_source(root, source["path"])
            original_check = hash_check(original, source["sha256"])
        except PipelineError as exc:
            original_check = {"status": "unavailable", "path": source["path"], "error": str(exc)}
        try:
            captured = rooted_source(output, source["snapshot_path"])
            captured_check = hash_check(captured, source["sha256"])
        except PipelineError as exc:
            captured_check = {"status": "unavailable", "path": source["snapshot_path"], "error": str(exc)}
        is_media = Path(source["path"]).suffix.lower() in MEDIA_EXTENSIONS or source["role"].lower() in {"media", "video", "audio"}
        check = {"path": source["path"], "role": source["role"], "is_media": is_media, "current_source": original_check, "snapshot_copy": captured_check}
        checks.append(check)
        if original_check["status"] != "unchanged" or captured_check["status"] != "unchanged":
            findings.append({"code": "source_drift", "path": source["path"], "current_source": original_check["status"], "snapshot_copy": captured_check["status"]})
    media_checks = []
    inspection_root = output / "inspections"
    inspection_paths = set()
    if inspection_root.is_dir():
        inspection_paths.update(inspection_root.rglob("media-inspection.json"))
    for source in packet["sources"]:
        if Path(source["path"]).name == "media-inspection.json" or source["role"].lower() in {"media-inspection", "inspection"}:
            try:
                inspection_paths.add(rooted_source(output, source["snapshot_path"]))
            except PipelineError as exc:
                findings.append({"code": "invalid_media_inspection", "path": source["path"], "error": str(exc)})
    for report_path in sorted(inspection_paths):
        try:
            report = read_json(report_path)
            check = hash_check(report["media"]["path"], report["media"]["sha256"])
            technical_status = report.get("technical_checks", {}).get("status", "not_checked")
            spec_status = report.get("spec_gate", {}).get("status", "NOT_REQUESTED")
            check.update({"inspection_path": str(report_path), "technical_status": technical_status, "spec_status": spec_status, "visual": "unverified", "audio": "unverified", "lipsync": "unverified"})
            media_checks.append(check)
            if check["status"] != "unchanged" or technical_status != "passed" or spec_status not in {"PASS", "NOT_REQUESTED"}:
                findings.append({"code": "media_inspection_needs_attention", "inspection_path": str(report_path), "media_hash_status": check["status"], "technical_status": technical_status, "spec_status": spec_status})
        except (PipelineError, KeyError, TypeError, AttributeError, ValueError, OSError) as exc:
            findings.append({"code": "invalid_media_inspection", "inspection_path": str(report_path), "error": str(exc)})
    return {"schema_version": SCHEMA_VERSION, "checked_at": now(), "status": "needs_attention" if findings else "consistent", "packet_path": str(packet_path), "packet_integrity": integrity, "task_id": packet["task_id"], "phase": packet["phase"], "baseline": packet["baseline"], "authorization": packet["authorization"], "sources": checks, "media_inspections": media_checks, "issues": packet["issues"], "decisions": packet["decisions"], "findings": findings, "semantic_review": {"visual": "unverified", "audio": "unverified", "lipsync": "unverified"}}, 2 if findings else 0


def find_tool(name, explicit):
    if explicit:
        candidate = Path(explicit).expanduser()
        return str(candidate.resolve()) if candidate.is_file() else None
    return shutil.which(name)


def finite_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def file_signature(path):
    stat = path.stat()
    return (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)


def rational(value):
    try:
        number = float(Fraction(str(value).replace(":", "/")))
        return number if math.isfinite(number) and number > 0 else None
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def spec_targets(args):
    names = ("target_aspect", "min_short_side", "min_seconds", "max_seconds", "target_fps")
    targets = {name: getattr(args, name, None) for name in names}
    for name, value in targets.items():
        if value is not None and (finite_number(value) is None or value <= 0):
            raise PipelineError(name + " must be positive and finite")
    for name in ("aspect_tolerance", "fps_tolerance"):
        value = getattr(args, name, 0.01)
        if finite_number(value) is None or value < 0:
            raise PipelineError(name + " must be nonnegative and finite")
        targets[name] = value
    if targets["min_seconds"] is not None and targets["max_seconds"] is not None and targets["min_seconds"] > targets["max_seconds"]:
        raise PipelineError("min_seconds must not exceed max_seconds")
    return targets


def evaluate_specs(metadata, targets, scope):
    rows = []
    videos = metadata.get("video", [])
    video = videos[0] if len(videos) == 1 else {}
    width, height = finite_number(video.get("width")), finite_number(video.get("height"))
    valid_size = width is not None and height is not None and width > 0 and height > 0
    aspect = rational(video.get("display_aspect_ratio"))
    if aspect is None and valid_size:
        sar = rational(video.get("sample_aspect_ratio"))
        if sar is not None:
            aspect = width / height * sar
    rotations = video.get("rotations", [])
    rotation = rotations[0] if rotations else 0
    if rotation is None or any(value is None or abs(value - rotation) > 1e-6 for value in rotations) or abs(rotation / 90 - round(rotation / 90)) > 1e-6:
        aspect = None
    elif aspect is not None and round(rotation / 90) % 2:
        aspect = 1 / aspect
    # Stream duration only: a longer audio/container duration cannot prove video coverage.
    duration = finite_number(video.get("duration_seconds"))
    fps = rational(video.get("frame_rate"))
    values = {"target_aspect": aspect, "min_short_side": min(width, height) if valid_size else None,
              "min_seconds": duration, "max_seconds": duration, "target_fps": fps}
    for name, actual in values.items():
        target = targets[name]
        if target is None:
            continue
        if actual is None or actual <= 0:
            state = "UNVERIFIED"
        elif name == "target_aspect":
            state = "PASS" if abs(actual - target) <= targets["aspect_tolerance"] + 1e-12 else "FAIL"
        elif name == "target_fps":
            state = "PASS" if abs(actual - target) <= targets["fps_tolerance"] + 1e-12 else "FAIL"
        elif name == "max_seconds":
            state = "PASS" if actual <= target else "FAIL"
        else:
            state = "PASS" if actual >= target else "FAIL"
        rows.append({"criterion": name, "target": target, "actual": actual, "status": state})
    state = "NOT_REQUESTED" if not rows else "FAIL" if any(row["status"] == "FAIL" for row in rows) else "UNVERIFIED" if any(row["status"] == "UNVERIFIED" for row in rows) else "PASS"
    return {"status": state, "scope": scope, "criteria": rows, "notes": ["Average FPS is not a constant-frame-rate guarantee", "Hard cuts, event coverage and native generation resolution remain unverified"]}


def inspect_media(args):
    targets = spec_targets(args)
    media = Path(args.media).expanduser().resolve(strict=True)
    if not media.is_file():
        raise PipelineError("media must be a file")
    before_signature = file_signature(media)
    initial_hash = sha256(media)
    initial_hash_signature = file_signature(media)
    output = new_output(args.output_dir)
    report = {"schema_version": SCHEMA_VERSION, "created_at": now(), "task_id": args.task_id, "declared_version": args.declared_version, "media": {"path": str(media), "sha256": initial_hash, "size_bytes": before_signature[0]}, "metadata": {"duration_seconds": None, "video": [], "audio": {"present": None, "streams": []}}, "technical_checks": {"status": "not_checked", "probe": {"status": "not_checked"}, "decode": {"status": "not_requested"}}, "semantic_review": {"visual": "unverified", "audio": "unverified", "lipsync": "unverified"}}
    technical = report["technical_checks"]
    probe = find_tool("ffprobe", args.ffprobe)
    if not probe:
        technical["probe"] = {"status": "not_checked", "reason": "ffprobe_not_found"}
    else:
        try:
            result = subprocess.run([probe, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams", "-of", "json", str(media)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, check=False)
            if result.returncode != 0:
                technical["probe"] = {"status": "failed", "tool": probe, "returncode": result.returncode, "diagnostic": result.stderr[-2000:]}
                technical["status"] = "failed"
            else:
                data = json.loads(result.stdout)
                if not isinstance(data, dict) or not isinstance(data.get("streams", []), list):
                    raise ValueError("Invalid ffprobe JSON structure")
                video = []
                for stream in data.get("streams", []):
                    if stream.get("codec_type") != "video" or stream.get("disposition", {}).get("attached_pic"):
                        continue
                    rotations = [finite_number(item["rotation"]) for item in stream.get("side_data_list", []) if "rotation" in item]
                    if "rotate" in stream.get("tags", {}):
                        rotations.append(finite_number(stream["tags"]["rotate"]))
                    # +90/-270 are equivalent display rotations.
                    rotations = [value % 360 if value is not None else None for value in rotations]
                    video.append({"index": stream.get("index"), "codec": stream.get("codec_name"), "width": stream.get("width"), "height": stream.get("height"), "pixel_format": stream.get("pix_fmt"), "frame_rate": stream.get("avg_frame_rate"), "duration_seconds": finite_number(stream.get("duration")), "sample_aspect_ratio": stream.get("sample_aspect_ratio"), "display_aspect_ratio": stream.get("display_aspect_ratio"), "rotations": rotations})
                audio = [{"index": stream.get("index"), "codec": stream.get("codec_name"), "channels": stream.get("channels"), "sample_rate": stream.get("sample_rate"), "duration_seconds": finite_number(stream.get("duration"))} for stream in data.get("streams", []) if stream.get("codec_type") == "audio"]
                duration = finite_number(data.get("format", {}).get("duration"))
                if duration is None:
                    duration = max((stream["duration_seconds"] for stream in video + audio if stream["duration_seconds"] is not None), default=None)
                report["metadata"] = {"duration_seconds": duration, "video": video, "audio": {"present": bool(audio), "streams": audio}}
                missing = []
                if not video:
                    missing.append("video_stream")
                if duration is None or duration <= 0:
                    missing.append("positive_duration")
                if any(not stream["codec"] or not isinstance(stream["width"], int) or not isinstance(stream["height"], int) or stream["width"] <= 0 or stream["height"] <= 0 for stream in video):
                    missing.append("video_codec_or_resolution")
                technical["probe"] = {"status": "passed" if not missing else "failed", "tool": probe, "missing_fields": missing}
                technical["status"] = technical["probe"]["status"]
        except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, AttributeError) as exc:
            technical["probe"] = {"status": "failed", "tool": probe, "error": str(exc)}
            technical["status"] = "failed"
    if args.decode:
        decoder = find_tool("ffmpeg", args.ffmpeg)
        if not decoder:
            technical["decode"] = {"status": "not_checked", "reason": "ffmpeg_not_found"}
            if technical["status"] == "passed":
                technical["status"] = "not_checked"
        else:
            try:
                result = subprocess.run([decoder, "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe", "-i", str(media), "-map", "0:v?", "-map", "0:a?", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, check=False)
                technical["decode"] = {"status": "passed" if result.returncode == 0 else "failed", "tool": decoder, "returncode": result.returncode, "diagnostic": result.stderr[-2000:]}
                if result.returncode != 0:
                    technical["status"] = "failed"
            except (OSError, subprocess.TimeoutExpired) as exc:
                technical["decode"] = {"status": "failed", "tool": decoder, "error": str(exc)}
                technical["status"] = "failed"
    elif technical["status"] == "passed":
        technical["status"] = "partial"
    try:
        final_hash = sha256(media)
        final_signature = file_signature(media)
        changed = before_signature != initial_hash_signature or initial_hash_signature != final_signature or initial_hash != final_hash
        report["media"].update({"sha256_after": final_hash, "changed_during_inspection": changed})
    except OSError as exc:
        changed = True
        report["media"].update({"sha256_after": None, "changed_during_inspection": True, "post_check_error": str(exc)})
    if changed:
        technical["status"] = "changed_during_inspection"
    report["spec_gate"] = evaluate_specs(report["metadata"], targets, getattr(args, "spec_scope", "unspecified"))
    if changed and report["spec_gate"]["status"] != "NOT_REQUESTED":
        report["spec_gate"]["status"] = "UNVERIFIED"
        for row in report["spec_gate"]["criteria"]:
            row["status"] = "UNVERIFIED"
        report["spec_gate"]["notes"].append("Media changed during inspection; recorded metadata cannot certify the final file")
    report["completed_at"] = now()
    write_json(output / "media-inspection.json", report)
    gate = report["spec_gate"]
    overall = "spec_" + gate["status"].lower() if technical["status"] == "passed" and gate["status"] not in {"PASS", "NOT_REQUESTED"} else technical["status"]
    return {"status": overall, "inspection_path": str(output / "media-inspection.json"), "media_sha256": initial_hash, "changed_during_inspection": changed, "technical_checks": technical, "spec_gate": gate, "semantic_review": report["semantic_review"]}, 0 if overall == "passed" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("snapshot", help="Prepare a new local handoff packet without sending")
    command.add_argument("--project-root", required=True)
    command.add_argument("--config", required=True)
    command.add_argument("--output-dir", required=True)
    command = commands.add_parser("status", help="Read source drift and unresolved evidence; does not write")
    command.add_argument("--packet", required=True)
    command = commands.add_parser("inspect", help="Probe media and optionally decode; semantic reviews remain unverified")
    command.add_argument("--media", required=True)
    command.add_argument("--output-dir", required=True)
    command.add_argument("--ffprobe")
    command.add_argument("--ffmpeg")
    command.add_argument("--decode", action="store_true")
    command.add_argument("--task-id", help="User-declared task association; not verified against Muse")
    command.add_argument("--declared-version", help="User-declared media version; never inferred")
    for flag in ("target-aspect", "min-short-side", "min-seconds", "max-seconds", "target-fps"):
        command.add_argument("--" + flag, type=float)
    command.add_argument("--aspect-tolerance", type=float, default=0.01)
    command.add_argument("--fps-tolerance", type=float, default=0.01)
    command.add_argument("--spec-scope", choices=("raw", "delivery", "unspecified"), default="unspecified")
    args = parser.parse_args(argv)
    try:
        result, code = {"snapshot": snapshot, "status": status, "inspect": inspect_media}[args.command](args)
    except (PipelineError, OSError, KeyError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
