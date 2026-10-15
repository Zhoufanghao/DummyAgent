#!/usr/bin/env python3
"""从真实 Git tags 构建可直接打开的静态教学网页（仅使用标准库）。"""

import argparse
import difflib
import hashlib
import html
import json
import os
import subprocess
import sys
from pathlib import Path


TAGS = (
    "v0-token", "v1-memory", "v2-chat", "v3-tools",
    "v4-agent-loop", "v5-execution",
)
SOURCE_FILES = ("agent.py", "tools.py")


class BuildError(Exception):
    """让构建失败原因以简洁中文呈现。"""


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
        encoding="utf-8", timeout=30,
    )
    if result.returncode:
        raise BuildError(f"Git 命令失败：{' '.join(args)}\n{result.stderr.strip()}")
    return result.stdout


def escape(value):
    return html.escape(str(value), quote=True)


def read_stages(metadata):
    try:
        stages = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BuildError(f"不能读取阶段说明 {metadata}：{exc}") from exc
    if (not isinstance(stages, list) or not all(isinstance(s, dict) for s in stages)
            or [s.get("tag") for s in stages] != list(TAGS)):
        raise BuildError("stages.json 必须按顺序包含全部六个规定的 Git tags。")
    required = ("ref", "title", "ability", "why", "can_do", "focus", "minutes")
    if any(not isinstance(s.get(k), str) for s in stages for k in required):
        raise BuildError("每个阶段都必须包含 ref / title / ability / why / can_do / focus / minutes 文本。")
    return stages


def load_versions(repo, stages, source_files=SOURCE_FILES):
    """只读取已存在的真实 tags；不使用工作区文件补齐历史版本。"""
    try:
        refs = json.loads(os.environ.get("DUMMY_AGENT_STAGE_REFS", "{}"))
    except ValueError as exc:
        raise BuildError("DUMMY_AGENT_STAGE_REFS 必须是阶段到 Git ref 的 JSON 对象。") from exc
    if (not isinstance(refs, dict) or any(k not in TAGS or not isinstance(v, str) or not v
                                         for k, v in refs.items())):
        raise BuildError("DUMMY_AGENT_STAGE_REFS 只能指定六个教学阶段及非空 Git ref。")
    existing = set(git(repo, "tag", "--list").splitlines())
    missing = [s["ref"] for s in stages if s["ref"] not in existing and s["tag"] not in refs]
    if missing:
        raise BuildError("缺少 Git tags：" + ", ".join(missing)
                         + "。请逐阶段验证、提交并创建 tag 后再生成网页。")
    versions = []
    for stage in stages:
        tag = stage["tag"]
        ref = refs.get(tag, stage["ref"])
        paths = set(git(repo, "ls-tree", "-r", "--name-only", ref).splitlines())
        if "agent.py" not in paths:
            raise BuildError(f"{tag} 中没有 agent.py，无法展示同一程序的演进。")
        sources = {
            path: git(repo, "show", f"{ref}:{path}")
            for path in source_files if path in paths
        }
        versions.append({
            **stage, "ref": ref, "sha": git(repo, "rev-parse", f"{ref}^{{commit}}").strip(),
            "sources": sources,
        })
    return versions


def line_changes(before, after):
    """统计源码行的真实变化；替换计作删除旧行并增加新行。"""
    old, new = before.splitlines(), after.splitlines()
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    added = removed = 0
    highlights = {}
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op in ("delete", "replace"):
            removed += i2 - i1
        if op in ("insert", "replace"):
            added += j2 - j1
            for index in range(j1, j2):
                highlights[index + 1] = "modified" if op == "replace" else "added"
    return added, removed, highlights


def render_code(source, highlights):
    lines = source.splitlines()
    if not lines:
        return '<p class="empty">这个版本中没有此文件。</p>'
    output = []
    for number, line in enumerate(lines, 1):
        kind = highlights.get(number, "")
        output.append(
            f'<span class="code-line {kind}"><span class="line-number" '
            f'aria-hidden="true">{number}</span><code>{escape(line) or " "}</code></span>'
        )
    return '<pre class="source-code">' + "".join(output) + "</pre>"


