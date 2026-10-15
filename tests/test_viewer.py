"""普通临时目录验证本地源码、相邻差异与真实转录的安全呈现。"""

import hashlib
import html
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_viewer", ROOT / "build_viewer.py")
viewer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(viewer)


class ViewerTests(unittest.TestCase):
    def fixture(self, root):
        (root / "web").mkdir()
        stages = json.loads((ROOT / "web/stages.json").read_text(encoding="utf-8"))
        stages[0]["ability"] = '<img src=x onerror="alert(1)">'
        metadata = root / "web/stages.json"
        metadata.write_text(json.dumps(stages), encoding="utf-8")
        for index in range(6):
            (root / f"agent_v{index}.py").write_text(f'print("local-{index}")\n', encoding="utf-8")
        (root / "recordings").mkdir()
        record = {
            "kind": "live-program-recording", "stage": "v0",
            "recorded_at": "2026-10-15T00:00:00Z", "model_requested": "requested-model",
            "transcript": '<script>THIS IS A RECORDING</script>',
            "inputs": ['<question>saved user input</question>'],
            "source_file": "agent_v0.py",
            "source_sha256": hashlib.sha256((root / "agent_v0.py").read_bytes()).hexdigest(),
        }
        (root / "recordings/v0.json").write_text(json.dumps(record), encoding="utf-8")
        return stages, metadata, record

    def test_replacements_are_both_added_and_removed(self):
        added, removed, highlights = viewer.line_changes("same\nold\n", "same\nnew\nmore\n")
        self.assertEqual((added, removed), (2, 1))
        self.assertEqual(highlights, {2: "modified", 3: "modified"})

    def test_source_and_diff_are_escaped(self):
        payload = '</code><script>alert("x")</script>'
        for output in (viewer.render_code(payload, {}), viewer.render_diff("", payload, "old", "new")):
            self.assertNotIn("<script>", output)
            self.assertIn("&lt;script&gt;", output)

    def test_build_reads_plain_files_and_saved_stdout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stages, metadata, record = self.fixture(root)
            page = viewer.build(root, metadata, root / "web/index.html").read_text(encoding="utf-8")
            self.assertFalse((root / ".git").exists())
            self.assertEqual(page.count('class="stage"'), 6)
            self.assertEqual(page.count('class="copy-command"'), 6)
            self.assertEqual(page.count('REPLAY · 已保存输出'), 6)
            self.assertIn("local-0", page)
            self.assertIn("local-5", page)
            self.assertIn("--- agent_v0.py", page)
            self.assertIn("+++ agent_v1.py", page)
            self.assertIn(record["source_sha256"][:12], page)
            self.assertIn("SHA-256", page)
            self.assertIn('&lt;script&gt;THIS IS A RECORDING&lt;/script&gt;', page)
            self.assertIn('&lt;img src=x', page)
            self.assertNotIn('<img src=x', page)
            self.assertIn('尚无当前源码的真实运行记录', page)
            self.assertIn('请求模型：requested-model', page)
            self.assertIn('真实程序交互录制', page)
            self.assertIn('原始程序输出转录', page)
            self.assertIn('彩排输入 · 保存的输入列表', page)
            self.assertIn('&lt;question&gt;saved user input&lt;/question&gt;', page)
            self.assertNotIn('<question>', page)
            terminal = page.split('<pre class="terminal">', 1)[1].split('</pre>', 1)[0]
            self.assertEqual(html.unescape(terminal), record["transcript"])
            self.assertNotIn('历史记录：此输出不对应当前展示的源码', page)
            self.assertNotIn('API 返回模型', page)
            for index in range(6):
                self.assertIn(f'python agent_v{index}.py</code>', page)
                self.assertIn(f'data-stage="v{index}"', page)
            for removed in ('git switch', 'Git tag', 'commit', 'source_commit', 'file-selector', 'run_stage.py', ':quit', ':reset'):
                self.assertNotIn(removed, page)
            self.assertIn('直接进入自由交互', page)
            self.assertIn('Ctrl+D', page)
            self.assertIn('Pr[token | context]', page)
            self.assertIn('navigator.clipboard.writeText(command)', page)
            self.assertIn('命令已选中，请手动复制', page)
            self.assertIn('python chat_template_demo.py', page)
            self.assertIn('代码字号', page)
            self.assertNotIn('innerHTML', page)
            self.assertNotIn('https://', page)

    def test_source_changes_mark_recording_as_historical(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stages, metadata, record = self.fixture(root)
            (root / "agent_v0.py").write_text('print("changed")\n', encoding="utf-8")
            page = viewer.build(root, metadata, root / "web/index.html").read_text(encoding="utf-8")
            self.assertIn('print(&quot;changed&quot;)', page)
            self.assertIn('历史记录：此输出不对应当前展示的源码', page)

    def test_unsupported_recording_kind_or_stage_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stages, metadata, record = self.fixture(root)
            path = root / "recordings/v0.json"
            for field, value, expected in (("kind", "old-format", "类型不匹配"),
                                           ("stage", "v1", "阶段不匹配"),
                                           ("transcript", [], "stdout 转录")):
                with self.subTest(field=field):
                    path.write_text(json.dumps({**record, field: value}), encoding="utf-8")
                    with self.assertRaisesRegex(viewer.BuildError, expected):
                        viewer.build(root, metadata, root / "web/index.html")

    def test_missing_source_and_invalid_metadata_fail_clearly(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stages, metadata, record = self.fixture(root)
            (root / "agent_v5.py").unlink()
            with self.assertRaisesRegex(viewer.BuildError, "agent_v5.py"):
                viewer.load_versions(root, stages)
            stages[0]["file"] = "../outside.py"
            metadata.write_text(json.dumps(stages), encoding="utf-8")
            with self.assertRaisesRegex(viewer.BuildError, "阶段源码文件"):
                viewer.read_stages(metadata)
            metadata.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(viewer.BuildError, "六个阶段"):
                viewer.read_stages(metadata)


if __name__ == "__main__":
    unittest.main()
