"""真实临时 Git 仓库验证 tags、差异和静态输出的安全转义。"""

import importlib.util
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_viewer", ROOT / "build_viewer.py")
viewer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(viewer)


class ViewerTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("DUMMY_AGENT_STAGE_REFS", None)

    def test_replacements_are_both_added_and_removed(self):
        added, removed, highlights = viewer.line_changes("same\nold\n", "same\nnew\nmore\n")
        self.assertEqual((added, removed), (2, 1))
        self.assertEqual(highlights, {2: "modified", 3: "modified"})

    def test_rendered_text_is_escaped(self):
        payload = '</code><script>alert("x")</script>'
        output = viewer.render_code(payload, {})
        self.assertNotIn("<script>", output)
        self.assertIn("&lt;script&gt;", output)
        diff = viewer.render_diff("", payload, "old", "new")
        self.assertNotIn("<script>", diff)

    def test_build_reads_tagged_code_and_saved_output(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            def git(*args):
                return subprocess.run(
                    ["git", "-C", str(repo), *args], check=True,
                    capture_output=True, text=True,
                ).stdout

            git("init", "-q")
            git("config", "user.name", "Viewer Test")
            git("config", "user.email", "viewer@example.invalid")
            (repo / "web").mkdir()
            stages = json.loads((ROOT / "web" / "stages.json").read_text(encoding="utf-8"))
            stages[0]["ability"] = '<img src=x onerror="alert(1)">'
            metadata = repo / "web" / "stages.json"
            metadata.write_text(json.dumps(stages), encoding="utf-8")
            with self.assertRaisesRegex(viewer.BuildError, "缺少 Git tags"):
                viewer.load_versions(repo, stages)
            for index, tag in enumerate(viewer.TAGS):
                (repo / "agent.py").write_text(f'print("tagged-{index}")\n', encoding="utf-8")
                if index == 2:
                    (repo / "chat_template_demo.py").write_text('print("template")\n', encoding="utf-8")
                    (repo / "data").mkdir()
                    (repo / "data" / "deepseek_v3_chat_template.jinja").write_text(
                        '{{ "<｜User｜>" + message }}', encoding="utf-8")
                if index == 3:
                    (repo / "tools.py").write_text("def tool():\n    return 42\n", encoding="utf-8")
                if index == 5:
                    (repo / "tools.py").unlink()
                git("add", "-A")
                git("commit", "-qm", f"Stage {index}")
                git("tag", tag)
            (repo / "agent.py").write_text("WORKING TREE MUST NOT APPEAR\n", encoding="utf-8")
            (repo / "recordings").mkdir()
            (repo / "recordings" / "v0-token.json").write_text(json.dumps({
                "kind": "live-api-recording", "stage": "v0-token",
                "recorded_at": "2026-10-15T00:00:00Z", "model_requested": "requested-model",
                "transcript": '<script>THIS IS A RECORDING</script>',
                "source_sha256": hashlib.sha256(b'print("tagged-0")\n').hexdigest(),
                "events": [{"response": {"model": "returned-model"}}],
            }), encoding="utf-8")
            output = viewer.build(repo, metadata, repo / "web" / "index.html")
            page = output.read_text(encoding="utf-8")
            self.assertEqual(page.count('class="stage"'), 6)
            self.assertIn('tagged-0', page)
            self.assertIn('tagged-5', page)
            self.assertNotIn('WORKING TREE MUST NOT APPEAR', page)
            self.assertIn(git("rev-parse", "v2-chat").strip()[:12], page)
            self.assertIn('&lt;script&gt;THIS IS A RECORDING&lt;/script&gt;', page)
            self.assertIn('&lt;img src=x', page)
            self.assertNotIn('<img src=x', page)
            self.assertIn('这个版本中没有此文件', page)
            self.assertIn('尚无当前源码的真实运行记录', page)
            self.assertIn('请求模型：requested-model', page)
            self.assertIn('API 返回模型：returned-model', page)
            self.assertIn('真实 API 调用录制', page)
            self.assertEqual(page.count('class="copy-command"'), 6)
            self.assertEqual(page.count('REPLAY · 已保存输出'), 6)
            self.assertIn('white-space:pre-wrap', page)
            for tag in viewer.TAGS:
                self.assertIn(f'git switch --detach {tag}\npython agent.py</code>', page)
            self.assertIn('直接进入自由交互', page)
            self.assertIn('Ctrl+D', page)
            for removed in ('run_stage.py', 'common.py', 'sandbox.py', 'lab.py', '--demo', ':quit', ':reset'):
                self.assertNotIn(removed, page)
            self.assertIn('Pr[token | context]', page)
            self.assertIn('navigator.clipboard.writeText(command)', page)
            self.assertIn('命令已选中，请手动复制', page)
            self.assertIn('python chat_template_demo.py', page)
            self.assertNotIn('data/deepseek_v3_chat_template.jinja', page)
            self.assertNotIn('innerHTML', page)
            self.assertNotIn('https://', page)

            # A candidate is a real committed ref; public tags and worktree files remain distinct.
            git("add", "agent.py")
            git("commit", "-qm", "Candidate fixture")
            candidate = git("rev-parse", "HEAD").strip()
            with patch.dict(os.environ, {"DUMMY_AGENT_STAGE_REFS": json.dumps({"v0-token": candidate})}):
                candidate_page = viewer.build(repo, metadata, repo / "web/candidate.html").read_text()
            self.assertIn('WORKING TREE MUST NOT APPEAR', candidate_page)
            self.assertIn('历史记录：此输出不对应当前展示的源码', candidate_page)
            self.assertIn('tagged-0', git("show", "v0-token:agent.py"))

    def test_invalid_candidate_refs_are_rejected(self):
        for mapping in ('not-json', '[]', '{"unknown":"HEAD"}', '{"v0-token":3}'):
            with self.subTest(mapping=mapping), patch.dict(os.environ, {"DUMMY_AGENT_STAGE_REFS": mapping}):
                with self.assertRaises(viewer.BuildError):
                    viewer.load_versions(ROOT, [])


if __name__ == "__main__":
    unittest.main()