def render_diff(before, after, old_label, new_label):
    diff = list(difflib.unified_diff(
        before.splitlines(), after.splitlines(), fromfile=old_label,
        tofile=new_label, lineterm="", n=3,
    ))
    if not diff:
        return '<p class="empty">与上一阶段相比，这个文件没有变化。</p>'
    output = []
    for line in diff:
        if line.startswith(("--- ", "+++ ")):
            kind = "diff-header"
        elif line.startswith("@@"):
            kind = "diff-range"
        elif line.startswith("+"):
            kind = "added"
        elif line.startswith("-"):
            kind = "removed"
        else:
            kind = ""
        output.append(f'<span class="diff-line {kind}">{escape(line) or " "}</span>')
    return '<pre class="diff-code">' + "".join(output) + "</pre>"


def recording_text(data):
    """兼容纯 transcript 和常见事件列表；未识别的结构不伪造成运行结果。"""
    if isinstance(data, str):
        return data
    if not isinstance(data, dict):
        return ""
    for field in ("transcript", "text", "stdout"):
        value = data.get(field)
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
    events = data.get("events", [])
    if isinstance(events, list):
        texts = []
        for event in events:
            if isinstance(event, str):
                texts.append(event)
            elif isinstance(event, dict):
                for key in ("text", "message", "content", "stdout"):
                    if isinstance(event.get(key), str):
                        texts.append(event[key])
                        break
        return "\n".join(texts)
    return ""


def render_recording(repo, tag, filename=None, version=None):
    path = repo / "recordings" / (filename or f"{tag}.json")
    if not path.is_file():
        return ('<p class="empty">尚无当前源码的真实运行记录。使用教师验证工具联网验证后，'
                f'将记录保存到 <code>recordings/{escape(tag)}.json</code> 再重新构建本页。</p>')
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BuildError(f"运行记录无法读取 {path}：{exc}") from exc
    if isinstance(data, dict) and data.get("stage", tag) != tag:
        raise BuildError(f"运行记录阶段不匹配：{path} 声明的 stage 不是 {tag}。")
    transcript = recording_text(data)
    provenance = []
    if isinstance(data, dict):
        for key, label in (("recorded_at", "记录时间"), ("provider", "服务"),
                           ("model_requested", "请求模型"), ("model", "模型"),
                           ("mode", "记录模式")):
            if isinstance(data.get(key), (str, int, float)):
                provenance.append(f"{label}：{escape(data[key])}")
        returned_models = []
        events = data.get("events", [])
        for event in events if isinstance(events, list) else []:
            if not isinstance(event, dict) or not isinstance(event.get("response"), dict):
                continue
            model = event["response"].get("model")
            if isinstance(model, str) and model not in returned_models:
                returned_models.append(model)
        if returned_models:
            provenance.append("API 返回模型：" + escape(", ".join(returned_models)))
    meta = " · ".join(provenance)
    result = f'<p class="recording-meta">来源：recordings/{escape(path.name)} · 离线回放</p>'
    if version and isinstance(data, dict):
        hashes = {name: hashlib.sha256(source.encode("utf-8")).hexdigest()
                  for name, source in version["sources"].items()}
        recorded = data.get("runtime_sha256", {})
        matches = data.get("source_sha256") == hashes["agent.py"]
        if "tools.py" in hashes or recorded:
            matches = matches and isinstance(recorded, dict) and all(
                recorded.get(name) == digest for name, digest in hashes.items())
        if data.get("source_commit"):
            matches = matches and data["source_commit"] == version["sha"]
        if not matches:
            result += '<p class="recording-meta">历史记录：此输出不对应当前展示的源码。</p>'
    if isinstance(data, dict) and data.get("kind") == "live-api-recording":
        result += '<p class="recording-meta">记录类型：真实 API 调用录制；当前页面展示已保存输出。</p>'
    if meta:
        result += f'<p class="recording-meta">{meta}</p>'
    if not transcript:
        return result + '<p class="empty">记录存在，但没有可展示的 transcript / text / stdout / events 文本。</p>'
    return result + f'<pre class="terminal">{escape(transcript)}</pre>'


