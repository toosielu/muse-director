from pathlib import Path
import tempfile
import unittest
from build_muse_guide import render_guide, render_compact, SOURCES, independent_markdown


class GuideBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in SOURCES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('{"fixture":true}' if name.endswith(".json") else "# 测试\n[本地说明](other.md)与[公开来源](https://example.com)", encoding="utf-8")

    def test_reproducible_and_independent(self):
        guide = render_guide(self.root)
        self.assertEqual(guide, render_guide(self.root))
        self.assertNotIn("](other.md)", guide)
        self.assertIn("https://example.com", guide)

    def test_source_changes_guide_and_manifest(self):
        before = render_guide(self.root)
        (self.root / SOURCES[0]).write_text("# 新的委托规则", encoding="utf-8")
        self.assertNotEqual(before, render_guide(self.root))

    def test_recovery_reference_is_embedded_and_versioned(self):
        recovery = self.root / "references/rejection-diagnostics.md"
        recovery.write_text("# 拒收诊断与有限恢复\n唯一恢复记录", encoding="utf-8")
        before = render_guide(self.root)
        self.assertIn("## 拒收诊断与有限恢复\n唯一恢复记录", before)
        self.assertIn('"references/rejection-diagnostics.md":', before)
        recovery.write_text("# 拒收诊断与有限恢复\n已更新恢复记录", encoding="utf-8")
        self.assertNotEqual(before, render_guide(self.root))

    def test_missing_source_is_an_error(self):
        (self.root / SOURCES[0]).unlink()
        with self.assertRaises(OSError):
            render_guide(self.root)

    def test_local_links_removed_public_links_preserved(self):
        self.assertEqual(independent_markdown("[内部](#检查) [来源](https://example.com)"), "内部 [来源](https://example.com)")

    def test_excluded_reference_routes_to_embedded_instruction(self):
        converted = independent_markdown("见[审查覆盖](workflow.md#审查覆盖)和[对照实验](comparison-experiments.md)")
        self.assertIn("有限质量检查与结束条件", converted)
        self.assertIn("受限对照试验", converted)
        self.assertNotIn("审查覆盖", converted)
        self.assertIn("## 受限对照试验", render_guide(self.root))

    def test_full_example_claim_is_not_redirected_to_short_example(self):
        text = "完整交接与返修演示见 [制作与返修示例](worked-example.md)。"
        converted = independent_markdown(text)
        self.assertNotIn("完整交接与返修演示", converted)
        self.assertIn("上例只说明镜头设计", converted)
        self.assertIn("镜头检查与返修记录", converted)

    def test_compact_is_generated_from_same_source(self):
        path = self.root / "references/execution-modes.md"
        path.write_text("# 范围\n## 标准委托入口\n一条实际规则\n## 其他\n不进入快速版", encoding="utf-8")
        quick = render_compact(self.root)
        self.assertIn("一条实际规则", quick)
        self.assertNotIn("不进入快速版", quick)
        self.assertEqual(quick, render_compact(self.root))
        self.assertIn("一条实际规则", render_guide(self.root))
        path.write_text("# 范围\n## 标准委托入口\n新的规则", encoding="utf-8")
        self.assertNotEqual(quick, render_compact(self.root))

    def test_compact_missing_or_oversize_entry_fails(self):
        with self.assertRaises(ValueError):
            render_compact(self.root)
        (self.root / "references/execution-modes.md").write_text("## 标准委托入口\n" + "长" * 3000, encoding="utf-8")
        with self.assertRaises(ValueError):
            render_compact(self.root)


if __name__ == "__main__":
    unittest.main()
