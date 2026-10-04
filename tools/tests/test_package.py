from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_package import check

ROOT = Path(__file__).resolve().parents[2]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class PackageTests(unittest.TestCase):
    def test_package_passes(self):
        report = check(ROOT)
        self.assertEqual(report["status"], "PASS", report["errors"])

    def test_audit_jargon_in_guide_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder) / "pkg"
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git"))
            guide = copy / "muse-idea-to-short.md"
            guide.write_text(guide.read_text(encoding="utf-8") + "\n默认3+2，待测。\n", encoding="utf-8")
            report = check(copy)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any("3+2" in e for e in report["errors"]))

    def test_guide_length_is_reported_without_a_hard_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder) / "pkg"
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git"))
            guide = copy / "muse-idea-to-short.md"
            guide.write_text(guide.read_text(encoding="utf-8") + "\n" + "长" * 4100, encoding="utf-8")
            report = check(copy)
        self.assertGreater(report["lengths"]["muse-idea-to-short.md"], 4000)
        self.assertFalse(any("muse-idea-to-short.md:" in e and "characters" in e for e in report["errors"]))

    def test_detailed_example_keeps_user_wording(self):
        text = read("examples/detailed-prompt.md")
        original = text.split("## 用户给的15秒提示词", 1)[1].split("## 第一步", 1)[0]
        final = text.split("## 第2镜最终提示词", 1)[1]
        for phrase in ("16:9，台湾青春剧质感，阴天柔光，浅景深。", "阿琪，短黑发，蓝色校服外套，白色帆布鞋。",
                       "校门外的石板路，右侧一辆红色自行车。", "她右手握住车把，侧头看向左边，喊“等我一下”。"):
            self.assertIn(phrase, original)
            self.assertIn(phrase, final)

    def test_one_line_example_prompt_starts_with_anchors(self):
        text = read("examples/one-line.md")
        anchor = re.search(r"（英文固定版）(.*)", text).group(1).strip()
        section = text.split("## 第2镜怎么生成", 1)[1].split("## 为什么这样拆", 1)[0]
        first_frame, video = re.findall(r"```\n(.*?)```", section, re.S)
        self.assertIn("9:16", first_frame)
        for prompt in (first_frame, video):
            self.assertIn(anchor, prompt)

    def test_dialogue_example_has_one_speaker_per_shot(self):
        text = read("examples/dialogue-scene.md")
        rows = [line for line in text.splitlines() if re.match(r"^\|\d+\|", line)]
        self.assertGreaterEqual(len(rows), 4)
        for row in rows:
            self.assertLessEqual(row.count("：“"), 1, row)
            self.assertNotIn("配音", row)

    def test_next_round_test_documents_are_packaged(self):
        for name in ("testing/multi-reference.md", "testing/scene-continuity.md",
                     "testing/scene-continuity-results-2026-10-05.md"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                copy = Path(folder) / "pkg"
                shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git"))
                (copy / name).unlink()
                report = check(copy)
                self.assertIn("missing: " + name, report["errors"])

    def test_scene_followup_keeps_fixed_prompt_and_user_audio_verbatim(self):
        text=read("testing/scene-continuity.md")
        script=re.search(r"```text\n(.*?)```",text,re.S).group(1)
        prefix=[
            "国风手绘二维动画，线条干净，平涂上色，柔和光影，横屏16:9。",
            "白衣师姐，二十岁左右的女子，乌黑长发束成高马尾，系红色发带，穿象牙白宽袖长衣，系浅灰腰带。",
            "青衣师弟，十五岁左右的少年，比师姐矮半个头，黑色短发在头顶束成一个小髻，穿青绿色短打衣裤，系深棕腰带。",
            "剑，一柄细长直剑，始终插在黑色剑鞘里，剑柄缠着红绳。",
            "竹林小院，白天柔光。镜头从院子正面拍：画面左边是白墙上的圆形月洞门，右边是一张圆石桌和两个石凳，桌上放一只青瓷茶壶，左上角屋檐下挂一盏红灯笼，背后是一排绿竹。",
        ]
        suffix=[
            "镜头：全景，固定机位。",
            "声音：竹叶沙沙声和鸟叫，没有音乐，没有人声。",
            "约束：无文字、无字幕、无水印。画面里只有这两个人。剑始终插在鞘里，不拔剑，不打斗。",
        ]
        pattern=re.escape("\n".join(prefix))+r"\n道具：[^\n]+\n动作：[^\n]+\n"+re.escape("\n".join(suffix))
        self.assertEqual(len(re.findall(pattern,script)),2)

    def test_draft_topics_are_not_default_genres(self):
        for name in ("beauty-oncamera.md", "guofeng-live.md"):
            self.assertFalse((ROOT / "genres" / name).exists())
            self.assertTrue((ROOT / "drafts" / name).is_file())

    def test_draft_content_is_not_checked_as_a_main_rule(self):
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder) / "pkg"
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git"))
            draft = copy / "drafts/beauty-oncamera.md"
            draft.write_text(draft.read_text(encoding="utf-8") + "\n待测 U0\n" + "长" * 1600, encoding="utf-8")
            report = check(copy)
        self.assertFalse(any("drafts/beauty-oncamera.md:" in e or "audit jargon in drafts/" in e for e in report["errors"]))

    def test_capability_round_four_is_not_double_counted(self):
        text = read("examples/case-2026-10-04-capability-test.md")
        self.assertEqual(len(re.findall(r"^## 第四轮：", text, re.M)), 1)
        round_four = text.split("## 第四轮：", 1)[1].split("## 下一轮要测", 1)[0]
        self.assertIn("原输入也写了9:16", round_four)
        self.assertIn("只记这一次", round_four)

    def test_real_run_case_keeps_observed_failures(self):
        text = read("examples/case-2026-10-03-healing-45s.md")
        for phrase in ("45", "960", "萤火虫", "室内", "星星", "定妆图"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
