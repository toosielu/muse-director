import json
from pathlib import Path
import tempfile
import unittest
from lint_shot import lint


class ShotLintTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "ref.png").write_bytes(b"fixture; presence only, not image validation")
        self.card = {"card_id":"C01", "version":"v1", "locked_text":"圆脑袋，蓝外套", "style_prefix":"9:16，二维插画", "adoption_evidence":"虚构测试：主控依据全片委托选用", "reference_images":[{"source":"ref.png", "required":True}]}
        self.meta = {"cards":[{"card_id":"C01", "version":"v1"}], "subject_count":1, "references":[{"order":1, "source":"ref.png"}], "prompt_budget_seconds":10, "usable_window":[1,7], "required_event":"把盒子推到B位"}
        self.body = "[图1：身份]\n风格：9:16，二维插画\n人物：圆脑袋，蓝外套\n主体数：1。\n场景：柜台\n起点：手贴盒子\n动作：向右推\n终点：盒子停在B\n镜头：固定中景\n声音：只有动作声\n"

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


if __name__ == "__main__":
    unittest.main()
