#!/bin/bash
# autoloop.sh - Claude Dashboard Autoresearch Loop
# experiment.pyのプロンプトを自動改善し、スコアが上がったらgit commitする。
#
# 使い方:
#   bash ~/claude_dashboard/autoloop.sh          # デフォルト20回
#   bash ~/claude_dashboard/autoloop.sh 50       # 50回ループ
#   bash ~/claude_dashboard/autoloop.sh 0        # 無制限ループ

set -euo pipefail

INSTALL_DIR="$HOME/claude_dashboard"
SCORE_FILE="$INSTALL_DIR/best_score.txt"
LOG_FILE="$INSTALL_DIR/autoloop.log"
MAX_ITERS="${1:-20}"
PYTHON=$(which python3)

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE"
}

# ── 初期化 ─────────────────────────────────────────────────────────────────
cd "$INSTALL_DIR"

# gitリポジトリがなければ初期化
if [ ! -d ".git" ]; then
    git init -q
    git add experiment.py program.md eval.py autoloop.sh 2>/dev/null || true
    git commit -q -m "autoresearch: initial commit" 2>/dev/null || true
    log "Git initialized"
fi

# ベストスコアファイルがなければ作成
[ -f "$SCORE_FILE" ] || echo "0" > "$SCORE_FILE"
BEST=$(cat "$SCORE_FILE" | tr -d '[:space:]')

log "========================================"
log "Autoresearch loop start"
log "Install dir : $INSTALL_DIR"
log "Max iters   : $MAX_ITERS (0=unlimited)"
log "Best score  : $BEST"
log "========================================"

ITER=0

while true; do
    ITER=$((ITER+1))
    [ "$MAX_ITERS" -gt 0 ] && [ "$ITER" -gt "$MAX_ITERS" ] && break

    log "--- Iteration $ITER ---"

    # ── ステップ1: 現在のexperiment.pyをバックアップ ──────────────────────
    cp "$INSTALL_DIR/experiment.py" "$INSTALL_DIR/experiment_backup.py"

    # ── ステップ2: Claudeにexperiment.pyの改善を依頼 ─────────────────────
    CURRENT_EXPERIMENT=$(cat "$INSTALL_DIR/experiment.py")
    PROGRAM_MD=$(cat "$INSTALL_DIR/program.md")

    AGENT_PROMPT="$PROGRAM_MD

## 現在のexperiment.py（直近のベストスコア: $BEST/100）

\`\`\`python
$CURRENT_EXPERIMENT
\`\`\`

## タスク

上記のANALYZE_PROMPTを1箇所だけ改善してください。
- Pythonコードの構造（def, import等）は変えないこと
- ANALYZE_PROMPTの文字列内容のみ変更すること
- 改善したexperiment.pyの完全なファイル内容を返してください

出力形式: \`\`\`python から始まり \`\`\` で終わるコードブロックのみ（説明文不要）"

    log "Asking Claude to improve experiment.py..."
    AGENT_RESPONSE=$(echo "$AGENT_PROMPT" | claude --print --output-format text 2>/dev/null || echo "")

    if [ -z "$AGENT_RESPONSE" ]; then
        log "ERROR: Empty response from Claude. Skipping."
        cp "$INSTALL_DIR/experiment_backup.py" "$INSTALL_DIR/experiment.py"
        continue
    fi

    # コードブロックを抽出
    NEW_CODE=$($PYTHON -c "
import sys, re
text = sys.stdin.read()
m = re.search(r'\`\`\`python\n([\s\S]*?)\`\`\`', text)
if m:
    print(m.group(1), end='')
else:
    # コードブロックがない場合はそのまま使う
    stripped = text.strip()
    if 'ANALYZE_PROMPT' in stripped:
        print(stripped, end='')
" <<< "$AGENT_RESPONSE")

    if [ -z "$NEW_CODE" ] || ! echo "$NEW_CODE" | grep -q "ANALYZE_PROMPT"; then
        log "ERROR: Could not extract valid experiment.py. Skipping."
        cp "$INSTALL_DIR/experiment_backup.py" "$INSTALL_DIR/experiment.py"
        continue
    fi

    echo "$NEW_CODE" > "$INSTALL_DIR/experiment.py"

    # 構文チェック
    if ! $PYTHON -m py_compile "$INSTALL_DIR/experiment.py" 2>/dev/null; then
        log "ERROR: Syntax error in new experiment.py. Reverting."
        cp "$INSTALL_DIR/experiment_backup.py" "$INSTALL_DIR/experiment.py"
        continue
    fi

    # ── ステップ3: 評価 ───────────────────────────────────────────────────
    log "Running eval.py..."
    EVAL_OUTPUT=$($PYTHON "$INSTALL_DIR/eval.py" 2>&1) || true

    NEW_SCORE=$($PYTHON -c "
import sys, json
try:
    d = json.loads('''$EVAL_OUTPUT''')
    print(d.get('score', 0))
except:
    print(0)
" 2>/dev/null || echo "0")

    # eval詳細をログ
    DETAILS=$($PYTHON -c "
import sys, json
try:
    d = json.loads('''$EVAL_OUTPUT''')
    print(f\"coherence={d.get('coherence','?')} coverage={d.get('coverage','?')} actionability={d.get('actionability','?')} projects={d.get('num_projects','?')}\")
except:
    print('parse error')
" 2>/dev/null || echo "parse error")

    log "Score: $BEST → $NEW_SCORE  ($DETAILS)"

    # ── ステップ4: スコア比較・コミット ──────────────────────────────────
    IMPROVED=$($PYTHON -c "
try:
    print('yes' if float('$NEW_SCORE') > float('$BEST') else 'no')
except:
    print('no')
")

    if [ "$IMPROVED" = "yes" ]; then
        log "IMPROVED! Committing experiment.py (score: $BEST → $NEW_SCORE)"
        echo "$NEW_SCORE" > "$SCORE_FILE"
        BEST="$NEW_SCORE"
        git add experiment.py best_score.txt 2>/dev/null || true
        git commit -q -m "autoresearch: score $NEW_SCORE (iter $ITER)" 2>/dev/null || true
        log "Committed."
    else
        log "No improvement. Reverting experiment.py."
        cp "$INSTALL_DIR/experiment_backup.py" "$INSTALL_DIR/experiment.py"
    fi

    rm -f "$INSTALL_DIR/experiment_backup.py"

    # 無制限モード以外はループカウント表示
    if [ "$MAX_ITERS" -gt 0 ]; then
        log "Progress: $ITER/$MAX_ITERS (best=$BEST)"
    fi
done

log "========================================"
log "Autoresearch loop complete"
log "Final best score: $BEST"
log "Total iterations: $ITER"
log "========================================"
