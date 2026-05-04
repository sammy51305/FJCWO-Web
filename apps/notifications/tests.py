from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.notifications.utils import push_line_message


class PushLineMessageTest(TestCase):

    @patch.dict('os.environ', {
        'LINE_CHANNEL_ACCESS_TOKEN': 'test-token',
        'LINE_GROUP_ID': 'test-group',
    })
    @patch('apps.notifications.utils.urllib.request.urlopen')
    def test_sends_request_when_credentials_set(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        push_line_message('測試訊息')
        mock_urlopen.assert_called_once()

    @patch.dict('os.environ', {
        'LINE_CHANNEL_ACCESS_TOKEN': '',
        'LINE_GROUP_ID': 'test-group',
    })
    @patch('apps.notifications.utils.urllib.request.urlopen')
    def test_skips_when_token_missing(self, mock_urlopen):
        push_line_message('測試訊息')
        mock_urlopen.assert_not_called()

    @patch.dict('os.environ', {
        'LINE_CHANNEL_ACCESS_TOKEN': 'test-token',
        'LINE_GROUP_ID': '',
    })
    @patch('apps.notifications.utils.urllib.request.urlopen')
    def test_skips_when_group_id_missing(self, mock_urlopen):
        push_line_message('測試訊息')
        mock_urlopen.assert_not_called()

    @patch.dict('os.environ', {
        'LINE_CHANNEL_ACCESS_TOKEN': 'test-token',
        'LINE_GROUP_ID': 'test-group',
    })
    @patch('apps.notifications.utils.urllib.request.urlopen', side_effect=Exception('timeout'))
    def test_silent_fail_on_error(self, mock_urlopen):
        push_line_message('測試訊息')
