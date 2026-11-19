"""公告內容的格式化文字（rich text）處理。

編輯頁用 Quill 編輯器（static/vendor/quill-2.0.3/，自帶一份、不走 CDN），
送出的是 Quill 的 HTML。HTML 一律在「存檔」與「顯示」兩處都經過白名單過濾，
只留下編輯器工具列做得出來的格式，其餘（<script>、onerror=、javascript: 連結、
從 Word 貼上的雜亂樣式……）全部拿掉。

舊公告是純文字（不以 `<` 開頭），顯示時跳脫後一行轉成一個段落，不會被當成 HTML。
"""
import re

import nh3
from django.utils.html import escape
from django.utils.safestring import mark_safe

ALLOWED_TAGS = {'p', 'br', 'strong', 'em', 'u', 's', 'span', 'ol', 'ul', 'li', 'a'}
# 字級 class 與顏色 style 會掛在「最外層的行內標籤」上：只有顏色時是 <span>，
# 同時有底線／粗體時 Quill 直接寫成 <u class="ql-size-large" style="color: …">，所以行內標籤都要放行
_INLINE_ATTRS = {'class', 'style'}
ALLOWED_ATTRIBUTES = {
    'p': {'class'},
    'li': {'class', 'data-list'},
    'span': _INLINE_ATTRS,
    'strong': _INLINE_ATTRS,
    'em': _INLINE_ATTRS,
    'u': _INLINE_ATTRS,
    's': _INLINE_ATTRS,
    'a': {'href'} | _INLINE_ATTRS,
}

# 只放行工具列做得出來的 class：字級、對齊、縮排，以及 Quill 清單符號的佔位 span
_ALLOWED_CLASS = re.compile(
    r'^ql-(?:size-(?:small|large|huge)|align-(?:center|right|justify)|indent-[1-8]|ui)$'
)
_ALLOWED_DATA_LIST = {'bullet', 'ordered'}
# 只放行文字顏色與底色，值只接受 #hex 或 rgb()/rgba()
_STYLE_DECL = re.compile(
    r'^\s*(color|background-color)\s*:\s*'
    r'(#[0-9a-fA-F]{3,8}|rgba?\(\s*[\d.\s,%]+\))\s*$'
)


def _attribute_filter(tag, attr, value):
    if attr == 'class':
        kept = [c for c in value.split() if _ALLOWED_CLASS.match(c)]
        return ' '.join(kept) or None
    if attr == 'style':
        kept = []
        for decl in value.split(';'):
            m = _STYLE_DECL.match(decl)
            if m:
                kept.append(f'{m.group(1)}: {m.group(2).strip()}')
        return '; '.join(kept) or None
    if attr == 'data-list':
        return value if value in _ALLOWED_DATA_LIST else None
    return value


def sanitize_html(raw):
    """把編輯器送來的 HTML 過濾成只剩白名單格式。"""
    return nh3.clean(
        raw or '',
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        attribute_filter=_attribute_filter,
        url_schemes={'http', 'https', 'mailto'},
        link_rel='noopener noreferrer',
        strip_comments=True,
    )


def is_rich(content):
    """新格式（HTML）以 `<` 開頭；舊公告是純文字。"""
    return (content or '').lstrip().startswith('<')


def clean_content(raw):
    """存檔前的處理：HTML 過濾白名單；純文字（瀏覽器沒跑 JS 時）原樣保留，顯示時再跳脫。"""
    raw = (raw or '').strip()
    return sanitize_html(raw).strip() if is_rich(raw) else raw


def plain_text(html):
    """取出 HTML 的純文字，用來判斷「內容是不是空的」（Quill 空白時會送 <p><br></p>）。"""
    text = nh3.clean(html or '', tags=set())
    return text.replace('&nbsp;', ' ').strip()


def render_content(content):
    """給模板用：新格式過濾後輸出 HTML，舊純文字跳脫後換行轉段落。"""
    if is_rich(content):
        return mark_safe(sanitize_html(content))
    # 舊純文字：比照 Quill 的寫法，一行一個 <p>、空行是 <p><br></p>，
    # 這樣顯示時的空行間距與在編輯器裡打開時一致
    lines = (content or '').replace('\r\n', '\n').split('\n')
    return mark_safe(''.join(f'<p>{escape(line) or "<br>"}</p>' for line in lines))
