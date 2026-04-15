# FJCWO-Web 設計邏輯說明

> 本文件說明 Phase 1 & 2 的設計決策、資料庫結構與各系統的運作邏輯。
> 目標讀者：接手開發或複習程式碼的人（包含自己）。
> 最後更新：2026-04-16（補充公告系統 views 設計）

---

## 目錄

1. [整體架構概念](#一整體架構概念)
2. [權限系統](#二權限系統)
3. [資料庫設計與 Model 關聯](#三資料庫設計與-model-關聯)
4. [各系統運作邏輯](#四各系統運作邏輯)
   - [公開頁面（public）](#41-公開頁面public)
   - [帳號與會員（accounts）](#42-帳號與會員accounts)
   - [場地管理（band_public）](#43-場地管理band_public)
   - [演出活動與排練（events）](#44-演出活動與排練events)
   - [QR Code 簽到（events）](#45-qr-code-簽到events)
   - [請假申請（events）](#46-請假申請events)
   - [財務管理（finance）](#47-財務管理finance)
   - [樂譜庫存（scores）](#48-樂譜庫存scores)
   - [公用財產與借用（assets）](#49-公用財產與借用assets)
   - [公告（announcements）](#410-公告announcements)
   - [首頁 Dashboard（public）](#411-首頁-dashboardpublic)
   - [演出曲目管理（events）](#412-演出曲目管理events)
   - [樂譜瀏覽與下載（scores）](#413-樂譜瀏覽與下載scores)
   - [報表：排練出席（events）](#414-報表排練出席events)
   - [報表：財產借用現況（assets）](#415-報表財產借用現況assets)
   - [報表：會費繳納狀況（finance）](#416-報表會費繳納狀況finance)
   - [報表：請假統計（events）](#417-報表請假統計events)

---

## 一、整體架構概念

### Django 的 MTV 模式

Django 把程式分成三層，對應到網站的不同職責：

```
瀏覽器發出請求
      ↓
  urls.py          ← 決定這個 URL 要交給哪個 view 處理
      ↓
  views.py         ← 商業邏輯（從資料庫拿資料、判斷權限）
      ↓
  models.py        ← 資料庫的定義與操作
      ↓
  templates/*.html ← 把資料填進 HTML，回傳給瀏覽器
```

### App 的分工

```
apps/
├── accounts/      會員登入、User 資料、通訊錄
├── public/        不需登入就能看的頁面（首頁、章程）+ Venue / VenueTimeSlot
├── events/        演出活動、排練、QR 簽到、請假
├── finance/       財務紀錄、會費
├── scores/        樂譜庫存、對外交換
├── assets/        公用財產、借用、樂器保養
└── announcements/ 公告
```

> **為什麼 Venue 放在 `public` app？**
> 場地資料（場地名稱、地址、交通）本身不涉及任何登入，且 `events` app 在建立
> 排練時需要關聯場地。為了避免循環引用（events 引用 public、public 又引用 events），
> 場地主檔放在較底層的 `public` app，讓上層的 events 單向引用它。

---

## 二、權限系統

### 三種角色

`User.role` 欄位有三個值：

| 值 | 顯示 | 說明 |
|----|------|------|
| `member` | 團員 | 一般會員，可查詢活動、申請請假、借用財產 |
| `officer` | 幹部 | 可管理 QR Code、審核請假、查看通訊錄 |
| `admin` | 管理員 | 等同幹部，另有 Django Admin 的完整控制權 |

### `is_officer` 屬性

`User` model 有一個 property：

```python
@property
def is_officer(self):
    return self.is_superuser or self.role in (self.Role.OFFICER, self.Role.ADMIN)
```

這個設計讓 views 和 templates 不需要同時判斷 `officer` 和 `admin`，
只要寫 `user.is_officer` 就能涵蓋兩種有管理權的角色。

`self.is_superuser` 也納入，確保 Django superuser 帳號能正常使用所有幹部功能。

### `User.save()` 與 `is_staff` 自動設定

```python
def save(self, *args, **kwargs):
    if self.is_superuser or self.role == self.Role.ADMIN:
        self.is_staff = True
    super().save(*args, **kwargs)
```

`is_staff=True` 才能進入 `/admin/` 後台。`admin` 角色和 superuser 需要這個權限，
所以在 `save()` 時自動設定，避免手動忘記勾選。

### 在 views 裡如何擋權限

```python
@login_required          # 未登入 → 轉到登入頁
def qr_manage(request, pk):
    if not request.user.is_officer:   # 非幹部 → 顯示錯誤並導回列表
        messages.error(request, '權限不足。')
        return redirect('events:event_list')
    ...
```

`@login_required` 只確保「有登入」，更細的角色檢查要在 view 裡自己寫。

### 在 templates 裡如何顯示/隱藏

```html
{% if user.is_officer %}
  <a href="...">QR 簽到管理</a>
{% endif %}
```

**注意**：template 的 `{% if %}` 只是隱藏 HTML，真正的安全防線還是 view 裡的檢查。
光靠 template 隱藏是不夠的，因為使用者可以直接輸入 URL。

---

## 三、資料庫設計與 Model 關聯

### 關聯圖（簡化版）

```
InstrumentType ←─── User ───→ SectionType
                      │
                      └──→ Registration（校友報到申請）

Venue ──→ VenueTimeSlot
  │
  ├── PerformanceEvent ──→ Setlist ──→ Score
  │         │                │
  │         │                └──→ PartAssignment ──→ User / GuestMember
  │         │
  │         └──→ Rehearsal ──→ RehearsalQRToken
  │                   │
  │                   ├──→ RehearsalAttendance ──→ User
  │                   └──→ LeaveRequest ──→ User
  │
  └── PerformanceAttendance ──→ User

FinanceRecord ──→ PerformanceEvent（選填）
               ──→ User（登記者）

Score ──→ Score（parent_score，版本鏈）
ScoreExchange ──→ ScoreExchangeItem ──→ Score

BandProperty ──→ AssetBorrow ──→ User
             └──→ InstrumentMaintenance ──→ User

Announcement ──→ User（發布者）
MembershipFee ──→ User（團員、收款幹部）
```

### 關鍵設計說明

#### ForeignKey 的刪除行為

Django ForeignKey 有幾種 `on_delete` 選項，本系統用到三種：

| 選項 | 說明 | 用在哪裡 |
|------|------|---------|
| `CASCADE` | 父資料刪掉，子資料一起刪 | 排練刪掉 → 出席紀錄、QR Token 一起刪 |
| `PROTECT` | 有子資料時不允許刪除父資料 | 場地有排練記錄時不能刪場地 |
| `SET_NULL` | 父資料刪掉，子資料的欄位設為 NULL | 幹部帳號刪掉，排練摘要的「填寫者」變空白 |

**為什麼 Venue 用 PROTECT？**
若幹部不小心刪了場地，歷史排練紀錄就會失去場地資訊。`PROTECT` 強迫使用者先處理掉關聯的排練，才能刪場地，防止誤刪。

#### `unique_together`

某些表設了組合唯一限制：

```python
# RehearsalAttendance：同一場排練，同一位團員只能有一筆紀錄
unique_together = [['rehearsal', 'member']]

# LeaveRequest：同一場排練，同一位團員只能申請一次請假
unique_together = [['member', 'rehearsal']]
```

這樣在 view 裡用 `get_or_create` 就不會重複建資料。

#### `settings.AUTH_USER_MODEL` 而非直接寫 `User`

```python
# 正確：用 settings.AUTH_USER_MODEL
created_by = models.ForeignKey(settings.AUTH_USER_MODEL, ...)

# 錯誤：直接 import User
from apps.accounts.models import User  # 不建議在 model 裡跨 app import
```

Django 官方建議用 `settings.AUTH_USER_MODEL`，因為 User model 可能被替換，
用設定檔的字串參考可以避免 app 之間的循環引用。

---

## 四、各系統運作邏輯

### 4.1 公開頁面（public）

**檔案**：`apps/public/views.py`、`templates/public/`

`about`、`rules` 兩支 view 只回傳靜態模板，沒有資料庫查詢。
`index`（首頁）對已登入者另外查詢個人化資料，詳見 [4.11 首頁 Dashboard](#411-首頁-dashboardpublic)。

---

### 4.2 帳號與會員（accounts）

**檔案**：`apps/accounts/models.py`、`apps/accounts/views.py`

#### 三支公開 View 的分工

| View | 路由 | 說明 |
|------|------|------|
| `registration_apply` | `GET/POST /accounts/register/` | 填寫申請表單，送出後建立 `Registration`（status=pending）|
| `registration_status` | `GET/POST /accounts/register/status/` | 輸入 Email 查詢自己的申請狀態，**不需登入** |
| `registration_review` | `GET/POST /accounts/register/review/` | 幹部審核，核准或拒絕申請，記錄 reviewed_by / reviewed_at |

`registration_status` 設計為公開頁面，讓申請者不需帳號就能確認申請進度，
避免對方不斷來電詢問。查詢以 Email 為鍵，列出該 Email 所有申請紀錄。

#### 為什麼要繼承 AbstractUser？

Django 內建的 User 只有 username / email / password，沒有「樂器」、「聲部」等欄位。
繼承 `AbstractUser` 可以在保留 Django 登入系統的前提下，自由新增欄位。

**重要**：自訂 User model 必須在**建立專案初期**設定好，之後改非常麻煩（會影響所有 migration）。

#### 登入流程

```
使用者 POST 帳號密碼
      ↓
BootstrapAuthenticationForm.is_valid()  ← Django 內建表單，加了 Bootstrap 樣式
      ↓
login(request, form.get_user())         ← Django 把使用者資訊存進 session
      ↓
redirect 到 ?next= 或首頁
```

#### 會員通訊錄的分組邏輯

```python
# 撈所有啟用中、非管理員的會員，依樂器分類排序
members = User.objects.filter(is_active=True).exclude(role=User.Role.ADMIN)
          .order_by('instrument__category', 'instrument__name', 'name')

# 用 dict 分組
grouped = {}
for member in members:
    category = member.instrument.get_category_display() if member.instrument else '未分類'
    grouped.setdefault(category, []).append(member)
```

`get_category_display()` 是 Django 自動加在 `TextChoices` 欄位上的方法，
可以把資料庫存的英文 key（如 `woodwind`）轉成中文顯示值（如 `木管`）。

---

### 4.3 場地管理（band_public）

**檔案**：`apps/public/models.py`（Venue、VenueTimeSlot）

#### 為什麼要有 VenueTimeSlot？

同一個場地在不同星期、不同時段的費用可能不同。
例如「世韻藝術」可能有三個時段：
- 週六 09:00–12:00，費用 3000
- 週六 13:00–17:00，費用 4000
- 週日 09:00–12:00，費用 2500

把時段拆出來，建立排練時只要選「哪個時段」，費用就自動帶入，不用每次重新輸入。

#### 星期的設計

```python
# 七個 Boolean 欄位，各自代表一天
is_sun = models.BooleanField('週日', default=False)
is_mon = models.BooleanField('週一', default=False)
...
```

這樣一個時段可以同時適用多天（例如週六＆週日都有同樣時段），
比存一個字串（"週六,週日"）更容易過濾查詢。

---

### 4.4 演出活動與排練（events）

**檔案**：`apps/events/models.py`、`apps/events/views.py`

#### 演出活動 vs 排練 的關係

```
PerformanceEvent（一場演出，例如「2026 年春季音樂會」）
    │
    ├── Rehearsal（第 1 次排練）
    ├── Rehearsal（第 2 次排練）
    └── Rehearsal（第 N 次排練）
```

一場演出有多次排練，用 ForeignKey 關聯。排練有 `sequence` 欄位記錄「第幾次」，
並設了 `unique_together = [['event', 'sequence']]`，確保同一場演出不會有兩個「第 3 次排練」。

#### 演出活動的狀態流程

```
planning（籌備中）→ confirmed（確認）→ finished（已結束）
```

`event_list` view 用這個狀態把活動分成「即將到來」和「已結束」兩區：

```python
upcoming = PerformanceEvent.objects.exclude(status='finished')
past     = PerformanceEvent.objects.filter(status='finished')
```

#### `select_related` 是什麼？

```python
rehearsals = event.rehearsals.select_related('venue').order_by('sequence')
```

若不用 `select_related`，每次在 template 裡存取 `rehearsal.venue.name`，
Django 就會多發一次 SQL 查詢。有 10 筆排練就多 10 次查詢（N+1 問題）。
`select_related` 告訴 Django 用 JOIN 一次把關聯資料一起撈回來，效能更好。

---

### 4.5 QR Code 簽到（events）

**檔案**：`apps/events/views.py`（`qr_manage`、`qr_generate`、`qr_toggle`、`qr_checkin`、`qr_checkin_confirm`）

#### 整體流程

```
幹部進入排練詳情頁 → 點「QR 簽到管理」
      ↓
qr_manage（GET）：顯示管理頁
      ↓（若尚未產生）
qr_generate（POST）：建立 RehearsalQRToken，生成 UUID token
      ↓
qr_manage 顯示 QR Code 圖片（編碼的是 /events/checkin/<token>/ 的完整網址）
      ↓
團員用手機掃描 QR Code
      ↓
qr_checkin（GET）：顯示簽到頁，確認 token 有效性
      ↓
qr_checkin_confirm（POST）：建立或更新 RehearsalAttendance（status=present）
      ↓
幹部在 qr_manage 頁即時看到出席名單
```

#### QR Code 圖片如何產生？

```python
import qrcode, io, base64

def _make_qr_data_url(url):
    img = qrcode.make(url)           # 產生 QR Code 圖片物件
    buf = io.BytesIO()               # 建立記憶體緩衝區（不寫入硬碟）
    img.save(buf, format='PNG')      # 把圖片存進緩衝區
    data = base64.b64encode(buf.getvalue()).decode()  # 轉成 base64 字串
    return f'data:image/png;base64,{data}'  # 回傳可直接放在 <img src> 的 Data URL
```

用 Data URL 的好處是不需要在 server 上儲存圖片檔，也不需要額外的路由，
圖片直接嵌在 HTML 裡回傳。缺點是圖片較大的話 HTML 會變很長，但 QR Code 圖片小，沒問題。

#### Token 有效性判斷

```python
def is_valid(self):
    return self.is_active and timezone.now() <= self.expires_at
```

兩個條件都要滿足才是有效的 token：
1. `is_active`：幹部沒有手動停用
2. 時間還沒過期

`timezone.now()` 而非 `datetime.now()`：前者是 timezone-aware（有時區資訊），後者是 naive（沒有時區）。PostgreSQL 存時間時需要 timezone-aware 才能正確比較。

#### 重新產生 token 時為什麼要換 UUID？

```python
qr_token.token = uuid.uuid4()  # 換一個新的隨機 UUID
qr_token.expires_at = expires_at
qr_token.is_active = True
qr_token.save()
```

舊的 QR Code 印出來或截圖的話，換了 UUID 就讓舊 QR Code 失效，
強迫大家使用新的。如果不換 UUID，重新產生只是延長了有效時間，舊 QR Code 仍可使用。

#### 簽到的冪等性（Idempotent）

```python
attendance, _ = RehearsalAttendance.objects.get_or_create(
    rehearsal=qr_token.rehearsal,
    member=request.user,
)
```

`get_or_create` 的意思是：有就拿，沒有就建立。
這樣團員不小心掃兩次也不會建出兩筆紀錄，只會更新第一筆的狀態。
這種「不管執行幾次結果都一樣」的設計稱為「冪等性」。

---

### 4.6 請假申請（events）

**檔案**：`apps/events/views.py`（`leave_request_create`、`my_leave_requests`、`leave_review_list`）

#### 三支 View 各自的職責

| View | 對象 | 功能 |
|------|------|------|
| `leave_request_create` | 所有團員 | 填寫請假原因，送出申請 |
| `my_leave_requests` | 所有團員 | 查看自己歷史申請的狀態 |
| `leave_review_list` | 幹部 | 審核待審的申請（核准 / 拒絕） |

#### 防止重複申請

```python
existing = LeaveRequest.objects.filter(member=request.user, rehearsal=rehearsal).first()
...
elif existing:
    messages.error(request, '您已提交過此次排練的請假申請。')
```

進頁面時先查資料庫有沒有已存在的申請，如果有，POST 時直接擋掉。
Model 層的 `unique_together` 是最後一道防線，但 view 層先擋才能給使用者友善的錯誤訊息。

#### `created_at` 欄位

```python
created_at = models.DateTimeField('申請時間', auto_now_add=True)
```

記錄申請送出的時間，方便幹部在審核頁面看到申請時序，也作為稽核軌跡。

#### 審核後的狀態流程

```
pending（待審核）
    ├── approved（核准）← 幹部按「核准」
    └── rejected（拒絕）← 幹部按「拒絕」
```

核准後，`reviewed_by` 和 `reviewed_at` 會一起記錄，留下稽核軌跡。

`leave_review_list` 在處理核准/拒絕動作前，會先確認申請狀態仍為 `pending`，
防止幹部透過瀏覽器上一頁重複送出，誤將已審核的申請再次翻轉。

---

### 4.7 財務管理（finance）

**檔案**：`apps/finance/models.py`

目前只有 Model + Admin，尚未做前端頁面。所有財務操作透過 Django Admin 進行。

#### 兩個 Model 的差異

| Model | 用途 |
|-------|------|
| `FinanceRecord` | 所有收入/支出明細，可關聯到某場演出 |
| `MembershipFee` | 專門追蹤每位團員每期會費的繳交狀況 |

**為什麼分開？**
MembershipFee 有「期別」的概念（如「2026 上半年」），且需要知道每個人有沒有繳，
這和一般的支出紀錄性質不同，拆開比較容易查詢「誰還沒繳費」。

---

### 4.8 樂譜庫存（scores）

**檔案**：`apps/scores/models.py`

#### 總譜 vs 分譜

```python
class ScoreType(models.TextChoices):
    FULL = 'full', '總譜'   # 指揮用，不需要填樂器
    PART = 'part', '分譜'   # 各樂器用，需要填樂器＋聲部
```

`instrument` 和 `section` 欄位設為 `null=True, blank=True`，
因為總譜不需要這兩個欄位，但分譜需要。

Model 層透過 `clean()` 驗證確保資料一致性：

```python
def clean(self):
    if self.score_type == self.ScoreType.FULL:
        if self.instrument or self.section:
            raise ValidationError('總譜不應指定樂器或聲部。')
    elif self.score_type == self.ScoreType.PART:
        if not self.instrument:
            raise ValidationError('分譜必須指定樂器。')
```

Django Admin 的表單會自動呼叫 `clean()`，確保透過後台輸入的資料也符合規則。

#### Setlist 只連結總譜

`Setlist.score` 外鍵指向 `Score`，view 層限制只能選 `score_type='full'` 的曲子：

```python
available_scores = Score.objects.filter(score_type=Score.ScoreType.FULL)
```

演出曲目只需要記錄「哪首曲子」，個別樂手用哪份分譜由 `PartAssignment` 負責。
把「曲目選擇」限制在總譜層面，讓 setlist 語意明確：一首曲子一個 item，不會因為分譜數量不同而重複列出。

#### 版本鏈設計

```python
parent_score = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
```

`ForeignKey('self', ...)` 是指向同一張表的外鍵，用來表達「改版自哪個版本」：

```
原版《天空之城》
    └── 改版 v1（加了長笛 ossia）
            └── 改版 v2（加了打擊聲部）
```

`on_delete=SET_NULL` 確保刪掉某個版本不會連鎖刪掉衍生版本，只是斷開關聯。

#### 對外交換的主從結構

```
ScoreExchange（一次交換事件，記錄對方樂團與聯絡人）
    ├── ScoreExchangeItem（這次交換：給出《天空之城》分譜）
    └── ScoreExchangeItem（這次交換：收入《卡門》總譜）
```

一次交換可能包含多首曲目，用主表 + 明細表拆開，比把所有樂譜塞在一個欄位更容易查詢與維護。

---

### 4.9 公用財產與借用（assets）

**檔案**：`apps/assets/models.py`

#### 設計理念：樂器只是財產的一種

過去管樂團常常只有「樂器借用登記本」，但其他公用物品（譜架、音響設備、制服）也需要管理。
系統把所有物品統一放在 `BandProperty`，用 `category` 區分類別：

```python
class Category(models.TextChoices):
    INSTRUMENT = 'instrument', '樂器'
    STAND = 'stand', '譜架'
    AUDIO = 'audio', '音響設備'
    UNIFORM = 'uniform', '制服'
    OTHER = 'other', '其他'
```

#### 如何判斷是否已歸還？

```python
@property
def is_returned(self):
    return self.returned_at is not None
```

`returned_at` 為空 = 尚未歸還；有日期 = 已歸還。
不另外設 boolean 欄位，因為日期本身就是最好的狀態指標，也記錄了「何時」歸還。

#### 樂器保養為何獨立成表？

`InstrumentMaintenance` 只對 `BandProperty` 裡 `category=instrument` 的資料有意義，
但 Django 不原生支援「conditional foreign key」，所以用獨立表 + 應用層確保只關聯樂器。
其他財產的保養可暫時用 `BandProperty.notes` 欄位記錄文字。

---

### 4.10 公告（announcements）

**檔案**：`apps/announcements/models.py`、`views.py`、`urls.py`

#### 三層可見範圍

```python
class Visibility(models.TextChoices):
    PUBLIC = 'public', '公開'             # 所有人（包含未登入）
    MEMBER_ONLY = 'member_only', '團員限定'  # 需登入
    OFFICER_ONLY = 'officer_only', '幹部限定' # 需幹部角色
```

各身份可見的公告類型：

| 身份 | 公開 | 團員限定 | 幹部限定 | 草稿 |
|------|:---:|:---:|:---:|:---:|
| 未登入 | ✅ | ✗ | ✗ | ✗ |
| 團員 | ✅ | ✅ | ✗ | ✗ |
| 幹部 | ✅ | ✅ | ✅ | 管理頁可見 |

草稿對所有人的詳情頁都回 404，幹部只能在管理頁看到草稿清單。

#### 草稿 vs 已發布

`published_at` 為空 = 草稿，尚未對外顯示。
有時間戳 = 已發布，且這個時間戳就是「發布時間」，不需要另一個 boolean 欄位。

```python
@property
def is_published(self):
    return self.published_at is not None
```

#### 可見性過濾邏輯（`_visible_announcements`）

列表頁與詳情頁共用同一個 helper 函式，確保兩處規則一致、不重複：

```python
def _visible_announcements(user):
    qs = Announcement.objects.filter(published_at__isnull=False)
    if not user.is_authenticated:
        return qs.filter(visibility=Announcement.Visibility.PUBLIC)
    if user.is_officer:
        return qs
    return qs.exclude(visibility=Announcement.Visibility.OFFICER_ONLY)
```

詳情頁直接對這個 QuerySet 做 `get_object_or_404`，無需再重複寫可見性判斷。

#### URL 結構

| URL | View | 存取限制 |
|-----|------|---------|
| `/announcements/` | `announcement_list` | 公開 |
| `/announcements/<pk>/` | `announcement_detail` | 依可見性 |
| `/announcements/manage/` | `announcement_manage` | 幹部 |
| `/announcements/create/` | `announcement_create` | 幹部 |
| `/announcements/<pk>/edit/` | `announcement_edit` | 幹部 |
| `/announcements/<pk>/delete/` | `announcement_delete` | 幹部（POST only）|
| `/announcements/<pk>/publish/` | `announcement_publish` | 幹部（POST only）|

---

### 4.11 首頁 Dashboard（public）

**檔案**：`apps/public/views.py`（`index`）

首頁對**未登入者**顯示靜態內容；對**已登入者**額外查詢三筆資料，組成個人化 Dashboard：

```python
# 下次排練：最近一場日期 > 現在的排練
context['next_rehearsal'] = (
    Rehearsal.objects
    .filter(date__gt=timezone.now())
    .select_related('event', 'venue')
    .order_by('date')
    .first()
)

# 我的待審請假（提醒團員有哪些申請尚未被幹部處理）
context['pending_leaves'] = (
    LeaveRequest.objects
    .filter(member=request.user, status=LeaveRequest.Status.PENDING)
    .select_related('rehearsal__event')
    .order_by('rehearsal__date')
)

# 幹部專屬：待審核的校友報到申請數（顯示提醒徽章）
if request.user.is_officer:
    context['pending_registrations_count'] = (
        Registration.objects.filter(status=Registration.Status.PENDING).count()
    )
```

**設計考量：**
- 三個查詢彼此獨立，無 N+1 問題（`select_related` 處理關聯）
- `pending_registrations_count` 只給幹部，一般團員不需要看這個數字
- import 放在 `if request.user.is_authenticated` 內部，避免未登入時引發不必要的查詢

---

### 4.12 演出曲目管理（events）

**檔案**：`apps/events/views.py`（`setlist_manage`）、路由：`/events/<pk>/setlist/`

**幹部限定**，管理某場演出的曲目順序清單（Setlist）。

#### 兩個 action 的邏輯

| action | 說明 |
|--------|------|
| `add` | 從總譜清單選一首、填演出順序，建立 `Setlist`。同一場演出的順序號不可重複（view 層檢查），同一首曲目也不可重複加入 |
| `remove` | 刪除指定的 `Setlist` item |

#### 為什麼只能選總譜？

```python
available_scores = Score.objects.filter(score_type=Score.ScoreType.FULL)
```

演出曲目記錄的是「這場演出演哪首曲子」，概念上是作品層級。
個別樂手的分譜分配由 `PartAssignment` 負責，兩者分層管理，
避免因分譜數量不同而讓同一首曲子在 setlist 出現多次。

#### 下一個可用順序號

```python
'next_order': (setlists.last().order + 1) if setlists.exists() else 1,
```

自動填入建議的下一個演出順序，方便幹部快速新增，不用自己算。

---

### 4.13 樂譜瀏覽與下載（scores）

**檔案**：`apps/scores/views.py`（`score_list`、`score_detail`、`score_download`）

**登入者可用**，一般團員與幹部皆可瀏覽。

#### score_list：篩選與分頁

```python
# 三個可組合的篩選條件（均透過 GET 參數傳入）
score_type    = request.GET.get('type', '')       # 'full' 或 'part'
instrument_id = request.GET.get('instrument', '') # 樂器 ID
query         = request.GET.get('q', '').strip()  # 曲名關鍵字（icontains）

# 每頁 30 筆
paginator = Paginator(scores, 30)
```

三個條件可以自由組合，例如「只看長笛分譜」或「搜尋包含 '星' 字的曲子」。

#### score_detail：版本鏈顯示

```python
versions = score.versions.select_related('instrument')
```

`versions` 是 `parent_score` ForeignKey 的 `related_name`，
顯示從這個版本衍生出去的所有改版，讓使用者沿著版本鏈上下追溯。

#### score_download：直接下載 PDF

```python
return FileResponse(score.file.open('rb'), as_attachment=True, filename=...)
```

沒有上傳 PDF 的樂譜，`score.file` 為空，直接回傳 404。
用 `as_attachment=True` 讓瀏覽器觸發下載而非在 tab 內開啟。

---

### 4.14 報表：排練出席（events）

**檔案**：`apps/events/views.py`（`attendance_report`）、路由：`/events/<pk>/attendance/`

**幹部限定**，以演出活動為單位，顯示所有排練的出席狀況。

#### 資料建構策略

```python
# 一次查詢建立 lookup table，避免 N+1
attendance_map = {
    (a.rehearsal_id, a.member_id): a.status
    for a in RehearsalAttendance.objects.filter(rehearsal_id__in=[r.pk for r in rehearsals])
}
```

用 `(rehearsal_id, member_id)` 為 key 的 dict，查詢複雜度 O(1)。
不論有幾場排練、幾位團員，只需一次 DB 查詢。

#### 兩層輸出

| 輸出 | 說明 |
|------|------|
| 各場排練統計（上半部）| 每場排練的出席 / 請假 / 缺席 / 無紀錄人數 |
| 個人橫列（下半部）| 每位團員各場排練的狀態 + 出席率（綠/黃/紅色標示）|

#### 無紀錄 vs 缺席

`absent`（缺席）是幹部手動標記的狀態；無紀錄（`None`）是完全沒有 `RehearsalAttendance` 的情況。
兩者語意不同，分開計算與顯示，讓幹部知道哪些人「確認缺席」、哪些人「根本沒任何紀錄」。

---

### 4.15 報表：財產借用現況（assets）

**檔案**：`apps/assets/views.py`（`borrow_status_report`）、路由：`/assets/borrows/`

**幹部限定**，顯示所有 `returned_at IS NULL` 的借用紀錄，並標記逾期項目。

```python
today = timezone.localdate()
active_borrows = AssetBorrow.objects.filter(returned_at__isnull=True)

rows = []
for borrow in active_borrows:
    overdue = borrow.due_date is not None and borrow.due_date < today
    rows.append({'borrow': borrow, 'overdue': overdue})
```

**為什麼用 `timezone.localdate()` 而非 `timezone.now().date()`？**
`localdate()` 會依設定的 `TIME_ZONE` 轉換成本地日期，確保台灣時區的「今天」判斷正確。

逾期列在 template 用 `class="table-danger"` 高亮，同時顯示逾期徽章，讓幹部一眼識別。

---

### 4.16 報表：會費繳納狀況（finance）

**檔案**：`apps/finance/views.py`（`membership_fee_report`）、路由：`/finance/membership/`

**幹部限定**，按期別顯示所有團員的繳費狀態。

#### 三種狀態

| status | 條件 | 說明 |
|--------|------|------|
| `paid` | `MembershipFee` 存在且 `paid_at` 有值 | 已繳費 |
| `unpaid` | `MembershipFee` 存在但 `paid_at` 為空 | 建了紀錄但尚未繳費 |
| `no_record` | 該期別完全沒有 `MembershipFee` 紀錄 | 幹部尚未建立此人的紀錄 |

`no_record` 是透過比對「全體活躍團員」與「該期別 fee_map」的差集得出：

```python
fee_map = {f.member_id: f for f in MembershipFee.objects.filter(period=selected_period)}
for member in members:
    fee = fee_map.get(member.pk)  # None = no_record
```

#### 預設期別

```python
periods = MembershipFee.objects.values_list('period', flat=True).distinct().order_by('-period')
selected_period = request.GET.get('period', '')
if not selected_period and periods:
    selected_period = periods[0]
```

按 `period` 字串倒序排列，`'2026 上半年'` 排在 `'2025 下半年'` 之前，
符合直覺（最新期別在前）而不需要額外的日期型別。

---

### 4.17 報表：請假統計（events）

**檔案**：`apps/events/views.py`（`leave_stats`）、路由：`/events/leave/stats/`

**幹部限定**，以演出活動為單位，提供請假申請的兩層統計。

```python
from collections import defaultdict

S = LeaveRequest.Status
rehearsal_counts = defaultdict(lambda: {S.PENDING: 0, S.APPROVED: 0, S.REJECTED: 0})
member_leave_map = defaultdict(list)

for leave in leaves:
    rehearsal_counts[leave.rehearsal_id][leave.status] += 1
    member_leave_map[leave.member_id].append(leave)
```

用兩個 `defaultdict` 單次迴圈同時完成排練層與個人層的統計，不需要額外查詢。

#### 兩層輸出

| 輸出 | 說明 |
|------|------|
| 排練層（上半部）| 每場排練的待審 / 核准 / 拒絕請假數 |
| 個人層（下半部）| 按總請假次數遞減排序，顯示各狀態細分 |

個人層只顯示「有請假紀錄的團員」，零請假的人不出現，避免表格過長。

---

## 附錄：常見 Django 概念速查

| 概念 | 說明 |
|------|------|
| `@login_required` | 裝飾器，未登入自動導到登入頁 |
| `get_object_or_404` | 查不到資料時回傳 404，避免自己寫 try/except |
| `messages` | 跨 request 的一次性提示訊息（成功/錯誤），存在 session |
| `select_related` | JOIN 查詢，解決 ForeignKey 的 N+1 問題 |
| `get_or_create` | 有就拿，沒有就建立，回傳 (instance, created) |
| `TextChoices` | 列舉型別，資料庫存英文 key，顯示用中文 label |
| `auto_now_add=True` | 建立時自動填入當前時間，之後不能修改 |
| `null=True, blank=True` | null 是資料庫層允許 NULL；blank 是表單驗證層允許空白 |
