# 測試說明

本文件說明如何執行測試、目前的測試覆蓋範圍，以及新增測試的慣例。

> 最後更新：2026-08-08（共 450 個測試）

---

## 目錄

1. [執行測試](#執行測試)
2. [測試資料庫](#測試資料庫)
3. [目前測試總覽](#目前測試總覽)
4. [測試策略說明](#測試策略說明)
5. [新增測試的慣例](#新增測試的慣例)
6. [尚未覆蓋的功能](#尚未覆蓋的功能)

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

### 測試被中斷後，下次卡在「要不要刪除測試資料庫」

若上一次測試被中途強制中斷（關掉終端、背景工作被 kill、session teardown），`test_fjcwo`
可能沒被清乾淨而殘留。下次跑測試時 Django 會停下來互動詢問：

```
Type 'yes' if you would like to try deleting the test database 'test_fjcwo', or 'no' to cancel:
```

在無法互動的環境（背景執行、CI）這會直接 `EOFError` 中止，測試根本沒跑到。
加上 `--noinput` 讓它自動刪掉殘留的舊測試庫再重建即可：

```bash
python manage.py test --noinput
```

---

## 目前測試總覽

共 **450 個測試**，分布在 8 個 app。

### `apps/accounts/tests.py`（112 個）

| Class | 測試內容 |
|-------|---------|
| `LoginLogoutTest` | 登入頁存取、正確/錯誤帳密、session 建立與清除、登出導向 |
| `ProfileTest` | 個人資料頁存取控制、顯示姓名、POST 更新儲存 |
| `MemberDirectoryTest` | 通訊錄存取控制、電話/email 可見性（member vs officer）、admin 不顯示、依姓名搜尋、預設隱藏已退團、status=inactive 篩選、一般團員無法使用狀態篩選 |
| `MemberEditTest` | 存取控制（未登入/他人/幹部）、GET 預先帶入既有資料、POST 更新成功、幹部可升級為幹部角色、一般幹部不可授予管理員角色（僅管理員本身可以）、404 |
| `MemberStatusTest` | 幹部可退團／恢復、退團不刪除資料、不能將自己標記退團、一般團員無法操作他人狀態 |
| `MemberDeleteTest` | 無關聯紀錄的帳號可真正刪除、有關聯紀錄（如出席）的帳號擋下並保留、不能刪除自己、一般團員無法刪除他人、管理員／superuser 可強制刪除有關聯紀錄的帳號、PROTECT 關聯（如發過公告）即使管理員也無法繞過 |
| `UserRoleTest` | `is_officer` 各角色行為（member/officer/admin/superuser）、`is_staff` 與 `is_superuser` 自動設定 |
| `RegistrationTest` | 校友報到申請（公開存取、重複申請防止、送出建立紀錄）、狀態查詢（用 email 查）、幹部審核（核准/拒絕）、核准同步建立 User 帳號（含 must_change_password）、寄送臨時密碼信件、Email 重複時擋下不建立重複帳號 |
| `RegistrationManageTest` | 依姓名/Email 搜尋、依狀態篩選、拒絕可重新開放審核（核准不行）、新增申請紀錄（幹部限定）、編輯基本資料（不影響審核狀態）、刪除申請紀錄（已核准者不可刪除，一般團員不可操作）|
| `MemberCreateTest` | 存取控制（未登入/一般團員/幹部）、POST 新增團員成功（角色固定 member）、帳號依 Email 自動產生、Email 重複不建立記錄、寄送臨時密碼信件 |
| `ForcePasswordChangeTest` | `must_change_password` 使用者任何頁面都被導向設定密碼頁、一般使用者不受影響、設定密碼頁本身不被攔截、成功設定後清除 flag 並可用新密碼登入、密碼不一致/太弱被擋、臨時密碼登入後仍被導向設定密碼頁（含錯誤密碼登入失敗的驗證）|
| `MemberDirectoryReportTest` | 通訊錄列印報表：存取控制（未登入/一般團員無權限含電話Email→導回通訊錄/幹部可看）、顯示姓名電話Email、依樂器族群分組、列印按鈕、status 篩選（預設在團排除退團、inactive、all）|
| `GuestManageTest` | 客座團員（槍手）管理：存取控制、CRUD（新增設 role=guest／不可登入／空 email 存 NULL、姓名必填、email 重複擋、編輯、刪除）、轉正（改 member／補 email／開通登入／強制改密碼、缺 email 擋）、資安（guest 即使有密碼也被登入表單擋、通訊錄排除 guest、guest 列表顯示）|

### `apps/events/tests.py`（124 個）

| Class | 測試內容 |
|-------|---------|
| `LeaveRequestTestCase` | 請假申請的存取控制、空白/空白原因被擋、正常送出、重複申請防止、我的紀錄、幹部審核（核准/拒絕）、核准後同步出席紀錄、核准不覆寫已簽到的 PRESENT 紀錄、核准/拒絕後 result_seen 設為 False、刪除請假紀錄限管理員 |
| `PerformanceLeaveRequestTestCase` | 演出請假（比照排練請假）：存取控制、空白原因被擋、正常送出、重複申請防止、過期演出 server-side 阻擋、我的紀錄含演出請假、幹部審核（核准/拒絕）、核准標記 PerformanceAttendance.on_leave 且不覆寫既有 confirmed、已審核不可重複操作、刪除限管理員、活動詳情頁演出請假捷徑（未來顯示/過去停用）|
| `EventViewsTest` | 演出活動列表/詳情、排練詳情、摘要/備註顯示、申請請假按鈕（未來啟用/過去停用）、活動詳情頁請假捷徑連結（未來顯示/過去不顯示）|
| `QRCodeTest` | QR 管理頁存取控制、產生 token、重新產生換 UUID、小時數邊界、停用/啟用 toggle、簽到頁顯示、已簽到提示、簽到確認建立出席紀錄 |
| `SetlistManageTest` | 曲目管理存取控制、新增總譜成功、新增分譜被擋（404）、重複順序被擋、移除曲目 |
| `AttendanceReportTest` | 存取控制（未登入/一般團員/幹部）、404、出席/請假/無紀錄分類計數、個人出席率計算 |
| `LeaveStatsTest` | 存取控制、預設最新活動、排練層計數（核准/待審）、個人層出現、按總次數遞減排序 |
| `LeaveRequestPastRehearsalTest` | 直接 POST 到已結束排練的請假 URL 應被 server-side 阻擋 |
| `EventManageTest` | 存取控制（未登入/團員/幹部）、新增演出活動成功、空名稱被擋、已取消活動不出現在列表（role=admin 仍看得到）、編輯活動更新資料庫、不存在 pk 回 404 |
| `EventDeleteTest` | 團員/幹部無法刪除、GET 不刪除、管理員 POST 刪除並導回列表、刪除 cascade 排練、刪除按鈕在列表頁與詳情頁皆出現（管理員可見/幹部不可見）|
| `RehearsalManageTest` | 存取控制（未登入/團員/幹部）、新增排練成功、重複 sequence 被擋、空日期被擋、編輯排練更新 sequence |

### `apps/scores/tests.py`（73 個）

| Class | 測試內容 |
|-------|---------|
| `ScoreModelValidationTest` | `clean()` 驗證：總譜不可有樂器/聲部/full_score、分譜的 full_score 必須指向總譜；`__str__` 格式（含聲部/不含聲部/總譜） |
| `ScoreListViewTest` | 存取控制、預設顯示全部、`type` 篩選、`instrument` 篩選、關鍵字搜尋、無結果空狀態、分譜顯示已綁定/未綁定總譜、刪除按鈕限管理員可見 |
| `ScoreDetailViewTest` | 存取控制、曲名/作曲顯示、404、無 PDF 顯示提示、麵包屑帶/不帶篩選條件連回列表 |
| `ScoreCreateViewTest` | 存取控制（未登入/一般團員/幹部）、POST 新增總譜成功並導向詳情頁、POST 新增分譜（含樂器）成功、空曲名不建立記錄、分譜缺樂器不建立記錄、新增分譜時指定 full_score 正確綁定、總譜忽略殘留的 full_score 值 |
| `ScoreEditViewTest` | 存取控制（未登入/一般團員/幹部）、GET 既有資料預先帶入欄位、404、POST 更新成功、空曲名不更新、未上傳新檔案保留原檔、上傳新檔案取代原檔、編輯分譜可綁定/更新 full_score |
| `ScoreDeleteViewTest` | 一般幹部無法刪除、管理員可刪除並導向列表、刪除總譜連帶刪除分譜（CASCADE）、被 Setlist 或 ScoreExchangeItem 引用（PROTECT）時即使管理員也無法刪除 |
| `ScoreDownloadViewTest` | 存取控制、無 PDF 回 404、無效 pk 回 404 |
| `ScorePartsManageTest` | 存取控制（未登入/一般團員/幹部）、分譜 pk 回 404、無效 pk 回 404、POST 建立分譜記錄、重複上傳不重複建立（get_or_create）、POST 無檔案顯示警告 |
| `PerformancePartsViewTest` | 演出分譜下載入口：存取控制（未登入/登入）、無效演出 pk 回 404、依登入者樂器族群篩選（列出同族群、排除他族群）、非本場曲目的分譜排除、未設族群顯示提示、無對應分譜顯示空狀態 |

### `apps/assets/tests.py`（9 個）

| Class | 測試內容 |
|-------|---------|
| `BorrowStatusReportTest` | 存取控制、空狀態訊息、借出中財產顯示、已還財產不顯示、逾期標記（overdue flag）、未到期不標記、overdue_count 正確計算 |

### `apps/finance/tests.py`（71 個）

| Class | 測試內容 |
|-------|---------|
| `MembershipFeeReportTest` | 存取控制、無期別時提示新增期別、預設最新期別、GET（期別 pk）切換、已繳/待確認/未繳/作廢(視為無紀錄)/無紀錄分類計數、rows 涵蓋活躍非 admin 團員、槍手排除 |
| `FeePeriodTest` | 會費期別主檔 CRUD：存取控制（團員無權限/幹部可看）、新增、同年份+期別重複被擋、金額 0 被擋、編輯、刪除限管理員（幹部擋下/管理員可刪）、已有繳費紀錄時 PROTECT 擋下 |
| `FeeReportTest` | 團員自助申報（P2 現金 / P4 轉帳）：我的會費列期別/可申報、現金申報建 reported（記收款幹部、金額快照）、缺收款幹部被擋、轉帳申報記末五碼(無收款幹部)、末五碼非 5 位數字被擋、已申報/已繳不可重複、作廢後可重新申報、撤回自己的待確認、不可撤回已繳/他人 |
| `PaymentConfigTest` | 轉帳收款設定（P4）：存取控制（團員無權限/幹部可看）、儲存結構化欄位（代號/名稱/戶名/帳號）到單例設定、帳號存檔自動去除 dash 與空白 |
| `FeeReviewTest` | 幹部確認/作廢（P2）：存取控制、確認→已繳(記 paid_at、result_seen=False、金額再快照)、作廢→void、已處理不可重複、管理員可硬刪/一般幹部不可刪 |
| `FeeIncomeTest` | 確認繳費自動入帳（P3）：確認→產生會費收入(金額/日期=收款日、連結 finance_record)、作廢待確認不產生收入、幹部代登記已繳也入帳、已繳改未繳連動移除收入、管理員硬刪連動刪收入 |
| `AnnualReportTest` | 當年度收支（P3）：存取控制、預設最新年度、當年收入/支出/結餘彙總（跨年不計入）、確認繳費的會費收入計入當年度 |
| `FinanceRecordCRUDTest` | 收支明細：存取控制（未登入/團員/幹部）、新增（登記者自動帶入）、amount 0/負數/缺說明被擋、編輯、刪除限管理員（幹部擋下、管理員可刪）、列表收入/支出/結餘摘要 |
| `FeeEditTest` | 會費登記（幹部代登記）：一般團員無權限、登記已繳（status=paid、設 paid_at 與收款幹部）、未繳（status=unpaid、兩者為空）、金額一律自期別快照（不受表單影響）、同 member+period 再登記更新不重複、缺團員/期別被擋 |

### `apps/announcements/tests.py`（23 個）

| Class | 測試內容 |
|-------|---------|
| `AnnouncementListTest` | 未登入只見公開、團員見公開+團員限定、幹部見全部已發布、所有人看不到草稿 |
| `AnnouncementDetailTest` | 未登入可看公開詳情、團員看幹部限定回 404、幹部可看幹部限定、草稿對所有人回 404 |
| `AnnouncementManageTest` | 存取控制（未登入/團員/幹部）、管理頁顯示草稿 |
| `AnnouncementCreateTest` | 幹部新增成功（預設草稿）、空標題/空內容被擋 |
| `AnnouncementEditTest` | 幹部可編輯、無效輸入不儲存 |
| `AnnouncementPublishTest` | 發布草稿設定 published_at、取消發布清除 published_at |
| `AnnouncementDeleteTest` | 幹部可刪除、GET 請求不刪除 |

### `apps/notifications/tests.py`（4 個）

| Class | 測試內容 |
|-------|---------|
| `PushLineMessageTest` | credentials 齊全時發出 API 請求、TOKEN 缺少時略過、GROUP_ID 缺少時略過、API 失敗時 silent fail |

### `apps/public/tests.py`（34 個）

| Class | 測試內容 |
|-------|---------|
| `IndexDashboardLeaveResultTest` | 首頁顯示未讀的核准/拒絕請假結果、待審核不顯示為結果、看過一次後 result_seen 變 True、已讀結果不再顯示、不會看到其他團員的結果 |
| `PublicPagesTest` | 首頁、關於百韻、章程三頁面的 200 回應與不需登入；章程有內容時顯示、無內容時顯示佔位文字 |
| `CharterEditTest` | 存取控制（未登入/一般團員/幹部）、POST 儲存章程並 redirect、二次更新不新增資料 |
| `VenueManageTest` | 存取控制（未登入/一般團員/幹部）、依名稱搜尋、依類別篩選、新增/編輯場地、新增/刪除時段、刪除限管理員、被演出活動引用（PROTECT）時即使管理員也無法刪除 |

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
- **Phase 3 未實作的功能**（meetings、notifications）

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
| `public` | `about_manage` / `about_create` / `about_edit` / `about_delete` | 關於百韻內容管理，尚無自動測試 |
| `scores` | `score_list` 未過濾屬於總譜的分譜 | 分譜目前仍出現在列表，無對應測試 |
| `scores` | 上傳時的伺服器端 PDF 格式驗證 | 目前僅靠 HTML `accept=".pdf"` 限制 |
| `meetings` | 所有功能 | Phase 3，尚未實作 |
| `notifications` | Admin 觸發通知的整合測試 | 需要 mock Admin save_model，目前僅覆蓋 utils 層 |
