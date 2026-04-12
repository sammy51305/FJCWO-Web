"""
manage.py test_report
=====================
跑所有測試並自動生成 _notes/TEST_RESULTS.md。

使用方式：
    python manage.py test_report
"""

import time
import unittest
from collections import defaultdict
from datetime import date
from pathlib import Path

import django
from django.core.management.base import BaseCommand
from django.test.runner import DiscoverRunner


# ── 自訂 TestResult：逐筆收集結果 ────────────────────────────
class _CollectingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.all_results = []
        self._t0 = None

    def startTest(self, test):
        super().startTest(test)
        self._t0 = time.time()

    def _record(self, test, status):
        elapsed = time.time() - (self._t0 or time.time())
        self.all_results.append({
            'module':  test.__class__.__module__,
            'class':   test.__class__.__name__,
            'method':  test._testMethodName,
            'desc':    test.shortDescription() or '',
            'status':  status,
            'elapsed': elapsed,
        })

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, 'PASS')

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, 'FAIL')

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, 'ERROR')

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, 'SKIP')


# ── 自訂 Runner：注入 resultclass ────────────────────────────
class _CollectingRunner(DiscoverRunner):
    """覆寫 run_suite，讓 Django 使用我們的 _CollectingResult。"""

    def run_suite(self, suite, **kwargs):
        runner_kwargs = self.get_test_runner_kwargs()
        runner_kwargs['resultclass'] = _CollectingResult
        runner = self.test_runner(**runner_kwargs)
        result = runner.run(suite)
        self._last_result = result
        return result


# ── Markdown 生成 ─────────────────────────────────────────────
_STATUS_EMOJI = {'PASS': '✅', 'FAIL': '❌', 'ERROR': '⚠️', 'SKIP': '⏭️'}

_APP_LABEL = {
    'apps.public.tests':   'apps.public',
    'apps.accounts.tests': 'apps.accounts',
    'apps.events.tests':   'apps.events',
}


def _generate_markdown(results, total_time):
    passed  = sum(1 for r in results if r['status'] == 'PASS')
    failed  = sum(1 for r in results if r['status'] == 'FAIL')
    errors  = sum(1 for r in results if r['status'] == 'ERROR')
    skipped = sum(1 for r in results if r['status'] == 'SKIP')
    total   = len(results)
    ok      = failed == 0 and errors == 0

    grouped = defaultdict(lambda: defaultdict(list))
    for r in results:
        grouped[r['module']][r['class']].append(r)

    import sys
    v = sys.version_info

    lines = []
    lines.append('# 測試結果紀錄')
    lines.append('')
    lines.append('> 此檔案由 `python manage.py test_report` 自動生成，請勿手動編輯。')
    lines.append('')
    lines.append('## 最新執行結果')
    lines.append('')
    lines.append('| 欄位 | 內容 |')
    lines.append('|------|------|')
    lines.append(f'| 執行日期 | {date.today().strftime("%Y-%m-%d")} |')
    lines.append(f'| Django 版本 | {django.__version__} |')
    lines.append(f'| Python 版本 | {v.major}.{v.minor}.{v.micro} |')
    lines.append(f'| 通過 / 總計 | {passed} / {total} |')
    lines.append(f'| 失敗 / 錯誤 / 跳過 | {failed} / {errors} / {skipped} |')
    lines.append(f'| 執行時間 | {total_time:.2f} 秒 |')
    lines.append(f'| 結論 | {"全部通過 ✅" if ok else "有測試失敗 ❌"} |')
    lines.append('')
    lines.append('## 測試套件詳細結果')
    lines.append('')

    for module, classes in sorted(grouped.items()):
        app_total  = sum(len(v) for v in classes.values())
        app_passed = sum(1 for v in classes.values() for r in v if r['status'] == 'PASS')
        label = _APP_LABEL.get(module, module)
        lines.append(f'### {label}（{app_passed}/{app_total}）')
        lines.append('')

        for classname, tests in sorted(classes.items()):
            lines.append(f'#### {classname}')
            lines.append('')
            lines.append('| 測試方法 | 說明 | 結果 | 時間 |')
            lines.append('|----------|------|------|------|')
            for r in tests:
                emoji = _STATUS_EMOJI.get(r['status'], r['status'])
                lines.append(
                    f"| `{r['method']}` | {r['desc']} "
                    f"| {emoji} {r['status']} | {r['elapsed']*1000:.0f} ms |"
                )
            lines.append('')

    return '\n'.join(lines)


# ── Management Command ────────────────────────────────────────
class Command(BaseCommand):
    help = '跑所有測試並將結果寫入 _notes/TEST_RESULTS.md'

    def handle(self, *args, **options):
        self.stdout.write('執行測試中...\n')

        runner = _CollectingRunner(verbosity=2)
        t_start = time.time()
        runner.run_tests([])   # 空 list = 自動探索全部 tests
        total_time = time.time() - t_start

        result = getattr(runner, '_last_result', None)
        if result is None:
            self.stderr.write('無法取得測試結果。')
            return

        all_results = result.all_results
        passed = sum(1 for r in all_results if r['status'] == 'PASS')
        total  = len(all_results)
        ok     = result.wasSuccessful()

        md = _generate_markdown(all_results, total_time)
        out_path = Path(__file__).resolve().parents[4] / '_notes' / 'TEST_RESULTS.md'
        out_path.write_text(md, encoding='utf-8')

        status_str = self.style.SUCCESS('全部通過') if ok else self.style.ERROR('有失敗')
        self.stdout.write(f'\n結果：{passed}/{total}  {status_str}')
        self.stdout.write(f'報告已寫入：{out_path}\n')
