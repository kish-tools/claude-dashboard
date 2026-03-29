#!/usr/bin/env python3
"""
eval.py - Autoresearch用の評価スクリプト
experiment.pyのプロンプトでデモデータを分析し、品質スコアを返す。
スコアはJSON形式でstdoutに出力される。

【重要】このファイルは変更しないこと。
"""
import json, subprocess, re, sys
from pathlib import Path

INSTALL_DIR = Path(__file__).parent
DEMO_FILE   = INSTALL_DIR / "eval_testdata.json"


# ── テストデータが無ければ組み込みを使う ──────────────────────────────────
BUILTIN_TESTDATA = {
    "chats": [
        {"id": "bb000001-0000-0000-0000-000000000001", "title": "ECサイトのトップページ改善",       "summary": "CVR向上のためのトップページ改善案を検討した。",               "updated_at": "2026-03-28T10:00:00Z"},
        {"id": "bb000001-0000-0000-0000-000000000002", "title": "商品ページのSEO対策",               "summary": "メタタグとコンテンツを最適化してSEOを改善する方法を議論した。",   "updated_at": "2026-03-27T10:00:00Z"},
        {"id": "bb000001-0000-0000-0000-000000000003", "title": "カート離脱率の分析と改善",         "summary": "カート離脱が高い原因を分析し、チェックアウトフローの改善策を検討。", "updated_at": "2026-03-26T10:00:00Z"},
        {"id": "bb000002-0000-0000-0000-000000000001", "title": "社内ChatBot構築の要件定義",        "summary": "社内向けChatBotの要件定義と技術スタックを整理した。",               "updated_at": "2026-03-28T10:00:00Z"},
        {"id": "bb000002-0000-0000-0000-000000000002", "title": "RAGシステムの実装方法",            "summary": "社内ドキュメントを活用したRAGシステムの実装手順を検討した。",         "updated_at": "2026-03-27T10:00:00Z"},
        {"id": "bb000002-0000-0000-0000-000000000003", "title": "SlackBot連携の実装",               "summary": "SlackBotとChatBotを連携させる実装方法について議論した。",           "updated_at": "2026-03-26T10:00:00Z"},
        {"id": "bb000003-0000-0000-0000-000000000001", "title": "月次レポートの自動化",             "summary": "Pythonで月次売上レポートを自動生成するスクリプトを作成した。",         "updated_at": "2026-03-10T10:00:00Z"},
        {"id": "bb000003-0000-0000-0000-000000000002", "title": "請求書処理の自動化",               "summary": "PDFの請求書をOCRで読み取りスプレッドシートに自動入力する仕組みを構築。", "updated_at": "2026-03-09T10:00:00Z"},
        {"id": "bb000004-0000-0000-0000-000000000001", "title": "Pythonの基礎を学ぶ",               "summary": "Python初心者向けに基本的な文法と使い方を学習した。",                 "updated_at": "2026-03-05T10:00:00Z"},
        {"id": "bb000004-0000-0000-0000-000000000002", "title": "英文メールの翻訳・添削",           "summary": "海外取引先へのビジネスメールを英語に翻訳・添削した。",               "updated_at": "2026-03-04T10:00:00Z"},
    ]
}

# 期待されるグルーピング（正解データ）
EXPECTED_GROUPS = {
    "ec-site":    {"bb000001-0000-0000-0000-000000000001", "bb000001-0000-0000-0000-000000000002", "bb000001-0000-0000-0000-000000000003"},
    "chatbot":    {"bb000002-0000-0000-0000-000000000001", "bb000002-0000-0000-0000-000000000002", "bb000002-0000-0000-0000-000000000003"},
    "automation": {"bb000003-0000-0000-0000-000000000001", "bb000003-0000-0000-0000-000000000002"},
    "other":      {"bb000004-0000-0000-0000-000000000001", "bb000004-0000-0000-0000-000000000002"},
}


