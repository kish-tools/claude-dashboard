#!/usr/bin/env python3
"""
Claude Dashboard - AI Analysis Script
Uses `claude` CLI to analyze chats and generate project structure.
No API key required - uses Claude Code's OAuth.
プロンプトはexperiment.pyから読み込む（autoresearchで自動改善される）。
"""
import json, subprocess, sys, re
from datetime import datetime
from pathlib import Path

CHATS_JSON   = Path.home() / "claude_dashboard/claude_chats.json"
PROJECTS_JSON = Path.home() / "claude_dashboard/claude_projects.json"
INSTALL_DIR  = Path.home() / "claude_dashboard"


def run_claude(prompt: str) -> str:
    """claude CLIでプロンプトを実行してレスポンスを返す。"""
    result = subprocess.run(
        ["claude", "--print", "--output-format", "text"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI error: {result.stderr[:200]}")
    return result.stdout.strip()


def build_chat_list(chats: list) -> str:
    """分析用のチャット一覧テキストを作る。"""
    lines = []
    for c in chats:
        summary = c.get("summary", "").replace("\\n", " ").strip()
        summary_short = summary[:150] if summary else ""
        date = (c.get("updated_at") or "")[:10]
        lines.append(
            f'- [{date}] [{c["id"]}] {c["title"]}'
            + (f'\n  要約: {summary_short}' if summary_short else "")
        )
    return "\n".join(lines)


def analyze(chats: list) -> dict:
    """claudeでプロジェクト分析を実行してJSONを返す。"""
    chat_list = build_chat_list(chats)

    # experiment.pyのプロンプトを使用（autoresearchで自動改善される）
    try:
        import importlib, sys as _sys
        _sys.path.insert(0, str(INSTALL_DIR))
        exp = importlib.import_module("experiment")
        importlib.reload(exp)
        prompt = exp.get_prompt(chat_list)
    except Exception:
        # experiment.pyが無い場合はフォールバック
        prompt = f"""以下のClaudeとの会話を分析して、プロジェクト別にJSON形式でまとめてください。

{chat_list}

必ず以下のJSON形式だけで回答してください:
{{"projects": [{{"id": "slug", "name": "名前", "emoji": "絵文字", "description": "概要", "status": "active", "progress": 50, "topics": [], "next_action": "次のアクション", "chat_ids": []}}]}}"""

    raw = run_claude(prompt)

    # JSON部分を抽出
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if not json_match:
        raise ValueError(f"JSON not found in response: {raw[:200]}")

    return json.loads(json_match.group())


def main():
    if not CHATS_JSON.exists():
        print("ERROR: claude_chats.json が見つかりません。先に sync_claude_chats.py を実行してください。")
        sys.exit(1)

    data = json.loads(CHATS_JSON.read_text())
    chats = data.get("chats", [])

    if not chats:
        print("チャットデータが空です。")
        sys.exit(1)

    print(f"[分析中] {len(chats)}件のチャットを分析しています...")

    try:
        result = analyze(chats)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    projects = result.get("projects", [])

    # chat_id → project_id のマッピングを chats.json にも書き込む
    chat_project_map = {}
    for proj in projects:
        for cid in proj.get("chat_ids", []):
            chat_project_map[cid] = proj["id"]

    for chat in chats:
        chat["project_id"] = chat_project_map.get(chat["id"], "other")

    data["last_analyzed"] = datetime.now().isoformat()
    CHATS_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # projects.json を保存
    output = {
        "last_analyzed": datetime.now().isoformat(),
        "projects": projects,
    }
    PROJECTS_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    print(f"[完了] {len(projects)}件のプロジェクトを生成しました")
    for p in projects:
        print(f"  {p['emoji']} {p['name']} ({p['status']}) {p['progress']}% → {p['next_action']}")


main()
