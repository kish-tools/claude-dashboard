# 🗂️ Claude Dashboard

**Claudeのチャット履歴を自動収集して進捗管理できるローカルダッシュボード**

## 🚀 インストール（1行コピペ）
```bash
bash <(curl -s https://raw.githubusercontent.com/kish-tools/claude-dashboard/main/install.sh)
```

## ✨ できること
- 🔄 5分ごとにチャットURLを自動収集
- 📊 プロジェクト別・ステータス別に整理
- 📈 完了率・マイルストーン・次のアクションを可視化
- 🚀 Mac再起動後も自動起動

## 📋 動作環境
- macOS / Python 3.8以上 / Claudeデスクトップアプリ

## ❓ アンインストール
```bash
launchctl unload ~/Library/LaunchAgents/com.kish.claude-chat-sync.plist
launchctl unload ~/Library/LaunchAgents/com.kish.dashboard-server.plist
rm -rf ~/claude_dashboard
rm ~/Library/LaunchAgents/com.kish.claude-chat-sync.plist
rm ~/Library/LaunchAgents/com.kish.dashboard-server.plist
```

## 🛠️ 作者
**キッシュ** — Claude × LINE AI活用の人