def run_claude(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "--print", "--output-format", "text"],
        input=prompt, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude error: {result.stderr[:200]}")
    return result.stdout.strip()


def build_chat_list(chats: list) -> str:
    lines = []
    for c in chats:
        summary = c.get("summary", "").replace("\\n", " ").strip()[:150]
        date = (c.get("updated_at") or "")[:10]
        lines.append(f'- [{date}] [{c["id"]}] {c["title"]}' +
                     (f'\n  要約: {summary}' if summary else ""))
    return "\n".join(lines)


def score_grouping(projects: list, all_ids: set) -> dict:
    """グルーピング結果をスコアリング（0-100）"""

    # --- coherence: 同じグループに関連チャットが入っているか（期待グループとの一致度）---
    coherence_scores = []
    for exp_group in EXPECTED_GROUPS.values():
        best = 0.0
        for proj in projects:
            got = set(proj.get("chat_ids", []))
            if not got:
                continue
            intersection = exp_group & got
            union = exp_group | got
            iou = len(intersection) / len(union) if union else 0
            if iou > best:
                best = iou
        coherence_scores.append(best)
    coherence = round(sum(coherence_scores) / len(coherence_scores) * 100) if coherence_scores else 0

    # --- coverage: 全チャットが何らかのプロジェクトに入っているか ---
    assigned = set()
    for proj in projects:
        assigned.update(proj.get("chat_ids", []))
    valid_assigned = assigned & all_ids
    coverage = round(len(valid_assigned) / len(all_ids) * 100) if all_ids else 0

    # --- actionability: next_actionが具体的か（LLM判定）---
    next_actions = [p.get("next_action", "") for p in projects if p.get("next_action")]
    if next_actions:
        actions_text = "\n".join(f"- {a}" for a in next_actions)
        judge_prompt = f"""以下のnext_actionリストを評価してください。

{actions_text}

評価基準:
- 具体的な行動が書かれているか（「〜する」「〜を実装する」等）
- 曖昧な表現（「検討する」「考える」）は低評価
- 40文字以内に収まっているか

0から100のスコアのみ返してください（数字のみ）:"""
        try:
            raw = run_claude(judge_prompt)
            actionability = int(re.search(r'\d+', raw).group())
            actionability = max(0, min(100, actionability))
        except Exception:
            actionability = 50
    else:
        actionability = 0

    score = round((coherence + coverage + actionability) / 3)
    return {
        "coherence": coherence,
        "coverage": coverage,
        "actionability": actionability,
        "score": score,
    }


def main():
    # experiment.pyをインポート
    sys.path.insert(0, str(INSTALL_DIR))
    try:
        import importlib
        exp = importlib.import_module("experiment")
        importlib.reload(exp)
        get_prompt = exp.get_prompt
    except Exception as e:
        print(json.dumps({"error": f"experiment.py import error: {e}", "score": 0}))
        sys.exit(1)

    # テストデータ読み込み
    if DEMO_FILE.exists():
        data = json.loads(DEMO_FILE.read_text())
        chats = data.get("chats", [])
    else:
        chats = BUILTIN_TESTDATA["chats"]

    all_ids = {c["id"] for c in chats}
    chat_list = build_chat_list(chats)
    prompt = get_prompt(chat_list)

    # Claude実行
    try:
        raw = run_claude(prompt)
    except Exception as e:
        print(json.dumps({"error": str(e), "score": 0}))
        sys.exit(1)

    # JSON抽出
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if not json_match:
        print(json.dumps({"error": "JSON not found", "score": 0, "raw": raw[:200]}))
        sys.exit(1)

    try:
        result = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"JSON parse error: {e}", "score": 0}))
        sys.exit(1)

    projects = result.get("projects", [])
    scores = score_grouping(projects, all_ids)
    scores["num_projects"] = len(projects)

    print(json.dumps(scores, ensure_ascii=False))


main()
