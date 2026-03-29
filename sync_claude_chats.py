#!/usr/bin/env python3
"""
Claude Dashboard - Chat Sync Script
Extracts chat IDs and titles from Claude desktop app's LevelDB storage.
"""
import re, json, struct, shutil, tempfile
from datetime import datetime
from pathlib import Path

LEVELDB_PATH = Path.home() / "Library/Application Support/Claude/Local Storage/leveldb"
OUTPUT_JSON  = Path.home() / "claude_dashboard/claude_chats.json"

UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


# ── LevelDB log record parser ────────────────────────────────────────────────

def _read_varint(data: bytes, pos: int):
    result, shift = 0, 0
    while True:
        b = data[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def _parse_log_writebatch(raw: bytes) -> dict:
    """LevelDB log ファイルを解析して key→value マップを返す。
    値は先頭 0x00 バイト + UTF-16LE 本体の Chromium LocalStorage 形式。
    """
    BLOCK_SIZE = 32768
    records = []
    pos = 0
    while pos + 7 <= len(raw):
        block_end = ((pos // BLOCK_SIZE) + 1) * BLOCK_SIZE
        if pos + 4 > len(raw):
            break
        length = struct.unpack_from('<H', raw, pos + 4)[0]
        rtype  = raw[pos + 6]
        if length == 0 and rtype == 0:
            pos = block_end
            continue
        data = raw[pos + 7 : pos + 7 + length]
        records.append((rtype, data))
        pos += 7 + length
        if pos > block_end - 7:
            pos = block_end

    # FIRST(2) + MID(3)... + LAST(4) を結合
    current = bytearray()
    assembled = []
    for rtype, data in records:
        if rtype == 1:
            assembled.append(bytes(data))
        elif rtype == 2:
            current = bytearray(data)
        elif rtype == 3:
            current.extend(data)
        elif rtype == 4:
            current.extend(data)
            assembled.append(bytes(current))
            current = bytearray()

    kv = {}
    for rec in assembled:
        if len(rec) < 12:
            continue
        count = struct.unpack_from('<I', rec, 8)[0]
        pos = 12
        for _ in range(count):
            if pos >= len(rec):
                break
            etype = rec[pos]; pos += 1
            klen, pos = _read_varint(rec, pos)
            key = rec[pos:pos + klen]; pos += klen
            if etype == 1:  # PUT
                vlen, pos = _read_varint(rec, pos)
                val = rec[pos:pos + vlen]; pos += vlen
                kv[key] = val
            # DELETE は無視
    return kv


def extract_titles_from_leveldb(ldb_dir: Path) -> dict:
    """LocalStorage LevelDB からチャット UUID → タイトルを抽出する。"""
    title_map = {}

    # DB がロックされている可能性があるのでコピーして読む
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp) / "ldb"
        try:
            shutil.copytree(str(ldb_dir), str(tmp_dir))
        except Exception:
            return title_map

        # .log ファイルを優先（最新データ）、次に .ldb
        log_files = sorted(tmp_dir.glob("*.log"))
        ldb_files = sorted(tmp_dir.glob("*.ldb"))

        for f in log_files + ldb_files:
            try:
                raw = f.read_bytes()
            except Exception:
                continue

            if f.suffix == ".log":
                # LevelDB ログ形式を解析
                try:
                    kv = _parse_log_writebatch(raw)
                    for key, val in kv.items():
                        if b'react-query-cache-ls' in key:
                            _extract_from_rqc_value(val, title_map)
                except Exception:
                    pass
            else:
                # .ldb (SSTable): バイナリで UUID + 前後の name フィールドを探す
                _extract_from_ldb_raw(raw, title_map)

    return title_map



def _extract_from_rqc_value(val: bytes, title_map: dict):
    """react-query-cache-ls の値（先頭 0x00 + UTF-16LE JSON）から
    ユーザーのチャット uuid→name マッピングを抽出する。
    会話オブジェクトは uuid → name → ... → summary の順でフィールドを持つ。
    組織オブジェクトには summary がないので、これで区別する。
    """
    if not val or val[0] != 0x00:
        return
    try:
        val_str = val[1:].decode('utf-16-le', errors='replace')
    except Exception:
        return

    # 会話オブジェクト: uuid → name → summary → model → created_at → updated_at
    conv_re = re.compile(
        r'"uuid":"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"'
        r',"name":"((?:[^"\\]|\\.){1,300})"'
        r',"summary":"((?:[^"\\]|\\.){0,2000})"'
        r'[^}]{0,100}"model":"(claude-[^"]+)"'
        r'[^}]{0,100}"created_at":"([^"]+)"'
        r'[^}]{0,100}"updated_at":"([^"]+)"'
    )

    for m in conv_re.finditer(val_str):
        uid, name, summary, model, created_at, updated_at = m.groups()
        if uid not in title_map and len(name) >= 1:
            title_map[uid] = {
                "title": name,
                "summary": summary,
                "model": model,
                "created_at": created_at,
                "updated_at": updated_at,
            }


def _extract_from_ldb_raw(data: bytes, title_map: dict):
    """SSTable バイナリから UUID + name フィールドを抽出する（フォールバック）。"""
    uuid_pat = re.compile(rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
    # UTF-16LE エンコードの "name":"..." を探す
    name_pat_utf16 = re.compile(
        '"name":"'.encode('utf-16-le') + rb'((?:[^\x22\x00]|\x22\x30|[\x00-\xff][\x00-\xff]){2,300})'
    )

    for m in uuid_pat.finditer(data):
        uid = m.group().decode()
        if uid in title_map:
            continue
        window_start = max(0, m.start() - 100)
        window = data[window_start : m.end() + 1200]
        # UTF-16LE で name フィールドを探す
        try:
            w16 = window.decode('utf-16-le', errors='replace')
            nm = re.search(r'"name"\s*:\s*"((?:[^"\\]|\\.){2,300})"', w16)
            if nm:
                name = nm.group(1)
                if len(name) >= 2 and not name.startswith('user_') and not name.startswith('http'):
                    title_map[uid] = name
        except Exception:
            pass


def sync():
    title_map = extract_titles_from_leveldb(LEVELDB_PATH)
    # react-query-cache に含まれる UUID = 実際のユーザーチャット
    # （Claude Code バックグラウンドセッションは除外される）
    uuid_set = set(title_map.keys())

    # 既存データを読み込む
    data = {"chats": []}
    if OUTPUT_JSON.exists():
        try:
            data = json.loads(OUTPUT_JSON.read_text())
        except Exception:
            pass

    existing = {c["id"]: c for c in data["chats"]}
    added = updated = 0

    # 既存チャットのタイトル・summaryを更新
    for chat in data["chats"]:
        meta = title_map.get(chat["id"])
        if meta:
            if chat["title"] == "（タイトル未確認）":
                chat["title"] = meta["title"]
                updated += 1
            # summary・日時は常に最新で上書き
            chat["summary"]    = meta["summary"]
            chat["model"]      = meta["model"]
            chat["created_at"] = meta["created_at"]
            chat["updated_at"] = meta["updated_at"]

    # 新規チャットを追加
    for uid in uuid_set:
        if uid not in existing:
            meta = title_map[uid]
            data["chats"].append({
                "id":         uid,
                "url":        f"https://claude.ai/chat/{uid}",
                "title":      meta["title"],
                "summary":    meta["summary"],
                "model":      meta["model"],
                "created_at": meta["created_at"],
                "updated_at": meta["updated_at"],
                "status":     "todo",
                "note":       "",
                "tags":       [],
            })
            added += 1

    data["last_updated"] = datetime.now().isoformat()
    data["total"]        = len(data["chats"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    titled = sum(1 for c in data["chats"] if c["title"] != "（タイトル未確認）")
    print(f"[OK] {datetime.now().strftime('%H:%M:%S')} "
          f"総数:{len(data['chats'])}件 新規:{added}件 タイトル取得:{titled}件")


sync()
