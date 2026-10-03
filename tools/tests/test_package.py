from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from check_package import check


class PackageTests(unittest.TestCase):
    def test_canonical_structure_and_links(self):
        report=check(Path(__file__).resolve().parents[2])
        self.assertEqual(report["status"],"PASS",report["errors"])

    def test_detailed_example_repeats_user_blocks_in_each_shot(self):
        text=(Path(__file__).resolve().parents[2]/"examples/prompt-merge.md").read_text(encoding="utf-8")
        section=text.split("## 三镜完整输入",1)[1].split("## 差异与回传",1)[0]
        for phrase in ("阿琪，短黑发，蓝色校服外套，白色帆布鞋。", "16:9，台湾青春剧质感，阴天柔光，浅景深。", "校门外的石板路，右侧一辆红色自行车。", "无字幕、无水印。", "全片保留轻钢琴音乐和中文台词。"):
            self.assertEqual(section.count(phrase),3)

if __name__ == "__main__":
    unittest.main()