def render_stage(repo, stage, previous, index, source_files):
    current = stage["sources"]
    old = previous["sources"] if previous else {}
    files = [path for path in source_files if path in current or path in old]
    changes = {path: line_changes(old.get(path, ""), current.get(path, "")) for path in files}
    added = sum(change[0] for change in changes.values())
    removed = sum(change[1] for change in changes.values())
    compare = previous["tag"] if previous else "空文件（起点）"
    options = "".join(f'<option value="{escape(path)}">{escape(path)}</option>' for path in files)
    panels = []
    for file_index, path in enumerate(files):
        _, _, highlights = changes[path]
        source = render_code(current.get(path, ""), highlights)
        diff = render_diff(old.get(path, ""), current.get(path, ""),
                           f'{compare}/{path}', f'{stage["tag"]}/{path}')
        panels.append(
            f'<div class="file-panel" data-file="{escape(path)}"'
            + (" hidden" if file_index else "") + '><div class="code-columns">'
            f'<section class="code-pane"><h3>当前版本 · {escape(path)}</h3>{source}</section>'
            f'<section class="code-pane"><h3>与 {escape(compare)} 的差异</h3>{diff}</section>'
            '</div></div>'
        )
    extra = ""
    if stage["tag"] == "v2-chat":
        extra += ('<p class="page-note">公开模板辅助演示：在仓库根目录运行 '
                  '<code>python chat_template_demo.py</code>。该历史V3模板不代表当前Flash托管API内部格式。</p>')
    command = f"git switch --detach {stage['ref']}\npython agent.py"
    hidden = " hidden" if index else ""
    return f'''<article class="stage" id="{escape(stage['tag'])}" data-stage="{escape(stage['tag'])}"{hidden}>
      <div class="eyebrow">{escape(stage['minutes'])} <span>同一个 agent.py · 第 {index + 1} / 6 个版本</span></div>
      <h1>{escape(stage['title'])}</h1>
      <p class="focus">{escape(stage['focus'])}</p>
      <div class="learning-grid">
        <section><h2>增加什么能力</h2><p>{escape(stage['ability'])}</p></section>
        <section><h2>为什么需要</h2><p>{escape(stage['why'])}</p></section>
        <section><h2>可以演示</h2><p>{escape(stage['can_do'])}</p></section>
      </div>
      <section class="run-command" aria-label="运行当前阶段">
        <div class="command-row"><code class="command-text">{escape(command)}</code>
          <button class="copy-command" type="button">复制交互命令</button></div>
        <p>直接进入自由交互，以 <code>$ </code> 提示输入；按 <code>Ctrl+D</code> 结束。
          网页只展示代码与已保存输出；请在终端运行命令。</p>
      </section>
      <div class="version-bar"><span><code>{escape(stage['tag'])}</code> · commit <code title="{escape(stage['sha'])}">{escape(stage['sha'][:12])}</code></span>
        <span class="stats"><b class="plus">+{added}</b> / <b class="minus">−{removed}</b> 行 <small>全部教学源码</small></span></div>
      <div class="code-toolbar"><label>源码文件 <select class="file-selector" aria-label="选择源码文件">{options}</select></label>
        <span class="legend"><i class="added"></i> 新增 <i class="removed"></i> 删除 <i class="modified"></i> 修改后的行</span></div>
      {''.join(panels)}
      <section class="recording"><h2>示例运行结果 <span class="replay-badge">REPLAY · 已保存输出</span></h2>{render_recording(repo, stage['tag'], version=stage)}{extra}</section>
      <footer>统计仅覆盖本页的教学源码。替换一行计为删除一行、增加一行。页面内容来自 Git tag；本页不调用 API，也不执行模型生成的命令。</footer>
    </article>'''


