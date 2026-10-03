#!/usr/bin/env python3
"""Read real media specs and scene-change candidates; never generate or judge story."""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys


def number(value):
    try:
        result = float(Fraction(str(value).replace(":", "/")))
        return result if math.isfinite(result) and result > 0 else None
    except (ValueError, ZeroDivisionError, TypeError, OverflowError):
        return None


def validate_targets(target_aspect=None, min_seconds=None, max_seconds=None,
                     min_short_side=720, aspect_tolerance=0.01):
    for key, value in locals().items():
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (key != "aspect_tolerance" and value == 0)):
            raise ValueError("Invalid finite positive threshold: " + key)
    if min_seconds is not None and max_seconds is not None and min_seconds > max_seconds:
        raise ValueError("min-seconds exceeds max-seconds")


def evaluate_probe(probe, target_aspect=None, min_seconds=None, max_seconds=None,
                   min_short_side=720, aspect_tolerance=0.01, cut_times=None):
    validate_targets(target_aspect, min_seconds, max_seconds, min_short_side, aspect_tolerance)
    if not isinstance(probe, dict) or not isinstance(probe.get("streams"), list):
        raise ValueError("ffprobe data requires streams")
    streams = probe["streams"]
    videos = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
    findings = []
    def add(code, status, detail):
        findings.append({"code": code, "status": status, "detail": detail})
    spec = {}
    if len(videos) != 1:
        add("video_stream", "FAIL" if not videos else "UNVERIFIED", "No playable video or ambiguous multiple video streams")
    else:
        stream = videos[0]
        width, height = number(stream.get("width")), number(stream.get("height"))
        sar = number(stream.get("sample_aspect_ratio"))
        dar = number(stream.get("display_aspect_ratio"))
        rotation = stream.get("tags", {}).get("rotate", 0)
        for data in stream.get("side_data_list", []):
            if isinstance(data, dict) and "rotation" in data:
                rotation = data["rotation"]
        try:
            rotation = float(rotation)
            if not math.isfinite(rotation) or abs(rotation % 90) > 1e-6:
                raise ValueError()
        except (ValueError, TypeError):
            rotation = None
        if width and height and rotation is not None:
            aspect = dar if dar else (width * sar / height if sar else None)
            if aspect and int(round(rotation / 90)) % 2:
                aspect = 1 / aspect
            if aspect is None:
                add("display_aspect", "UNVERIFIED", "Pixel/display aspect missing; do not assume square pixels")
            elif target_aspect is not None and abs(aspect - target_aspect) > aspect_tolerance:
                add("aspect", "FAIL", "Display aspect outside adopted tolerance")
            short_side = min(width, height)
            if min_short_side is not None and short_side < min_short_side:
                add("short_side", "WARN", "Short side below adopted warning threshold")
            spec.update(width=width, height=height, rotation=rotation, aspect=aspect, short_side=short_side)
        else:
            add("dimensions", "UNVERIFIED", "Missing dimensions or unsupported rotation")
        duration = number(stream.get("duration"))
        if duration is None:
            duration_ts, time_base = number(stream.get("duration_ts")), number(stream.get("time_base"))
            if duration_ts and time_base:
                duration = duration_ts * time_base
        spec["duration"] = duration
        spec["fps"] = number(stream.get("avg_frame_rate"))
        if duration is None:
            add("duration", "UNVERIFIED", "Video-stream duration unavailable; container/audio duration is not proof")
        elif (min_seconds is not None and duration < min_seconds) or (max_seconds is not None and duration > max_seconds):
            add("duration", "FAIL", "Video duration outside adopted range")
    if cut_times is None:
        add("cut_scan", "UNVERIFIED", "No completed scene-change scan")
    elif cut_times:
        add("cut_scan", "WARN", "Possible cuts/concatenation; flashes or exposure can also trigger; inspect continuous intervals")
    states = {row["status"] for row in findings}
    status = "FAIL" if "FAIL" in states else "UNVERIFIED" if "UNVERIFIED" in states else "WARN" if "WARN" in states else "PASS"
    return {"status":status,"spec_gate":status,"spec":spec,"findings":findings,
            "possible_cut_times":cut_times,"content_review":"UNVERIFIED","audio_review":"UNVERIFIED",
            "defaults":"thresholds are provisional / 待测; adopted project targets override"}


def inspect(path, scene_threshold=0.35, **targets):
    path = Path(path)
    validate_targets(**targets)
    if type(scene_threshold) not in (int, float) or not math.isfinite(scene_threshold) or not 0 < scene_threshold <= 1:
        raise ValueError("scene-threshold must be in (0, 1]")
    if not path.is_file():
        raise ValueError("Actual media file does not exist")
    ffprobe, ffmpeg = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not ffprobe:
        return {"status":"UNVERIFIED","spec_gate":"UNVERIFIED","findings":[{"code":"ffprobe_missing","status":"UNVERIFIED","detail":"Install official FFmpeg or inspect with another actual tool"}]}
    result = subprocess.run([ffprobe,"-v","error","-show_streams","-show_format","-of","json",str(path)],capture_output=True,text=True,encoding="utf-8",timeout=60)
    if result.returncode:
        return {"status":"FAIL","spec_gate":"FAIL","findings":[{"code":"decode","status":"FAIL","detail":result.stderr.strip()}]}
    probe = json.loads(result.stdout)
    videos = [s for s in probe.get("streams", []) if isinstance(s, dict) and s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")]
    cut_times = None
    if ffmpeg and len(videos) == 1 and isinstance(videos[0].get("index"), int):
        # Read-only filter output goes to stderr; no media/log file is overwritten.
        scan = subprocess.run([ffmpeg,"-v","info","-i",str(path),"-map",f"0:{videos[0]['index']}","-vf",f"select=gt(scene\\,{scene_threshold}),showinfo","-an","-f","null","-"],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=60)
        if scan.returncode == 0:
            cut_times = [float(t) for t in re.findall(r"pts_time:([\d.]+)", scan.stderr)]
    report = evaluate_probe(probe, cut_times=cut_times, **targets)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda:source.read(1024*1024), b""):
            digest.update(chunk)
    report.update(file=str(path.resolve()),sha256=digest.hexdigest(),scene_threshold=scene_threshold)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file",type=Path)
    parser.add_argument("--target-aspect",type=float)
    parser.add_argument("--min-seconds",type=float)
    parser.add_argument("--max-seconds",type=float)
    parser.add_argument("--min-short-side",type=float,default=720)
    parser.add_argument("--aspect-tolerance",type=float,default=0.01)
    parser.add_argument("--scene-threshold",type=float,default=0.35,help="Provisional / 待测; scene-change candidate threshold in (0,1]")
    args = vars(parser.parse_args())
    path = args.pop("file")
    try:
        report = inspect(path, **args)
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
        report = {"status":"UNVERIFIED","spec_gate":"UNVERIFIED","error":str(exc)}
    print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    return {"PASS":0,"WARN":0,"FAIL":2,"UNVERIFIED":3}[report["status"]]


if __name__ == "__main__":
    sys.exit(main())
