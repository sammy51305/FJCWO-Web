import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

_LINE_PUSH_URL = 'https://api.line.me/v2/bot/message/push'
_WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']


def push_line_message(text: str) -> None:
    token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')
    group_id = os.environ.get('LINE_GROUP_ID', '')
    if not token or not group_id:
        logger.warning('LINE notification skipped: TOKEN or GROUP_ID not set')
        return

    payload = json.dumps({
        'to': group_id,
        'messages': [{'type': 'text', 'text': text}],
    }).encode('utf-8')

    req = urllib.request.Request(
        _LINE_PUSH_URL,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception as e:
        logger.warning('LINE notification failed: %s', e)


def fmt_dt(dt) -> str:
    weekday = _WEEKDAYS[dt.weekday()]
    return dt.strftime(f'%Y/%m/%d（週{weekday}）%H:%M')
