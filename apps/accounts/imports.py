"""Google 表單回覆 CSV → Registration 的解析與對應（#11）。

**為什麼獨立成模組**：解析與對應是純資料轉換，不碰 request 也不碰 DB，
拆出來才測得動——這裡的邏輯（欄位對位、樂器對照、日期格式）正是最容易出錯、
也最需要用真實資料反覆驗證的部分。

**為什麼用標題列比對而不是欄位順序**：表單題目會增修——實際回覆裡 Email 那題就是
2026-08-19 前後才加的，之前的欄位位置全部往後推。認標題文字才不會因為改題目而錯位。
"""

import csv
import datetime as dt
import io
import re

# 表單題目很長（含說明文字），所以用「包含這些關鍵字」來認欄位，不做完整比對。
# 順序有意義：先比對到的優先，所以較specific的關鍵字要排前面。
_COLUMN_KEYWORDS = {
    'name': ('姓名',),
    'national_id': ('身分證',),
    'birth_date': ('出生',),
    'phone': ('聯絡電話', '手機'),
    'email': ('電子信箱', 'email'),
    'address': ('通訊地址', '地址'),
    'line_id': ('line id', 'line'),
    'alumni_info': ('入學年', '就讀科系'),
    'instrument': ('第一聲部',),
}

# 表單填的是粗分類，系統的 InstrumentFamily 名稱略有出入，只有這幾個要轉。
# 對不上的不猜，留空給幹部指定（樂器本來就是選填）。
_INSTRUMENT_ALIASES = {
    '打擊樂器': '打擊樂',
    '長笛/短笛': '長笛',
    '長笛／短笛': '長笛',
    '鋼琴': '其他',
    '無': '',
}

_DATE_FORMATS = ('%Y/%m/%d', '%Y-%m-%d', '%Y.%m.%d')


class ImportError_(Exception):
    """整份檔案就有問題（例如缺必要欄位），與「單列有問題」不同層級。"""


def _match_columns(header):
    """把 CSV 標題列對應到我們的欄位名，回傳 {欄位: 索引}。"""
    mapping = {}
    for index, title in enumerate(header):
        lowered = title.strip().lower()
        for field, keywords in _COLUMN_KEYWORDS.items():
            if field in mapping:
                continue
            if any(keyword.lower() in lowered for keyword in keywords):
                mapping[field] = index
                break
    return mapping


def parse_date(value):
    """表單的日期格式不統一（1999/12/30、1999-12-30 都有），逐一試。"""
    value = (value or '').strip()
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def normalize_instrument(value):
    """表單的樂器值 → InstrumentFamily 名稱。對不上回傳空字串（不猜）。"""
    value = (value or '').strip()
    if not value:
        return ''
    return _INSTRUMENT_ALIASES.get(value, value)


def parse_csv(raw_bytes):
    """解析 CSV，回傳 (rows, columns)。

    rows 是 dict list，值都已 strip；columns 是實際對應到的欄位名集合，
    讓呼叫端知道這份檔案有哪些資料可用。
    """
    # Google 表單匯出的 CSV 是 UTF-8 with BOM，utf-8-sig 才不會讓第一個標題多出 ﻿
    try:
        text = raw_bytes.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ImportError_('檔案編碼無法辨識，請確認匯出為 UTF-8 的 CSV。')

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise ImportError_('檔案是空的。')

    columns = _match_columns(header)
    # 姓名與 Email 是建帳號的最低需求：沒有姓名不知道是誰，沒有 Email 產不出帳號
    for required in ('name', 'email'):
        if required not in columns:
            raise ImportError_(
                f'找不到「{"姓名" if required == "name" else "電子信箱"}」欄位。'
                '請確認上傳的是 Google 表單的回覆 CSV（第一列必須是題目標題）。'
            )

    rows = []
    for values in reader:
        if not any(v.strip() for v in values):
            continue    # 略過完全空白的列
        rows.append({
            field: values[index].strip() if index < len(values) else ''
            for field, index in columns.items()
        })
    return rows, set(columns)
