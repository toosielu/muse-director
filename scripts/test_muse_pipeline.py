"""Meaningful boundaries for local snapshot and technical evidence only."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import muse_pipeline as pipeline


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "项目"
        self.root.mkdir()
        (self.root / "剧本.md").write_text("原剧本\n", encoding="utf-8")
        self.config = {"schema_version": 1, "project_name": "动画", "episode": "EP02", "task_id": "user-supplied-task", "thread_url": None, "baseline": {"script_version": "v1", "visual_version": "v1", "approval_evidence": "用户确认记录"}, "phase": "prepare", "sources": [{"path": "剧本.md", "role": "script"}], "constraints": ["单人单场景"], "decisions": [], "issues": [], "deliverables": ["样片.mp4"], "authorization": {"mode": "prepare_only", "evidence": None}, "next_action": "准备工作包"}
        self.config_path = self.base / "config.json"
        self.save_config()

    def save_config(self):
        self.config_path.write_text(json.dumps(self.config, ensure_ascii=False), encoding="utf-8")

    def run_cli(self, *arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = pipeline.main(list(arguments))
        return code, json.loads(stdout.getvalue() or stderr.getvalue())

    def snapshot(self, name="packet"):
        return self.run_cli("snapshot", "--project-root", str(self.root), "--config", str(self.config_path), "--output-dir", str(self.base / name))

    def media_args(self, name="inspection", decode=False):
        media = self.base / "动画.mp4"
        if not media.exists():
            media.write_bytes(b"fake media bytes")
        args = ["inspect", "--media", str(media), "--output-dir", str(self.base / name)]
        if decode:
            args.append("--decode")
        return args

    @staticmethod
    def successful_probe():
        data = {"format": {"duration": "1.0"}, "streams": [{"index": 0, "codec_type": "video", "codec_name": "h264", "width": 320, "height": 180, "pix_fmt": "yuv420p", "avg_frame_rate": "24/1"}, {"index": 1, "codec_type": "audio", "codec_name": "aac", "channels": 2}]}
        return subprocess.CompletedProcess([], 0, json.dumps(data), "")

    def test_unicode_snapshot_and_read_only_status(self):
        code, result = self.snapshot()
        self.assertEqual(code, 0)
        packet_dir = self.base / "packet"
        self.assertTrue((packet_dir / "sources" / "剧本.md").is_file())
        packet = json.loads((packet_dir / "packet.json").read_text(encoding="utf-8"))
        self.assertEqual(packet["packet_sha256"], pipeline.packet_digest(packet))
        before = {str(path): (path.read_bytes(), path.stat().st_mtime_ns) for path in packet_dir.rglob("*") if path.is_file()}
        code, status = self.run_cli("status", "--packet", str(packet_dir))
        self.assertEqual(code, 0)
        self.assertEqual(status["status"], "consistent")
        after = {str(path): (path.read_bytes(), path.stat().st_mtime_ns) for path in packet_dir.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_source_escape_refused_before_output_creation(self):
        (self.base / "outside.md").write_text("outside", encoding="utf-8")
        self.config["sources"] = [{"path": "../outside.md", "role": "script"}]
        self.save_config()
        code, result = self.snapshot()
        self.assertEqual(code, 1)
        self.assertIn("escapes", result["error"])
        self.assertFalse((self.base / "packet").exists())

    def test_symlink_escape_refused(self):
        outside = self.base / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        try:
            (self.root / "link.md").symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"Symlink creation unavailable: {exc}")
        self.config["sources"] = [{"path": "link.md", "role": "script"}]
        self.save_config()
        code, result = self.snapshot()
        self.assertEqual(code, 1)
        self.assertFalse((self.base / "packet").exists())

    def test_output_cannot_be_overwritten_by_snapshot_or_inspect(self):
        self.assertEqual(self.snapshot()[0], 0)
        packet = self.base / "packet" / "packet.json"
        before = packet.read_bytes()
        self.assertEqual(self.snapshot()[0], 1)
        with patch.object(pipeline, "find_tool", return_value=None):
            self.assertEqual(self.run_cli(*self.media_args(name="packet"))[0], 1)
        self.assertEqual(before, packet.read_bytes())

    def test_existing_broken_output_symlink_is_not_overwritten(self):
        output = self.base / "packet"
        try:
            output.symlink_to(self.base / "missing-target", target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Symlink creation unavailable: {exc}")
        code, result = self.snapshot()
        self.assertEqual(code, 1)
        self.assertTrue(output.is_symlink())
        self.assertFalse((self.base / "missing-target").exists())

    def test_original_and_snapshot_drift_detected(self):
        self.snapshot()
        (self.root / "剧本.md").write_text("变更后的剧本", encoding="utf-8")
        code, result = self.run_cli("status", "--packet", str(self.base / "packet"))
        self.assertEqual(code, 2)
        self.assertEqual(result["sources"][0]["current_source"]["status"], "changed")
        self.assertEqual(result["sources"][0]["snapshot_copy"]["status"], "unchanged")
        (self.base / "packet" / "sources" / "剧本.md").write_text("被改动的快照", encoding="utf-8")
        code, result = self.run_cli("status", "--packet", str(self.base / "packet"))
        self.assertEqual(result["sources"][0]["snapshot_copy"]["status"], "changed")

    def test_packet_tampering_detected(self):
        self.snapshot()
        path = self.base / "packet" / "packet.json"
        packet = json.loads(path.read_text(encoding="utf-8"))
        packet["phase"] = "changed"
        path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
        code, result = self.run_cli("status", "--packet", str(path))
        self.assertEqual(code, 2)
        self.assertEqual(result["packet_integrity"], "changed")

    def test_provisional_and_missing_evidence_remain_unapproved(self):
        self.config["baseline"]["approval_evidence"] = None
        self.config["decisions"] = [{"id": "D01", "value": "角色笑一下", "status": "provisional", "evidence": None}]
        self.config["issues"] = [{"id": "I01", "timecode": "00:01", "observation": "嘴型不同步", "required_change": "重做", "acceptance": "实际看片", "status": "closed", "evidence": None}]
        self.save_config()
        self.snapshot()
        code, result = self.run_cli("status", "--packet", str(self.base / "packet"))
        self.assertEqual(code, 2)
        self.assertEqual(len(result["findings"]), 3)
        self.assertEqual(result["decisions"][0]["status"], "provisional")

    def test_missing_probe_never_passes_even_if_decode_passes(self):
        def lookup(name, explicit):
            return None if name == "ffprobe" else "fake-ffmpeg"
        with patch.object(pipeline, "find_tool", side_effect=lookup), patch.object(pipeline.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")):
            code, result = self.run_cli(*self.media_args(decode=True))
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "not_checked")
        self.assertEqual(result["technical_checks"]["probe"]["status"], "not_checked")

    def test_probe_failure_never_passes(self):
        with patch.object(pipeline, "find_tool", return_value="fake-ffprobe"), patch.object(pipeline.subprocess, "run", return_value=subprocess.CompletedProcess([], 7, "", "broken file")):
            code, result = self.run_cli(*self.media_args())
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "failed")

    def test_decode_failure_never_passes(self):
        with patch.object(pipeline, "find_tool", return_value="fake-tool"), patch.object(pipeline.subprocess, "run", side_effect=[self.successful_probe(), subprocess.CompletedProcess([], 8, "", "decode error")]):
            code, result = self.run_cli(*self.media_args(decode=True))
        self.assertEqual(code, 2)
        self.assertEqual(result["technical_checks"]["decode"]["status"], "failed")

    def test_missing_requested_decoder_never_passes(self):
        def lookup(name, explicit):
            return "fake-ffprobe" if name == "ffprobe" else None
        with patch.object(pipeline, "find_tool", side_effect=lookup), patch.object(pipeline.subprocess, "run", return_value=self.successful_probe()):
            code, result = self.run_cli(*self.media_args(decode=True))
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "not_checked")

    def test_media_replacement_during_probe_cannot_pass(self):
        media = self.base / "动画.mp4"
        args = self.media_args()
        def replace_during_probe(*unused_args, **unused_kwargs):
            media.write_bytes(b"replaced while probing")
            return self.successful_probe()
        with patch.object(pipeline, "find_tool", return_value="fake-ffprobe"), patch.object(pipeline.subprocess, "run", side_effect=replace_during_probe):
            code, result = self.run_cli(*args)
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "changed_during_inspection")
        self.assertTrue(result["changed_during_inspection"])

    def test_audio_presence_never_claims_semantic_review(self):
        with patch.object(pipeline, "find_tool", return_value="fake-ffprobe"), patch.object(pipeline.subprocess, "run", return_value=self.successful_probe()):
            code, result = self.run_cli(*self.media_args())
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["technical_checks"]["probe"]["status"], "passed")
        self.assertEqual(result["technical_checks"]["decode"]["status"], "not_requested")
        self.assertEqual(result["semantic_review"], {"visual": "unverified", "audio": "unverified", "lipsync": "unverified"})
        report = json.loads((self.base / "inspection" / "media-inspection.json").read_text(encoding="utf-8"))
        self.assertTrue(report["metadata"]["audio"]["present"])
        self.assertEqual(report["metadata"]["video"][0]["pixel_format"], "yuv420p")

    def test_task_and_version_are_only_user_declared(self):
        with patch.object(pipeline, "find_tool", return_value=None):
            self.run_cli(*self.media_args(), "--task-id", "task-user-supplied", "--declared-version", "vFinal候选")
            self.run_cli(*self.media_args(name="inspection-without-ids"))
        declared = json.loads((self.base / "inspection" / "media-inspection.json").read_text(encoding="utf-8"))
        missing = json.loads((self.base / "inspection-without-ids" / "media-inspection.json").read_text(encoding="utf-8"))
        self.assertEqual(declared["task_id"], "task-user-supplied")
        self.assertEqual(declared["declared_version"], "vFinal候选")
        self.assertIsNone(missing["task_id"])
        self.assertIsNone(missing["declared_version"])

    def test_authorization_scope_can_be_recorded_without_upgrade(self):
        self.config["authorization"]["evidence"] = "本轮查看优化，没有发送"
        self.save_config()
        self.assertEqual(self.snapshot()[0], 0)
        self.config["authorization"]["mode"] = "send"
        self.save_config()
        self.assertEqual(self.snapshot(name="not-authorized")[0], 1)
        self.assertFalse((self.base / "not-authorized").exists())

    def test_document_and_config_commands_are_data_only(self):
        marker = self.base / "executed.txt"
        payload = f"__import__('pathlib').Path({str(marker)!r}).write_text('bad')"
        (self.root / "剧本.md").write_text(payload, encoding="utf-8")
        self.config["constraints"] = [payload]
        self.save_config()
        with patch.object(pipeline.subprocess, "run", side_effect=AssertionError("Unexpected process execution")):
            self.assertEqual(self.snapshot()[0], 0)
        self.assertFalse(marker.exists())
        self.assertIn(payload, (self.base / "packet" / "handoff.md").read_text(encoding="utf-8"))

    def test_inspection_media_hash_drift_detected_in_packet(self):
        self.snapshot()
        args = self.media_args(name="packet/inspections/v1", decode=True)
        with patch.object(pipeline, "find_tool", return_value="fake-tool"), patch.object(pipeline.subprocess, "run", side_effect=[self.successful_probe(), subprocess.CompletedProcess([], 0, "", "")]):
            self.assertEqual(self.run_cli(*args)[0], 0)
        (self.base / "动画.mp4").write_bytes(b"different media")
        code, result = self.run_cli("status", "--packet", str(self.base / "packet"))
        self.assertEqual(code, 2)
        self.assertEqual(result["media_inspections"][0]["status"], "changed")


if __name__ == "__main__":
    unittest.main()
