from pathlib import Path
import copy
import sys
import unittest
from unittest.mock import patch
import json
import tempfile
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from u0_check import evaluate_probe, validate_targets, inspect


class U0Tests(unittest.TestCase):
    def setUp(self):
        self.probe = {"streams":[{"codec_type":"video","width":720,"height":1280,"sample_aspect_ratio":"1:1","display_aspect_ratio":"9:16","duration":"10.0","avg_frame_rate":"24/1"}]}
        self.targets = {"target_aspect":9/16,"min_seconds":6,"max_seconds":10,"min_short_side":720}

    def check(self, cut_times=None):
        return evaluate_probe(self.probe, cut_times=[] if cut_times is None else cut_times, **self.targets)

    def test_good_specs_do_not_claim_story_or_audio(self):
        report=self.check()
        self.assertEqual(report["status"],"PASS")
        self.assertEqual(report["content_review"],"UNVERIFIED")
        self.assertEqual(report["audio_review"],"UNVERIFIED")

    def test_wrong_display_ratio_fails(self):
        self.probe["streams"][0]["display_aspect_ratio"]="2:3"
        self.assertEqual(self.check()["status"],"FAIL")

    def test_stream_duration_not_container_or_audio_duration(self):
        self.probe["streams"][0]["duration"]="4"
        self.probe["format"]={"duration":"10"}
        self.probe["streams"].append({"codec_type":"audio","duration":"10"})
        self.assertEqual(self.check()["status"],"FAIL")
        self.probe["streams"][0].pop("duration")
        self.assertEqual(self.check()["status"],"UNVERIFIED")

    def test_low_short_side_warns_not_pass_or_fail(self):
        self.probe["streams"][0].update(width=360,height=640)
        self.assertEqual(self.check()["status"],"WARN")

    def test_scene_change_only_warns_possible_cut(self):
        report=self.check([4.2])
        self.assertEqual(report["status"],"WARN")
        self.assertIn("flashes",report["findings"][0]["detail"])

    def test_missing_scene_scan_is_unverified(self):
        self.assertEqual(evaluate_probe(self.probe,**self.targets)["status"],"UNVERIFIED")

    def test_rotation_uses_display_ratio(self):
        self.probe["streams"][0].update(width=1280,height=720,display_aspect_ratio="16:9",side_data_list=[{"rotation":90}])
        self.assertEqual(self.check()["status"],"PASS")

    def test_non_square_pixel_ratio_is_used(self):
        self.probe["streams"][0].pop("display_aspect_ratio")
        self.probe["streams"][0]["sample_aspect_ratio"]="2:1"
        self.assertEqual(self.check()["status"],"FAIL")

    def test_unknown_aspect_not_assumed_square(self):
        self.probe["streams"][0].pop("display_aspect_ratio")
        self.probe["streams"][0].pop("sample_aspect_ratio")
        self.assertEqual(self.check()["status"],"UNVERIFIED")

    def test_multiple_video_not_arbitrarily_selected(self):
        self.probe["streams"].append(copy.deepcopy(self.probe["streams"][0]))
        self.assertEqual(self.check()["status"],"UNVERIFIED")

    def test_cover_image_not_counted_as_playable_video(self):
        self.probe["streams"].append({"codec_type":"video","disposition":{"attached_pic":1}})
        self.assertEqual(self.check()["status"],"PASS")

    def test_no_video_fails(self):
        self.probe["streams"]=[{"codec_type":"audio"}]
        self.assertEqual(self.check()["status"],"FAIL")

    def test_invalid_thresholds_rejected(self):
        for value in (float("nan"),float("inf"),-1,0):
            with self.assertRaises(ValueError):
                validate_targets(target_aspect=value)
        with self.assertRaises(ValueError):
            validate_targets(min_seconds=10,max_seconds=6)

    def test_scan_uses_playable_stream_after_cover_and_adopted_threshold(self):
        self.probe["streams"][0]["index"]=2
        self.probe["streams"].insert(0,{"index":0,"codec_type":"video","disposition":{"attached_pic":1}})
        results=[SimpleNamespace(returncode=0,stdout=json.dumps(self.probe),stderr=""),SimpleNamespace(returncode=0,stdout="",stderr="pts_time:1.0")]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"candidate.mp4"
            path.write_bytes(b"synthetic fixture, subprocess mocked")
            with patch("u0_check.shutil.which",side_effect=lambda name:name),patch("u0_check.subprocess.run",side_effect=results) as run:
                report=inspect(path,scene_threshold=0.42,**self.targets)
                command=run.call_args_list[1].args[0]
                self.assertEqual(command[command.index("-map")+1],"0:2")
                self.assertIn("0.42",command[command.index("-vf")+1])
                self.assertEqual(report["status"],"WARN")

if __name__ == "__main__":
    unittest.main()
