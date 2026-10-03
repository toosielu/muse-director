from pathlib import Path
import sys
import unittest
import csv
import json
import re
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from check_package import check
from lint_shot import lint


class PackageTests(unittest.TestCase):
    def healing_inputs(self):
        text=(Path(__file__).resolve().parents[2]/"examples/healing-test.md").read_text(encoding="utf-8")
        return re.findall(r"## T\d+ 模型输入[^\n]*\n\n```text\n(.*?)\n```",text,re.S)

    def lint_healing(self,body):
        style=re.search(r"^风格：(.*)$",body,re.M).group(1)
        meta={"mode":"test","cards":[],"subject_count":1,"text_only":True,"references":[],"style_prefix":style,"prompt_budget_seconds":10,"usable_window":[0,8],"required_event":"本条原地动作真实发生"}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"shot.md"
            path.write_text("### 制作任务\n```json\n"+json.dumps(meta,ensure_ascii=False)+"\n```\n### 模型输入（原样转交）\n"+body,encoding="utf-8")
            return lint(path,[])

    def test_three_published_healing_inputs_pass_and_only_action_differs(self):
        bodies=self.healing_inputs()
        self.assertEqual(len(bodies),3)
        frozen=[re.sub(r"^2–5秒：.*$","2–5秒：动作变量",body,flags=re.M) for body in bodies]
        self.assertEqual(len(set(frozen)),1)
        for body in bodies:
            self.assertEqual(self.lint_healing(body)["status"],"text_checked")

    def test_healing_count_conflict_cannot_hide_behind_subject_line(self):
        body=self.healing_inputs()[0]
        report=self.lint_healing("主体数：1\n"+body.replace("恰好1个角色","恰好2个角色"))
        self.assertTrue(any(row["code"]=="subject_count" and row["status"]=="FAIL" for row in report["findings"]))

    def test_muse_and_human_scores_have_separate_csv_columns(self):
        path=Path(__file__).resolve().parents[1]/"test-log.csv"
        with path.open(encoding="utf-8",newline="") as source:
            header=next(csv.reader(source))
        self.assertEqual(len(header),len(set(header)))
        for prefix in ("muse_h","human_h"):
            self.assertTrue(all(prefix+str(i) in header for i in range(1,7)))
        self.assertTrue({"h3_na_adoption","score_coverage","muse_score_coverage","human_score_coverage","continuity_status"}.issubset(header))

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
