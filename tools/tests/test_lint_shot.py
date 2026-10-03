import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lint_shot import lint


class ShotLintTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "ref.png").write_bytes(b"fixture; presence only, not image validation")
        self.card = {"card_id":"C01", "version":"v1", "locked_text":"圆脑袋，蓝外套", "style_prefix":"9:16，二维插画", "adoption_evidence":"虚构测试：主控依据全片委托选用", "reference_images":[{"source":"ref.png", "required":True}]}
        self.meta = {"cards":[{"card_id":"C01", "version":"v1"}], "subject_count":1, "references":[{"order":1, "source":"ref.png"}], "prompt_budget_seconds":10, "usable_window":[1,7], "required_event":"把盒子推到B位"}
        self.body = "[图1：身份]\n风格：9:16，二维插画\n人物：圆脑袋，蓝外套\n主体数：1。\n场景：柜台\n起点：手贴盒子\n动作：向右推\n终点：盒子停在B\n镜头：固定中景\n声音：只有动作声\n约束：无文字、无字幕、无水印\n"

    def check(self, cap=None):
        card = self.root / "card.json"
        card.write_text(json.dumps(self.card, ensure_ascii=False), encoding="utf-8")
        shot = self.root / "shot.md"
        shot.write_text("### 制作任务\n```json\n" + json.dumps(self.meta, ensure_ascii=False) + "\n```\n### 模型输入（原样转交）\n" + self.body + "\n### 回传\n额外管理要求", encoding="utf-8")
        return lint(shot, [card], cap)

    def test_good_input_does_not_claim_semantics_or_upload(self):
        result = self.check()
        self.assertEqual(result["status"], "text_checked")
        self.assertEqual(result["semantic_review"], "unverified")
        self.assertEqual(result["platform_binding"], "unverified")
        self.assertNotIn("额外管理要求", result["model_input"])

    def test_identity_text_changed(self):
        self.body = self.body.replace("蓝外套", "红外套")
        self.assertTrue(any(row["code"] == "locked_text" for row in self.check()["findings"]))

    def test_stale_card_version(self):
        self.meta["cards"][0]["version"] = "v2"
        self.assertEqual(self.check()["status"], "needs_fix")

    def test_reference_number_mismatch(self):
        self.body = self.body.replace("图1", "图2")
        self.assertEqual(self.check()["status"], "needs_fix")

    def test_missing_required_image(self):
        (self.root / "ref.png").unlink()
        self.assertEqual(self.check()["status"], "needs_fix")

    def test_remote_handle_is_not_automatically_verified(self):
        self.meta["references"][0]["source"] = "media_handle:fixture"
        self.card["reference_images"][0]["source"] = "media_handle:fixture"
        result = self.check()
        self.assertEqual(result["status"], "text_checked")
        self.assertTrue(any(row["code"] == "reference_access" for row in result["findings"]))

    def test_target_window_exceeds_capacity(self):
        self.meta["usable_window"] = [0,11]
        self.assertEqual(self.check()["status"], "needs_fix")

    def test_project_capacity_limit(self):
        self.assertEqual(self.check(8)["status"], "needs_fix")

    def test_unselected_template(self):
        self.card["adoption_evidence"] = None
        self.assertEqual(self.check()["status"], "needs_fix")

    def test_text_only_does_not_bypass_adopted_image(self):
        self.meta.update(text_only=True, references=[])
        self.body = self.body.replace("[图1：身份]\n", "")
        self.assertEqual(self.check()["status"], "needs_fix")
        self.card["reference_images"] = []
        self.assertEqual(self.check()["status"], "text_checked")

    def test_timed_actions_are_valid_but_gaps_and_overflow_are_not(self):
        self.body = self.body.replace("起点：手贴盒子\n动作：向右推\n终点：盒子停在B", "0–2秒：手贴盒子\n2–5秒：向右推\n5–8秒：松手停在B")
        self.assertEqual(self.check()["status"], "text_checked")
        self.body = self.body.replace("2–5秒", "3–5秒")
        self.assertEqual(self.check()["status"], "needs_fix")
        self.body = self.body.replace("3–5秒", "2–5秒").replace("5–8秒", "5–11秒")
        self.assertEqual(self.check()["status"], "needs_fix")

    def test_explicit_sound_policy_with_negation(self):
        self.meta.update(allow_music=False, allow_dialogue=False)
        self.body = self.body.replace("只有动作声", "轻背景音乐和旁白")
        self.assertEqual(self.check()["status"], "needs_fix")
        self.body = self.body.replace("轻背景音乐和旁白", "无背景音乐，无旁白，只有动作声")
        self.assertEqual(self.check()["status"], "text_checked")

    def test_adopted_constraints_and_camera_override(self):
        self.card["constraint_block"] = "无水印"
        self.meta["policies"] = {"max_camera_moves": 1, "required_literals": ["无字幕"]}
        self.body += "约束：无水印，无字幕\n"
        self.assertEqual(self.check()["status"], "text_checked")
        self.body = self.body.replace("固定中景", "推镜然后环绕")
        self.assertEqual(self.check()["status"], "needs_fix")
        self.meta["policies"]["max_camera_moves"] = 2
        self.assertEqual(self.check()["status"], "text_checked")

    def test_pure_text_test_prompt_must_pass(self):
        self.meta.update(mode="test", cards=[], subject_count=0, references=[], text_only=True, style_prefix="9:16，二维插画")
        self.body = self.body.replace("[图1：身份]\n", "").replace("主体数：1", "主体数：0").replace("人物：圆脑袋，蓝外套\n", "")
        self.body = self.body.replace("起点：手贴盒子\n动作：向右推\n终点：盒子停在B", "0–2秒：蓝盒停在柜台A\n2–5秒：蓝盒移向B\n5–8秒：蓝盒停在B")
        path = self.root / "test.md"
        path.write_text("### 制作任务\n```json\n" + json.dumps(self.meta) + "\n```\n### 模型输入（原样转交）\n" + self.body, encoding="utf-8")
        self.assertEqual(lint(path, [])["status"], "text_checked")

    def test_deliberately_corrupted_prompt_must_fail(self):
        self.meta["prompt_budget_seconds"] = 15
        self.body = self.body.replace("约束：无文字、无字幕、无水印\n", "").replace("固定中景", "推镜然后环绕再拉远").replace("只有动作声", "音乐配乐、旁白与台词")
        self.body += "请用下面的提示词，原样使用，贴给我。\n"
        report = self.check()
        self.assertEqual(report["status"], "needs_fix")
        codes = {row["code"] for row in report["findings"] if row["status"] == "FAIL"}
        self.assertTrue({"planning_capacity", "project_policy", "sound_policy", "camera_policy", "management_in_model_input"}.issubset(codes))

    def test_detailed_mode_keeps_original_blocks_and_user_choices(self):
        self.meta.update(mode="detailed", allow_music=True, allow_dialogue=True, frozen_blocks={"character":"圆脑袋，蓝外套", "style":"9:16，二维插画", "constraint":"无字幕、无水印"}, policies={"max_camera_moves":2})
        self.body = self.body.replace("无文字、无字幕、无水印", "无字幕、无水印").replace("固定中景", "推镜然后环绕").replace("只有动作声", "钢琴音乐和中文台词")
        self.assertEqual(self.check()["status"], "text_checked")
        self.body = self.body.replace("蓝外套", "红外套")
        self.assertTrue(any(row["code"] == "original_blocks" and row["status"] == "FAIL" for row in self.check()["findings"]))

    def test_visual_negation_warn_does_not_strip_user_constraint(self):
        self.body = self.body.replace("向右推", "向右推，不要转头")
        report = self.check()
        self.assertEqual(report["status"], "text_checked")
        self.assertTrue(any(row["code"] == "visual_negation" for row in report["findings"]))
        self.assertIn("不要转头", report["model_input"])

    def test_embedded_project_limit(self):
        self.meta["planning_limit_seconds"] = 8
        self.assertEqual(self.check()["status"], "needs_fix")
        self.meta["planning_limit_seconds"] = float("nan")
        self.assertEqual(self.check()["status"], "needs_fix")

    def test_establishing_shot_without_fake_character_card(self):
        self.meta.update(cards=[], subject_count=0, references=[], text_only=True, style_prefix="9:16，二维插画")
        shot = self.root / "empty-scene.md"
        body = self.body.replace("[图1：身份]\n", "").replace("主体数：1", "主体数：0").replace("人物：圆脑袋，蓝外套\n", "")
        shot.write_text("### 制作任务\n```json\n" + json.dumps(self.meta) + "\n```\n### 模型输入（原样转交）\n" + body, encoding="utf-8")
        self.assertEqual(lint(shot, [])["status"], "text_checked")

    def test_guide_heading_level_does_not_leak_management_section(self):
        self.check()
        shot = self.root / "shot.md"
        shot.write_text(shot.read_text(encoding="utf-8").replace("### ", "#### "), encoding="utf-8")
        result = lint(shot, [self.root / "card.json"])
        self.assertEqual(result["status"], "text_checked")
        self.assertNotIn("额外管理要求", result["model_input"])
        self.assertNotIn("#### 回传", result["model_input"])


if __name__ == "__main__":
    unittest.main()
