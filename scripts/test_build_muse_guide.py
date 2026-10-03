from pathlib import Path
import tempfile
import unittest
from build_muse_guide import render_guide, SOURCES, independent_markdown


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


if __name__ == "__main__":
    unittest.main()