CSS = r'''
:root { color-scheme: light; --ink:#172737; --muted:#5b6d7d; --line:#dce5e9; --accent:#08796e; --code-size:14px; }
* { box-sizing:border-box; }
body { margin:0; font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; color:var(--ink); background:#f4f7f8; }
button,select { font:inherit; } button,select,a { touch-action:manipulation; }
button:focus-visible,select:focus-visible,a:focus-visible { outline:3px solid #d79519; outline-offset:3px; }
[hidden] { display:none!important; }
.layout { display:grid; grid-template-columns:255px minmax(0,1fr); min-height:100vh; }
aside { position:sticky; top:0; height:100vh; background:#112c36; color:#e6f2f2; padding:32px 22px; overflow:auto; }
.brand { font-size:13px; color:#8fbbb9; letter-spacing:.12em; } .course-title { font-size:22px; line-height:1.5; margin:14px 0 9px; font-weight:700; }
.subtitle { font-size:13px; color:#afc7ce; margin:0 0 28px; }
nav { display:grid; gap:8px; } .stage-link { border:1px solid transparent; border-radius:8px; background:transparent; padding:13px 12px; text-align:left; color:#d8e9ed; cursor:pointer; line-height:1.5; width:100%; }
.stage-link:hover { background:#203e48; } .stage-link[aria-current="step"] { background:#e3f7f1; color:#12594f; border-color:#b4e4d6; font-weight:700; }
.stage-link small { display:block; color:inherit; opacity:.7; font-size:11px; margin-top:3px; font-weight:400; }
.sidebar-note { border-top:1px solid #36515a; color:#afc7ce; margin-top:28px; padding-top:17px; font-size:12px; }
main { min-width:0; padding:30px clamp(22px,3.2vw,58px) 50px; max-width:1700px; width:100%; }
.page-note { font-size:12px; color:var(--muted); margin:0 0 25px; }
.page-controls { display:flex; justify-content:space-between; align-items:baseline; gap:14px; flex-wrap:wrap; }
.font-control { white-space:nowrap; font-size:12px; color:var(--muted); }
.eyebrow { color:var(--accent); font-size:13px; font-weight:600; } .eyebrow span { color:var(--muted); float:right; font-weight:400; }
h1 { font-size:clamp(26px,2.5vw,38px); line-height:1.3; margin:9px 0 10px; letter-spacing:-.025em; }
.focus { font-size:17px; color:var(--muted); margin:0 0 23px; }
.learning-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-bottom:22px; }
.learning-grid section { background:#fff; border:1px solid var(--line); border-radius:8px; padding:15px 18px; } h2 { margin:0; font-size:15px; }
.learning-grid h2 { font-size:12px; color:var(--accent); margin-bottom:6px; } .learning-grid p { margin:0; font-size:14px; }
.run-command { margin-bottom:20px; padding:12px 16px; background:#edf7f4; border:1px solid #c6e1d8; border-radius:8px; }
.command-row { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
.command-text { overflow-wrap:anywhere; white-space:pre-wrap; font-size:14px; }
.copy-command { padding:5px 10px; border:1px solid #82b6a7; border-radius:5px; background:#fff; color:#155f4f; cursor:pointer; font-size:12px; }
.run-command p { font-size:12px; color:var(--muted); margin:8px 0 0; }
.version-bar,.code-toolbar { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; }
.version-bar { font-size:12px; margin-bottom:12px; } code { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
.stats { display:flex; align-items:baseline; gap:7px; } .plus { color:#147843; } .minus { color:#ad3c3c; } .stats small { color:var(--muted); }
.code-toolbar { border:1px solid var(--line); border-bottom:0; padding:10px 14px; background:#fff; border-radius:8px 8px 0 0; font-size:12px; }
select { background:#f6f9fa; border:1px solid #c7d5db; color:var(--ink); border-radius:5px; margin-left:8px; padding:4px 24px 4px 8px; font:12px ui-monospace,SFMono-Regular,Menlo,monospace; }
.legend { display:flex; align-items:center; gap:6px; color:var(--muted); } .legend i { display:inline-block; width:10px; height:10px; border:1px solid #abb; margin-left:7px; }
.code-columns { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,.88fr); border:1px solid var(--line); border-radius:0 0 8px 8px; background:#fff; overflow:hidden; }
.code-pane { min-width:0; } .code-pane+section { border-left:1px solid var(--line); }
h3 { margin:0; padding:11px 14px; background:#edf3f5; font-size:12px; font-weight:600; border-bottom:1px solid var(--line); }
pre { margin:0; font:var(--code-size)/1.75 ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace; tab-size:4; }
.source-code,.diff-code { overflow:auto; max-height:560px; padding:13px 0; background:#fcfdfe; }
.code-line,.diff-line { display:block; width:max-content; min-width:100%; white-space:pre; }
.line-number { display:inline-block; width:4em; padding-right:1em; text-align:right; color:#7a8b96; user-select:none; }
.code-line code { padding-right:18px; } .diff-line { padding:0 14px; }
.added { background:#e5f6e9; } .removed { background:#fde9e8; } .modified { background:#eee9ff; }
.code-line.added { border-left:3px solid #379057; } .code-line.modified { border-left:3px solid #8861bb; }
.code-line.added .line-number,.code-line.modified .line-number { width:calc(4em - 3px); }
.diff-header { background:#e9eff2; color:#55717b; } .diff-range { color:#26748e; background:#edf8ff; }
.empty { margin:0; padding:20px; font-size:13px; color:var(--muted); }
.recording { margin-top:26px; } .recording h2 { display:flex; align-items:center; gap:10px; margin-bottom:9px; }
.replay-badge { font-size:10px; background:#fff1d7; border:1px solid #e6cd99; color:#7c5816; border-radius:4px; padding:2px 6px; font-weight:400; }
.recording-meta { color:var(--muted); font-size:11px; margin:3px 0; }
.terminal { margin-top:12px; padding:20px; border-radius:8px; background:#132e38; color:#dfefed; max-height:430px; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; }
footer { font-size:11px; color:var(--muted); margin-top:20px; } noscript { display:block; background:#fff2cb; padding:12px; }
@media(max-width:1000px) { .layout { grid-template-columns:215px minmax(0,1fr); } aside { padding:25px 15px; } .course-title { font-size:19px; } .learning-grid { grid-template-columns:1fr; gap:8px; } .learning-grid section { padding:10px 14px; } .code-columns { grid-template-columns:1fr; } .code-pane+section { border-left:0; border-top:1px solid var(--line); } .source-code { max-height:430px; } .diff-code { max-height:280px; } .eyebrow span { display:block; float:none; } }
@media(max-width:650px) { .layout { display:block; } aside { position:static; width:100%; height:auto; padding:17px 18px; } .brand,.subtitle,.sidebar-note { display:none; } .course-title { font-size:17px; margin:0 0 12px; } nav { display:flex; overflow-x:auto; gap:7px; } .stage-link { flex:0 0 145px; padding:9px; font-size:12px; } main { padding:20px 14px 35px; } .page-note { margin-bottom:18px; } .learning-grid p { font-size:13px; } .legend { font-size:10px; } }
'''

