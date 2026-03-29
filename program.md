# Claude Dashboard Autoresearch - Program Instructions

あなたはClaude Dashboardの「プロジェクト分析プロンプト」を改善するAIエージェントです。
自動ループの中で、experiment.pyを修正して、分析品質スコアを向上させてください。

## あなたのゴール

`experiment.py` の中にある `ANALYZE_PROMPT` テンプレートを改善して、
Claudeによるチャット→プロジェクトのグルーピング精度を上げること。

**スコア基準（eval.pyが測定）：**
- `coherence` (0-100): 関連チャットが正しく同一プロジェクトにまとまっているか
- `coverage` (0-100): 全チャットが意味あるプロジェクトに振り分けられているか
- `actionability` (0-100): next_actionが具体的で実行可能か

## 変更してよいもの

- `experiment.py` の `ANALYZE_PROMPT` 文字列のみ

## 絶対に変更してはいけないもの

- `eval.py` （評価ロジック）
- `autoloop.sh` （ループロジック）
- `program.md` （このファイル）
- `sync_claude_chats.py` （データ同期）
- `analyze_chats.py` （本番分析スクリプト）
- `dashboard.html` （UI）

## 改善のヒント

以下のような観点でプロンプトを改善してみてください：

1. **グルーピングルールの明確化**: 何をもって「同じプロジェクト」とするか
2. **chat_ids の精度向上**: UUIDを正確に抽出するための指示強化
3. **ステータス判定の改善**: active/hold/done の基準を具体化
4. **next_action の品質向上**: より具体的・実行可能なアクションを生成させる
5. **Few-shotの追加**: 良いグルーピング例をプロンプトに含める
6. **Chain-of-thought**: 分析の思考プロセスを明示させる

## 制約

- 出力形式（JSON構造）は変えないこと
- Pythonコードの構造（関数定義、import等）は変えないこと
- 日本語での出力指示は維持すること
