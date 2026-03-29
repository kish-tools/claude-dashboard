#!/bin/bash
set -e

REPO="https://raw.githubusercontent.com/kish-tools/claude-dashboard/main"
INSTALL_DIR="$HOME/claude_dashboard"
PYTHON=$(which python3)
PLIST_SYNC="$HOME/Library/LaunchAgents/com.kish.claude-chat-sync.plist"
PLIST_SERVER="$HOME/Library/LaunchAgents/com.kish.dashboard-server.plist"
PORT=8082

echo "🗂️  Claude Dashboard セットアップ開始"

# 既存プロセスを全停止
pkill -f "http.server $PORT" 2>/dev/null || true
sleep 1

# 既存の launchd ジョブを削除
for plist in "$PLIST_SYNC" "$PLIST_SERVER"; do
  [ -f "$plist" ] && launchctl unload "$plist" 2>/dev/null; rm -f "$plist"
done

# インストールディレクトリを作成
mkdir -p "$INSTALL_DIR"

echo "📥 ファイルをダウンロード中..."
curl -sH "Cache-Control: no-cache" "$REPO/sync_claude_chats.py" -o "$INSTALL_DIR/sync_claude_chats.py"
curl -sH "Cache-Control: no-cache" "$REPO/analyze_chats.py"    -o "$INSTALL_DIR/analyze_chats.py"
curl -sH "Cache-Control: no-cache" "$REPO/dashboard.html"      -o "$INSTALL_DIR/dashboard.html"
curl -sH "Cache-Control: no-cache" "$REPO/experiment.py"       -o "$INSTALL_DIR/experiment.py"
curl -sH "Cache-Control: no-cache" "$REPO/eval.py"             -o "$INSTALL_DIR/eval.py"
curl -sH "Cache-Control: no-cache" "$REPO/autoloop.sh"         -o "$INSTALL_DIR/autoloop.sh"
curl -sH "Cache-Control: no-cache" "$REPO/program.md"          -o "$INSTALL_DIR/program.md"
chmod +x "$INSTALL_DIR/autoloop.sh"

# サーバー起動スクリプトを作成（WorkingDirectory の代わりに使用）
cat > "$INSTALL_DIR/start_server.sh" << SHELL
#!/bin/bash
cd "$INSTALL_DIR"
exec "$PYTHON" -m http.server $PORT
SHELL
chmod +x "$INSTALL_DIR/start_server.sh"

# sync 用 plist
cat > "$PLIST_SYNC" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.kish.claude-chat-sync</string>
  <key>ProgramArguments</key><array>
    <string>$PYTHON</string>
    <string>$INSTALL_DIR/sync_claude_chats.py</string>
  </array>
  <key>StartInterval</key><integer>300</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$INSTALL_DIR/sync.log</string>
  <key>StandardErrorPath</key><string>$INSTALL_DIR/sync_error.log</string>
</dict></plist>
PLIST

# server 用 plist（start_server.sh 経由で確実に正しいディレクトリから起動）
cat > "$PLIST_SERVER" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.kish.dashboard-server</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string>
    <string>$INSTALL_DIR/start_server.sh</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$INSTALL_DIR/server.log</string>
  <key>StandardErrorPath</key><string>$INSTALL_DIR/server_error.log</string>
</dict></plist>
PLIST

launchctl load "$PLIST_SYNC"
launchctl load "$PLIST_SERVER"

# autoresearch用 git リポジトリを初期化
if [ ! -d "$INSTALL_DIR/.git" ]; then
  cd "$INSTALL_DIR" && git init -q
  git config user.email "claude-dashboard@local" && git config user.name "Claude Dashboard"
  git add experiment.py program.md eval.py autoloop.sh 2>/dev/null || true
  git commit -q -m "autoresearch: initial setup" 2>/dev/null || true
  echo "0" > "$INSTALL_DIR/best_score.txt"
fi

# 初回 sync 実行
"$PYTHON" "$INSTALL_DIR/sync_claude_chats.py"

echo "✅ 完了！ http://localhost:$PORT/dashboard.html"
echo ""
echo "🔬 自動改善ループを起動するには:"
echo "   bash $INSTALL_DIR/autoloop.sh"
open "http://localhost:$PORT/dashboard.html" 2>/dev/null || true