JS = r'''
(() => {
  const buttons = Array.from(document.querySelectorAll('.stage-link'));
  const stages = Array.from(document.querySelectorAll('.stage'));
  function selectStage(tag, updateHash) {
    if (!stages.some(stage => stage.dataset.stage === tag)) tag = stages[0].dataset.stage;
    stages.forEach(stage => { stage.hidden = stage.dataset.stage !== tag; });
    buttons.forEach(button => {
      if (button.dataset.target === tag) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
    if (updateHash) history.replaceState(null, '', '#' + tag);
  }
  buttons.forEach(button => button.addEventListener('click', () => selectStage(button.dataset.target, true)));
  document.querySelectorAll('.copy-command').forEach(button => {
    button.addEventListener('click', async () => {
      const command = button.closest('.command-row').querySelector('.command-text').textContent;
      try {
        await navigator.clipboard.writeText(command);
        button.textContent = '已复制';
      } catch (error) {
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(button.closest('.command-row').querySelector('.command-text'));
        selection.removeAllRanges();
        selection.addRange(range);
        button.textContent = '命令已选中，请手动复制';
      }
    });
  });
  document.querySelectorAll('.file-selector').forEach(select => {
    select.addEventListener('change', () => {
      select.closest('.stage').querySelectorAll('.file-panel').forEach(panel => {
        panel.hidden = panel.dataset.file !== select.value;
      });
    });
  });
  document.querySelector('#font-size').addEventListener('change', event => {
    const size = Number(event.target.value);
    if ([14, 16, 18, 20].includes(size)) {
      document.documentElement.style.setProperty('--code-size', size + 'px');
    }
  });
  window.addEventListener('hashchange', () => selectStage(location.hash.slice(1), false));
  selectStage(location.hash.slice(1), false);
})();
'''


