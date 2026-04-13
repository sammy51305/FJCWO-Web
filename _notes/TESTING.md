# 測試說明

本文件說明如何執行測試、目前的測試覆蓋範圍，以及新增測試的慣例。

> 最後更新：2026-04-14（共 155 個測試）

---

## 執行測試

### 執行全部測試

```bash
python manage.py test
```

### 執行特定 app 的測試

```bash
python manage.py test apps.events
python manage.py test apps.accounts
python manage.py test apps.scores
python manage.py test apps.assets
python manage.py test apps.finance
```

### 執行特定 Test class

```bash
python manage.py test apps.events.tests.QRCodeTest
```

### 執行單一 test method

```bash
python manage.py test apps.events.tests.QRCodeTest.test_qr_generate_creates_token
```

### 顯示詳細輸出

```bash
python manage.py test --verbosity=2
```

### 自動產生測試結果報告

```bash
python manage.py test_report
```

結果輸出至 `_notes/TEST_RESULTS.md`，包含每個測試的通過狀態與執行時間。

---

## 測試資料庫

Django 測試框架會自動建立一個獨立的測試資料庫（名稱為 `test_fjcwo`），
測試結束後自動刪除。**不會影響開發用的 `fjcwo` 資料庫。**

`fjcwo_user` 需要 `CREATEDB` 權限，詳見 [SETUP.md](SETUP.md) 步驟三。

---

## 目前測試總覽

共 **155 個測試**，分布在 6 個 app。

### `apps/accounts/tests.py`（36 個）

| Class | 測試內容 |
|-------|---------|
| `LoginLogoutTest` | 登入頁存取、正確/錯誤帳密、session 建立與清除、登出導向 |
| `ProfileTest` | 個人資料頁存取控制、顯示姓名、POST 更新儲存 |
| `MemberDirectoryTest` | 通訊錄存取控制、電話/email 可見性（member vs officer）、admin 不顯示 |
| `UserRoleTest` | `is_officer` 各角色行為（member/officer/admin/superuser）、`is_staff` 自動設定 |
| `RegistrationTest` | 校友報到申請（公開存取、重複申請防止、送出建立紀錄）、狀態查詢（用 email 查）、幹部審核（核准/拒絕）|

### `apps/events/tests.py`（73 個）

| Class | 測試內容 |
|-------|---------|
| `LeaveRequestTestCase` | 請假申請的存取控制、空白/空白原因被擋、正常送出、重複申請防止、我的紀錄、幹部審核（核准/拒絕）、核准後同步出席紀錄 |
| `EventViewsTest` | 演出活動列表/詳情、排練詳情、摘要/備註顯示、申請請假按鈕（未來啟用/過去停用）|
| `QRCodeTest` | QR 管理頁存取控制、產生 token、重新產生換 UUID、小時數邊界、停用/啟用 toggle、簽到頁顯示、已簽到提示、簽到確認建立出席紀錄 |
| `SetlistManageTest` | 曲目管理存取控制、新增總譜成功、新增分譜被擋（404）、重複順序被擋、移除曲目 |
| `AttendanceReportTest` | 存取控制（未登入/一般團員/幹部）、404、出席/請假/無紀錄分類計數、個人出席率計算 |
| `LeaveStatsTest` | 存取控制、預設最新活動、排練層計數（核准/待審）、個人層出現、按總次數遞減排序 |
| `LeaveRequestPastRehearsalTest` | 直接 POST 到已結束排練的請假 URL 應被 server-side 阻擋 |

### `apps/scores/tests.py`（21 個）

| Class | 測試內容 |
|-------|---------|
| `ScoreModelValidationTest` | `clean()` 驗證：總譜不可有樂器/聲部、分譜必須有樂器 |
| `ScoreListViewTest` | 存取控制、預設顯示全部、`type` 篩選、`instrument` 篩選、關鍵字搜尋、無結果空狀態 |
| `ScoreDetailViewTest` | 存取控制、曲名/作曲顯示、404、無 PDF 顯示提示 |
| `ScoreDownloadViewTest` | 存取控制、無 PDF 回 404、無效 pk 回 404 |

### `apps/assets/tests.py`（9 個）

| Class | 測試內容 |
|-------|---------|
| `BorrowStatusReportTest` | 存取控制、空狀態訊息、借出中財產顯示、已還財產不顯示、逾期標記（overdue flag）、未到期不標記、overdue_count 正確計算 |

### `apps/finance/tests.py`（10 個）

