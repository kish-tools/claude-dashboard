#!/usr/bin/env python3
"""
experiment.py - Autoresearch用の実験ファイル
このファイルのANALYZE_PROMPTをAIエージェントが改善します。
eval.pyとanalyze_chats.pyから参照されます。

【重要】このファイルのANALYZE_PROMPTのみ変更してください。
Pythonコードの構造（関数定義等）は変えないこと。
"""

# AIエージェントが改善するプロンプトテンプレート
# {chat_list} がチャット一覧に置換されます
ANALYZE_PROMPT = """あなたはユーザーのAI/Claude活用状況を分析する専門アシスタントです。
以下はClaudeとの会話タイトルと要約の一覧です（形式: [日付] [UUID] タイトル）。

{chat_list}

## 分析指示

これらの会話を分析し、意味のあるプロジェクト単位でグルーピングしてください。

### グルーピングルール
- 同じ目的・テーマの会話は同じプロジェクトにまとめる
- 1つのプロジェクトには最低2つ以上のチャットを含めること（単独チャットは「雑談・その他」へ）
- 「雑談・調査・その他」グループに単発の質問・調査・学習チャットをまとめる
- chat_idsには必ずリスト内の [UUID] 部分をそのまま使用すること（タイトルではなくUUID）

### ステータス判定基準
- `active`: 最近1ヶ月以内に更新があり、継続的に作業中
- `hold`: 作業が止まっている、または優先度が下がっている
- `done`: 目標が達成済み、または明らかに完結している

### next_actionのルール
- 「〜を検討する」ではなく「〜を実装してテストする」のような具体的なアクション
- 40文字以内で記述
- 動詞で終わること（例: 〜を完成させる、〜を設定する）

必ず以下のJSON形式だけで回答してください（説明文・コードブロック不要）:
{{
  "projects": [
    {{
      "id": "英数字のslug（例: line-secretary, ec-site）",
      "name": "プロジェクト名（20文字以内）",
      "emoji": "絵文字1文字",
      "description": "プロジェクトの概要（50文字以内）",
      "status": "active または hold または done",
      "progress": 0から100の整数,
      "topics": ["主なトピック1", "トピック2", "トピック3"],
      "next_action": "次にやるべき具体的なアクション（40文字以内）",
      "chat_ids": ["xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"]
    }}
  ]
}}"""


def get_prompt(chat_list: str) -> str:
    """チャット一覧を埋め込んだプロンプトを返す。"""
    return ANALYZE_PROMPT.format(chat_list=chat_list)