def build(repo, metadata, output, source_files=SOURCE_FILES):
    stages = read_stages(metadata)
    versions = load_versions(repo, stages, source_files)
    navigation = []
    articles = []
    for index, stage in enumerate(versions):
        current = ' aria-current="step"' if not index else ""
        navigation.append(
            f'<button class="stage-link" type="button" data-target="{escape(stage["tag"])}"{current}>'
            f'{escape(stage["title"])}<small>{escape(stage["tag"])}</small></button>'
        )
        articles.append(render_stage(repo, stage, versions[index - 1] if index else None,
                                     index, source_files))
    document = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>从文字接龙到 AI Agent · 代码演进</title><style>{CSS}</style></head>
<body><div class="layout"><aside>
  <div class="brand">45 MINUTES / SIX VERSIONS</div>
  <p class="course-title">从文字接龙<br>到 AI Agent</p>
  <p class="subtitle">用一个 API 构建智能体</p>
  <nav aria-label="教学阶段">{''.join(navigation)}</nav>
  <p class="sidebar-note">点击阶段即可查看真实 Git 版本。<br>绿：新增 · 红：删除 · 紫：修改<br>终端切换版本后直接运行 agent.py。</p>
</aside><main>
  <div class="page-controls"><p class="page-note">离线代码演进界面 · 源码来自六个 Git tags · 示例来自已保存运行记录 · 无需联网</p>
    <label class="font-control">代码字号 <select id="font-size" aria-label="代码字号"><option value="14">14 px</option><option value="16">16 px</option><option value="18">18 px · 投影</option><option value="20">20 px · 投影</option></select></label></div>
  <noscript>请启用浏览器 JavaScript 以切换阶段；源码与运行记录均已内嵌在本文件中。</noscript>
  {''.join(articles)}
</main></div><script>{JS}</script></body></html>
'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--metadata", type=Path, help="阶段说明 JSON；默认读取仓库中的 web/stages.json")
    parser.add_argument("--output", type=Path, help="输出 HTML；默认写入仓库中的 web/index.html")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        output = build(repo, args.metadata or repo / "web" / "stages.json",
                       args.output or repo / "web" / "index.html")
    except (BuildError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"构建失败：{exc}", file=sys.stderr)
        return 1
    print(f"已生成：{output}\n可直接在浏览器中打开；页面内嵌全部源码、diff 和已保存输出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