| Class | 測試內容 |
|-------|---------|
| `MembershipFeeReportTest` | 存取控制、無期別時顯示提示、預設最新期別、GET 切換期別、已繳/未繳/無紀錄三種狀態分類計數、rows 涵蓋全體活躍非 admin 團員 |

### `apps/public/tests.py`（6 個）

| Class | 測試內容 |
|-------|---------|
| `PublicPagesTest` | 首頁、關於我們、團則三頁面的 200 回應與不需登入 |

---

## 測試策略說明

### 我們測什麼

- **存取控制**：未登入導向登入頁、非幹部被擋並導回適當頁面
- **功能邏輯**：建立/更新/查詢資料庫紀錄的行為是否符合預期
- **UI 文字**：頁面有沒有出現應有的文字（或不該出現的文字）
- **Model 驗證**：`clean()` 在錯誤輸入時是否拋出 `ValidationError`
- **Context 資料**：view 傳給 template 的資料結構是否正確（統計數字、排序等）

### 我們不測什麼

- **Django 框架本身**（路由解析、ORM 查詢語法等）
- **靜態資源載入**（CSS / JS）
- **管理後台**（Django Admin 由框架負責，不另寫測試）
- **Phase 3 未實作的功能**（meetings、announcements views）

---

## 新增測試的慣例

### 檔案位置

每個 app 的測試都在同一支 `tests.py` 裡：

```
apps/
├── accounts/tests.py
├── events/tests.py
├── scores/tests.py
├── assets/tests.py
├── finance/tests.py
└── public/tests.py
```

### 命名

```python
class FeatureNameTest(TestCase):
    """功能的中文說明"""

    def test_具體行為描述(self):
        """這個測試在驗證什麼（一句話）"""
```

- Class 名稱：`功能名稱 + Test` 或 `功能名稱 + TestCase`
- Method 名稱：`test_` 開頭，描述**具體的行為**，而非「test_case_1」
- docstring：說明這個測試在驗證什麼

### 結構

每個測試 class 用 `setUp` 建立共用資料，避免每個 test method 重複建資料：

```python
class MyTest(TestCase):

    def setUp(self):
        # 建立測試用的 user、venue、event 等
        self.member = User.objects.create_user(...)
        self.url = reverse('events:some_view')

    def test_something(self):
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
```

### 常用斷言

```python
self.assertEqual(r.status_code, 200)           # 狀態碼
self.assertRedirects(r, url)                    # 導向（預設也驗證目標頁 200）
self.assertRedirects(r, url, fetch_redirect_response=False)  # 只驗導向，不跟進
self.assertContains(r, '某段文字')               # 頁面含此文字
self.assertNotContains(r, '某段文字')            # 頁面不含此文字
self.assertTrue(QuerySet.exists())              # 資料存在
self.assertFalse(QuerySet.exists())             # 資料不存在
self.assertEqual(QuerySet.count(), N)           # 資料筆數
self.assertRaises(ValidationError, fn)          # 拋出例外
obj.refresh_from_db(); self.assertEqual(...)    # 驗證資料庫更新後的值
r.context['key']                                # 直接驗證 view 傳給 template 的 context
```

### 驗證 context 資料的寫法

報表類 view 的核心邏輯通常是計算 context 裡的統計數字，直接驗證比 `assertContains` 更精準：

```python
def test_present_count_correct(self):
    RehearsalAttendance.objects.create(rehearsal=self.rehearsal, member=self.member,
                                       status='present')
    self.client.force_login(self.officer)
    r = self.client.get(self.url)
    rehearsals = r.context['rehearsals']
    self.assertEqual(rehearsals[0].stats['present'], 1)
```

### 驗證 Model clean() 的寫法

```python
def test_invalid_state_raises(self):
    score = Score(title='test', score_type=Score.ScoreType.FULL, instrument=some_inst)
    with self.assertRaises(ValidationError):
        score.clean()
```

注意：`clean()` 不會在 `Score.objects.create()` 時自動觸發，
只有透過 Django Form 或手動呼叫 `full_clean()` 才會執行。
直接呼叫 `clean()` 是最直接的單元測試方式。

---

## 尚未覆蓋的功能

下列功能目前**沒有測試**，開發時需要人工測試：

| App | 功能 | 說明 |
|-----|------|------|
| `announcements` | 所有功能 | 僅有 Model，尚無 views |
| `meetings` | 所有功能 | Phase 3，尚未實作 |
| `notifications` | 所有功能 | LINE Bot，Phase 2 待做 |
