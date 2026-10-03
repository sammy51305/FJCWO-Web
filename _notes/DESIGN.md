# FJCWO-Web 設計邏輯說明

> 本文件說明 Phase 1 & 2 的設計決策、資料庫結構與各系統的運作邏輯。
> 目標讀者：接手開發或複習程式碼的人（包含自己）。
> 最後更新：2026-09-09（#13-2／#13-9／#13-10 改名「入團申請」、請假頁分部長提示、保險費分類，#13 全部結案；#13-4 樂譜庫存只列總譜；#13-7／#13-8 請假截止改當天 23:59、過期樣式明確；#11 批次匯入完成，P0 全數結案；測試站接上 Gmail SMTP，#10 完成；#13-1 決定二定案並實作敏感個資欄位加密，#13-1 全部完成；新增 #16 金鑰管理強化待辦；#13-5／#13-6 演出出席意願三態完成、演出請假廢除；測試站已上線 Render＋Neon 並加 robots.txt／noindex；#10 選定路線 A；#4 確認申報需身分證字號；#13-3 公告三欄已完成；2026-09-19 首頁「下次排練」改成當天整天都留著、加路徑標示，見 §4.11；2026-09-19 場地管理列表補用途說明與使用次數，見 §4.3）

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
   - [報表：團員通訊錄名冊（accounts）](#報表團員通訊錄名冊accounts)
   - [LINE 群組通知（notifications）](#418-line-群組通知notifications)
   - [演出分譜下載（scores）](#419-演出分譜下載scores)
   - [關於百韻內容管理（public）](#420-關於百韻內容管理public)
   - [組織章程管理（public）](#421-組織章程管理public)
   - [演出出席意願（events）](#422-演出出席意願events)

**附錄**

- [附錄一：常見 Django 概念速查](#附錄一常見-django-概念速查)
- [附錄二：確認無問題的項目](#附錄二確認無問題的項目)
- [附錄三：設計選擇備忘](#附錄三設計選擇備忘)
- 附錄四、五（待評估項目、待開發構想）→ 已獨立為 [BACKLOG.md](BACKLOG.md)

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
InstrumentFamily ←─── User ───→ SectionType
       │
       └──→ InstrumentType
                                           │
                                           └──→ Registration（入團申請）

Venue ──→ VenueTimeSlot
  │
  ├── PerformanceEvent ──→ Setlist ──→ Score
  │         │                │
  │         │                └──→ PartAssignment ──→ User（含 role=guest 槍手）
  │         │
  │         ├──→ Rehearsal ──→ RehearsalQRToken
  │         │         │
  │         │         ├──→ RehearsalAttendance ──→ User
  │         │         └──→ LeaveRequest ──→ User
  │
  └── PerformanceAttendance ──→ User（intent 事前意願三態 ／ attended 事後到場）

FinanceRecord ──→ PerformanceEvent（選填）
               ──→ User（登記者）

Score ──→ Score（full_score，分譜→總譜，CASCADE）
Score ──→ Score（parent_score，版本鏈，SET_NULL）
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

`about` view 查詢 `AboutSection`（只取 `is_visible=True`）後回傳模板。
`rules` view 查詢 `CharterContent.objects.first()` 取得章程內容，幹部可透過 `rules_edit` 更新。
`index`（首頁）對已登入者另外查詢個人化資料，詳見 [4.11 首頁 Dashboard](#411-首頁-dashboardpublic)。

---

#### robots.txt 與搜尋引擎收錄（2026-09-07）

`/robots.txt` 掛在**網站根目錄**（`config/urls.py`，不是 `apps/public/urls.py`）——爬蟲只認這個位置。

行為由 `settings.ROBOTS_NOINDEX`（環境變數 `DJANGO_ROBOTS_NOINDEX`）切換：

| 模式 | robots.txt | X-Robots-Tag header |
|------|-----------|---------------------|
| 測試站（`True`）| `Disallow: /` 整站禁止 | `noindex, nofollow` |
| 正式站（`False`，預設）| 只擋 `/admin/`、`/accounts/`、`/events/`、`/scores/`、`/assets/`、`/finance/` | 不加 |

**為什麼要兩個機制**：robots.txt 擋的是「爬取」，不是「收錄」——搜尋引擎若從別處取得網址，
仍可能把網址列進結果。`X-Robots-Tag` 才是明確的不收錄指令，兩者搭配才擋得乾淨。

**為什麼 header 用 middleware 而非在 template 加 meta**：header 涵蓋所有回應
（含 Django Admin、檔案下載、JSON），不必逐一改樣板，日後新增頁面也不會漏。

**為什麼做成開關而非寫死**：同一份程式碼會同時部署到測試站與正式站。寫死「全站禁止」
會讓正式站的公開頁（關於百韻、組織章程、公開公告）也搜尋不到，那對樂團是損失。

---

### 4.2 帳號與會員（accounts）

**檔案**：`apps/accounts/models.py`、`apps/accounts/views.py`

#### 三支公開 View 的分工

| View | 路由 | 說明 |
|------|------|------|
| `registration_apply` | `GET/POST /accounts/register/` | 填寫申請表單，送出後建立 `Registration`（status=pending）|
| `registration_status` | `GET/POST /accounts/register/status/` | 輸入 Email 查詢自己的申請狀態，**不需登入** |
| `registration_review` | `GET/POST /accounts/register/review/` | 幹部管理頁：查詢／篩選所有申請、核准／拒絕／重新開放審核 |
| `registration_create` | `GET/POST /accounts/register/create/` | 幹部手動新增一筆申請紀錄（例如電話報到，補登進系統）|
| `registration_edit` | `GET/POST /accounts/register/<pk>/edit/` | 幹部編輯申請的基本資料，不含審核狀態 |
| `registration_delete` | `POST /accounts/register/<pk>/delete/` | **管理員**刪除申請紀錄（含已核准者）|

`registration_status` 設計為公開頁面，讓申請者不需帳號就能確認申請進度，
避免對方不斷來電詢問。查詢以 Email 為鍵，列出該 Email 所有申請紀錄。

#### registration_review 從「審核清單」升級成「管理頁」

原本的頁面把待審核與已審核（最近 50 筆）分成兩個區塊顯示，只能核准/拒絕，看不到全部歷史、
也不能查詢或修正打錯的資料。現在改成單一表格，支援：

```python
registrations = Registration.objects.select_related('instrument', 'reviewed_by').order_by('-created_at')
if query:
    registrations = registrations.filter(Q(name__icontains=query) | Q(email__icontains=query))
if status_filter in Registration.Status.values:
    registrations = registrations.filter(status=status_filter)
```

依姓名/Email 關鍵字搜尋、依狀態篩選、分頁（30 筆一頁），寫法跟 `score_list` 的篩選列一致。

#### 為什麼「審核狀態」不能透過 registration_edit 修改

`registration_edit` 只讓幹部改姓名/樂器/畢業年份/電話/Email，刻意不開放直接修改 `status` 欄位。
原因是核准動作有副作用（建立 User 帳號、寄送臨時密碼信），如果編輯表單也能把狀態直接改成
`approved`，就會繞過 `_create_member_with_temp_password()`，變成「申請顯示已核准，但其實沒有
對應帳號」的不一致狀態。狀態變更永遠只能透過 `核准`／`拒絕`／`重新審核` 這三個有明確副作用定義
的 action 進行，編輯表單只負責修正基本資料。

#### 為什麼拒絕可以「重新開放審核」，核准不行

`reject` 之後可能是幹部誤按或校友補件，讓它能重新回到 `pending` 合理。
`approve` 之後已經建立正式 User 帳號、也寄出臨時密碼，讓它「復原」並不會真的刪掉那個帳號，
只會讓 `Registration.status` 跟實際帳號狀態脫節，所以 `reopen` action 只接受 `status=rejected`
的申請（`registration_review` view 用 `elif reg and action == 'reopen' and reg.status == Registration.Status.REJECTED`
擋下 `approved` 的情況）。

#### 刪除申請紀錄：限管理員，已核准的也可刪（2026-09-09 修訂）

**原本的設計**：`registration_delete` 權限為 `is_officer`，且對 `status=approved` 直接擋下——
理由是稽核軌跡，帳號建立後這筆 `Registration` 就是「這個帳號怎麼來的」的唯一紀錄。

**改成什麼**（幹部實際使用後回報）：

| | 原本 | 現在 |
|---|---|---|
| 誰能刪 | `is_officer` | `is_superuser` 或 `is_admin_role` |
| 已核准的 | 一律擋下 | 可刪 |

**兩項都有理由**：

- **權限收成管理員**：刪除在本系統一律是管理員的事——團員通訊錄、演出活動、場地、樂譜
  都是這條線，入團申請原本是全站唯一的例外，不一致本身就是個坑。
- **放寬已核准的**：稽核軌跡的價值在一個內部小系統裡，抵不過「測試資料與重複申請永遠清不掉」
  的代價。實務上幹部第一個撞到的就是 demo 期間留下的已核准紀錄刪不掉。

⚠️ **刪申請紀錄不等於刪帳號**。核准時建立的 `User` 是獨立的資料，不會被連帶刪除；
要停用團員得走團員管理的退團（`is_active=False`）。已核准紀錄的刪除確認對話框會明講這件事，
避免幹部誤以為按下去就把人踢出團了。

> `reopen` 仍然只接受 `status=rejected`（見上一節）——那是因為 `approved` 的「復原」
> 會讓 status 與實際帳號狀態脫節，跟能不能刪除是兩回事。

#### 核准申請 / 手動新增團員：共用的帳號建立邏輯

早期版本的 `registration_review` 核准動作只把 `Registration.status` 改成 `approved`，
沒有真的建立 User 帳號——等於幹部核准後還要自己去 Django Admin 重新謄一次資料，審核形同虛設。
現在核准申請（`registration_review`）與幹部手動新增團員（`member_create`）都呼叫同一個
共用函式 `_create_member_with_temp_password()`：

```python
def _create_member_with_temp_password(*, name, email, instrument=None, section=None, grad_year=None, phone=''):
    username = _unique_username(email.split('@')[0])  # 帳號沒收集，用 Email 帳號部分產生
    password = get_random_string(10)                    # 隨機臨時密碼
    user = User.objects.create_user(
        username=username, password=password,
        name=name, email=email, role=User.Role.MEMBER,
        instrument=instrument, section=section, grad_year=grad_year, phone=phone,
        must_change_password=True,   # 強制對方第一次登入後自行設定新密碼
    )
    email_sent = send_temp_password_email(user, username, password)
    return user, username, password, email_sent
```

`_unique_username()` 把 Email 帳號部分（`@` 前）過濾成合法字元，重複時依序加數字後綴，確保帳號唯一。
角色固定寫死 `User.Role.MEMBER`——這兩個入口都是「開一個團員帳號」，不該用來直接授予幹部/管理員權限，
那件事應該透過 Django Admin 由更高權限的人操作。

若 Email 已被其他帳號使用（例如同一人重複申請、或幹部已手動開過帳號），核准/新增會被擋下並顯示錯誤，
不會建立重複帳號或撞到 `User.email` 的 unique 限制而噴 500。

#### 為什麼密碼不能留空、也不能讓團員自選帳號

原本設計想讓「帳號＋密碼都由團員自己填」，但這會踩到兩個問題：

1. **Django 的 `username` 是必填 + unique**，帳號建立當下一定要有值，不可能真的留空等團員填。
2. **若密碼留空（unusable password）直接讓人進到「設定密碼」頁面，會有帳號劫持風險**：
   只要駭客知道或猜到某人的帳號，就能搶先幫他設一組新密碼，本人反而登不進自己的帳號。

因此帳號固定由系統產生（Email 前綴，不開放自訂），密碼則是「先給一組真正、隨機產生的臨時密碼
守住登入這一關，登入後強制換成團員自己選的密碼」——見下方「強制設定新密碼」。

#### 帳密如何送達本人：Email

`apps/accounts/utils.py` 的 `send_temp_password_email()` 呼叫 Django 的 `send_mail()`，
把帳號與臨時密碼寄給本人。寄信失敗不擋帳號建立（帳號已經建立成功），只記 log，
呼叫端會依 `email_sent` 決定訊息文字：

```python
if email_sent:
    messages.success(request, f'...帳號密碼已寄送至 {email}。')
else:
    messages.warning(request, f'...但寄信失敗，請自行告知本人：帳號 {username}，臨時密碼 {password}。')
```

`EMAIL_BACKEND` 在 `config/settings.py` 依 `.env` 是否填了 `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD`
決定：本機開發沒填時自動改用 `console` backend（信件內容印在終端機），不需要真的申請 SMTP 帳號，
和 LINE Bot 缺少 Token 時 silent skip 是同一種「本機開發不需要真憑證」的設計慣例。

#### 強制設定新密碼（must_change_password）

`User.must_change_password` 為 `True` 時，`ForcePasswordChangeMiddleware`
（`apps/accounts/middleware.py`）會攔截該使用者的**所有請求**，導向 `change_password_view`：

```python
_EXEMPT_PATHS = ('/accounts/password/change/', '/accounts/logout/')
_EXEMPT_PREFIXES = ('/admin/', settings.STATIC_URL, settings.MEDIA_URL)
```

放行清單刻意排除設定密碼頁本身與登出，否則會形成無限重導向；也放行 `/admin/` 與
靜態/媒體檔路徑，避免本機 `runserver` 直接送靜態檔時，畫面上的圖片被攔成 302 而顯示不出來
（正式環境靜態檔由 Nginx 直接處理，不會經過這個 middleware）。

`change_password_view` 驗證兩次密碼一致、套用 Django 內建的 `validate_password()`
（沿用 `settings.AUTH_PASSWORD_VALIDATORS`，不重新發明強度規則），成功後：

```python
request.user.set_password(password1)
request.user.must_change_password = False
request.user.save()
update_session_auth_hash(request, request.user)  # 避免改密碼後被登出
```

`update_session_auth_hash()` 是必要的一步：Django 改密碼後預設會讓現有 session 失效，
不呼叫這個會讓使用者剛設完新密碼就被登出，變成要重新登入一次才能用。

#### member_create：幹部手動新增團員

路由：`/accounts/directory/create/`，幹部限定，入口在團員通訊錄頁面右上角「新增團員」按鈕。

校友報到申請流程假設對象是「本人上網填表」，但實務上有些團員是幹部直接口頭問完資料就手動建帳號
（例如指導老師、非透過網路報到的人），這種情境不會經過 `Registration` 這張表。
`member_create` 提供獨立的手動建帳號入口，表單只收基本資料（姓名、Email、樂器、聲部、畢業年份、電話），
不收帳號/密碼/角色——帳密由上述共用邏輯自動處理，角色固定為團員。

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

#### 團員通訊錄的分組邏輯

```python
# 撈所有啟用中、非管理員的會員，依樂器族群分類排序
# User.instrument 指向 InstrumentFamily（族群層級），不是 InstrumentType
members = User.objects.filter(is_active=True).exclude(role=User.Role.ADMIN)
          .select_related('instrument', 'section')
          .order_by('instrument__category', 'instrument__name', 'name')

# 用 dict 分組（依 InstrumentFamily.category 的中文顯示值）
grouped = {}
for member in members:
    category = member.instrument.get_category_display() if member.instrument else '未分類'
    grouped.setdefault(category, []).append(member)
```

`User.instrument` 關聯到 `InstrumentFamily`（族群），而非 `InstrumentType`（具體樂器）。
因為團員的個人資料只需識別到族群層級（如「豎笛」），不需細分到 Bb/Eb 豎笛。
`get_category_display()` 是 Django 自動加在 `TextChoices` 欄位上的方法，
把資料庫存的英文 key（如 `woodwind`）轉成中文顯示值（如 `木管`）。

#### 通訊錄的查詢／篩選

依姓名或樂器族群名稱關鍵字搜尋（`Q(name__icontains=query) | Q(instrument__name__icontains=query)`），
寫法跟 `score_list` 一致。狀態篩選（在團／已退團／全部）只給幹部用：

```python
status_filter = request.GET.get('status', '') if request.user.is_officer else ''
```

一般團員即使自己在網址帶 `?status=inactive`，view 也會強制忽略，只看得到在團名單——
誰已經退團屬於幹部內部管理事項，不對一般團員公開。

#### 退團＝軟刪除，不是真的刪除

`member_deactivate` 只是把 `User.is_active` 設成 `False`，`member_reactivate` 設回 `True`，
兩者都不動資料庫裡的任何其他紀錄。原因跟演出活動用「已取消」狀態而不直接刪除是同一個道理：
`User` 被排練出席、請假、演出出席、財產借用、財務紀錄、公告等多張表用外鍵參照，
其中不少是 `CASCADE`——真的刪除團員會連帶砍光他所有歷史紀錄。

#### member_delete：只有「乾淨」帳號才允許真的刪除

「退團」不能滿足所有情境——如果幹部新增團員時打錯字，馬上發現，這種帳號還沒有任何關聯資料，
應該可以直接刪乾淨，不需要留著一筆「退團」的髒資料。`_user_has_related_records()` 用 Django 的
`Collector`（`Model.delete()` 內部用的同一套機制）模擬一次刪除，檢查這個帳號會不會牽連任何其他資料：

```python
collector = Collector(using='default')
try:
    collector.collect([user])
except ProtectedError:
    return True          # PROTECT 關聯（如 Announcement.created_by）：擋下
for model, instances in collector.data.items():
    if model is not User and len(instances) > 0:
        return True       # 一般 CASCADE 收集到的關聯物件
for qs in collector.fast_deletes:
    if qs.model is not User and qs.exists():
        return True       # 見下方「fast_deletes 的坑」
for (field, value), querysets in collector.field_updates.items():
    for qs in querysets:
        if qs.exists():
            return True    # SET_NULL 關聯（如 Rehearsal.summary_by）
return False
```

有牽連就擋下真正刪除，只能改用退團；完全沒有牽連（`collector` 除了 `User` 自己以外什麼都沒收集到）
才允許 `member.delete()`。用 `Collector` 而非手動列出每張表的好處是，以後新增別的 app 參照 `User`
時，這裡不需要跟著改。

#### 管理員可以強制刪除，跳過關聯紀錄檢查

一般幹部受 `_user_has_related_records()` 限制，但管理員（`role=admin` 或 `is_superuser`）可以直接
跳過這層檢查，方便清掉開發／測試過程中不小心產生、卻已經牽連測試資料的帳號：

```python
can_force_delete = request.user.is_superuser or request.user.is_admin_role
...
elif not can_force_delete and _user_has_related_records(member):
    ...擋下...
else:
    member.delete()   # 管理員：CASCADE/SET_NULL 一律放行
```

即使是管理員，`PROTECT` 關聯（例如這個帳號發布過公告）仍是資料庫層級的硬限制，`member.delete()`
一樣會拋出 `ProtectedError`——這不是權限問題，是資料完整性問題，管理員也必須先處理該筆關聯資料
（例如到 Django Admin 改公告的發布者或刪除該公告）才能刪除帳號。這裡用 `try/except ProtectedError`
包起來顯示友善錯誤訊息，而不是讓它變成 500。

#### fast_deletes 的坑：CASCADE 反向關聯不一定出現在 collector.data

開發時原本以為「CASCADE 關聯會出現在 `collector.data`，SET_NULL 出現在 `collector.field_updates`」，
測試也因此一度誤判：明明帳號已經有 `RehearsalAttendance` 出席紀錄，`_user_has_related_records()`
卻回傳 `False`，讓真正刪除通過了。

原因是 Django 對某些「簡單、無需再觸發其他 signal」的 CASCADE 反向關聯，會走內部的**快速刪除路徑**
（直接發一條 SQL `DELETE ... WHERE`，不需要把每個 instance 都載入成 Python 物件），
這類物件只會出現在 `collector.fast_deletes`（一批尚未評估的 QuerySet），完全不會進入 `collector.data`。
`RehearsalAttendance` 剛好符合這個條件，所以第一版程式碼完全漏掉了它，是靠測試
（`MemberDeleteTest.test_member_with_related_records_cannot_be_deleted`）才抓出來的。

另外 `collector.field_updates` 的 key 其實是 `(field, value)` 這個 tuple，不是 model；
value 是尚未評估的 QuerySet 列表。第一版程式碼誤把 `len(field_updates[key])`（list 長度，
只要這個 FK 欄位存在就恆為 1）當成「筆數」，導致任何帳號都被誤判成「有牽連」——
必須改成呼叫 `qs.exists()` 才是正確判斷 QuerySet 裡有沒有真正的資料列。

---

#### 必填欄位與敏感個資（#13-1，2026-09-07 實作）

**必填七項**：姓名、Email、出生年月日、住址、手機、LINE ID、身分證字號。
**選填三項**：樂器、聲部、畢業年份。

```python
# apps/accounts/views.py
_REQUIRED_PROFILE_FIELDS = (('name', '姓名'), ('email', 'Email'), ('address', '住址'),
                            ('phone', '手機'), ('line_id', 'LINE ID'), ('national_id', '身分證字號'))

def _parse_profile_fields(post):   # 回傳 (data, errors)
    ...
```

**必填只在表單層、model 一律可空**——既有團員這些欄位是空的，model 設 `null=False`
會讓 `migrate` 直接卡在既有資料上（#13-1 決定三）。既有帳號也**不做 middleware 強制補填**，
登入照常使用，避免上線初期把人擋在門外。

**四個入口共用同一份規則**：校友自行申請、幹部補登申請、幹部編輯申請、幹部建團員帳號。
views 端共用 `_parse_profile_fields()`、template 端共用 `accounts/_profile_fields.html`，
兩者一對一對應。各寫一份必然隨時間走鐘，這是刻意集中。

**身分證字號／居留證號**（2026-09-07 放寬）：
- 接受兩種格式：**身分證**（1 英文字母 + 9 數字）與**居留證統一證號**（2 英文字母 + 8 數字）。
  團裡有港澳團員，在台長住者持居留證號，只收身分證會把他們擋在申請頁外。
- **兩者皆無者**（例如短期來幫忙的境外人士）：**公開申請頁維持必填、幹部端允許留空**——
  公開頁擋的是隨手亂填，幹部端擋的是本來就不存在的東西，兩者需求不同。
  view 端以 `_parse_profile_fields(..., require_national_id=False)` 切換。
  > 申報實務上，沒有證號的人本來就報不了，那是行政問題不是系統問題；
  > 幹部已知悉並決定屆時不申報這些人。
- 驗證只檢查格式、**不驗檢查碼**——目的是擋打錯，不是做身分驗證。
- 一律轉大寫再存，避免同一號碼因大小寫被當成兩筆。
- `masked_national_id` property 只留末四碼，列表／報表用它。
  **做成 property 而非讓各 template 自己遮**，是為了讓「不顯示完整值」只有一份實作，
  日後新增頁面不會漏——這是資安邊界，不是顯示細節。

**入學年／科系（`alumni_info`）**：入團申請表單的「輔大入學年 / 就讀科系」**原文照存**，
不自動拆成 `grad_year`。那一格塞了兩種資訊，實際填法有六七種變體（只填數字、填「非校友」、
填兩個學位都有），自動解析必然產生錯資料，**而錯資料比沒資料難處理**。
`grad_year`（西元畢業年份）維持原語意、匯入時留空，日後幹部要用再人工填。
> 刻意不把 `grad_year` 改成「入學年（民國）」——既有團員存的是西元畢業年份，
> 改語意會讓新舊資料混在同一欄，那是最難救的一種爛帳。

**`Registration.instrument` 指向樂器族群而非具體樂器**（2026-09-07 改）：
入團申請表單填的是「豎笛」「薩克斯風」「打擊樂器」這類粗分類，對不到 `InstrumentType`
的 Bb 豎笛／中音薩克斯風等細項；`InstrumentFamily`（族群）這層剛好一對一對得上，
九個實際填答值全部有對應（只有「打擊樂器→打擊樂」差一字，匯入時對照即可）。

另兩個好處：與 `User.instrument` 同一層，核准建帳號時不必再 `.family` 轉換；
且**分譜仍用 `InstrumentType` 保有細分**——Bb 豎笛與低音豎笛是不同分譜，那層不能合併。

> **Migration 注意**：改 FK 指向時，欄位裡存的還是舊的 `InstrumentType` id，
> 不清掉會被當成 `InstrumentFamily` id 重新解讀，變成「指向不相干樂器」的安靜錯資料。
> `0008` 因此在 `AlterField` **之前**先跑 `RunPython` 把 `instrument` 清空。

##### 敏感個資的欄位加密（實作，2026-09-08）

`apps/accounts/fields.py` 提供 `EncryptedTextField` 與 `EncryptedDateField`，
`national_id`／`address`／`birth_date` 三個欄位改用它們。**加解密只發生在 DB 邊界**，
view、template、form 用起來與一般欄位無異。

| 決策 | 為什麼 |
|------|--------|
| 用 **Fernet 對稱加密**，不是雜湊 | 這些值要能還原——申報要列完整號碼、團員要看得到自己的、幹部詳情頁要展開。雜湊不可逆，做不到 |
| 金鑰由**任意字串經 SHA-256 推導** | 環境變數填什麼都行，不必產生格式正確的 Fernet key；少一種「金鑰格式錯誤導致整站起不來」的失敗模式，Render 的 `generateValue` 也能直接用 |
| 空值**不加密**，維持空字串 | 沒有東西要保護；也讓「沒填」在 DB 裡仍看得出來，不會每列都像有資料 |
| 解不開的值**回傳空字串、不拋例外** | 換過金鑰或手動改過 DB 時，整個團員列表不該因一筆壞資料就 500 |
| `birth_date` 在 Python 端仍是 `date` | 型別轉換藏在欄位裡，呼叫端不必知道底層是密文字串 |
| DB 端不限長度、改用 `form_max_length` | 密文比原文長且長度不定，`max_length` 只能在表單層把關 |

**金鑰**：環境變數 `DJANGO_FIELD_ENCRYPTION_KEY`。沒設會退回 repo 內的開發預設值——
本機與測試跑得動，但**那把是公開的、等於沒加密**，所以 `build.sh` 在部署時直接擋下沒設金鑰的情況，
讓它在建置階段就失敗，而不是安靜地把真實個資明文存進去。

> ⚠️ **換金鑰等同資料遺失**：既有密文將解不開（顯示為空）。真要換必須先用舊金鑰解密、
> 再用新金鑰加密，不能直接改環境變數。

**Migration `accounts/0009`** 在欄位型別換成 text 之後，用**原生 SQL** 把既有明文就地加密——
此時欄位已是加密欄位，透過 ORM 讀取會嘗試解密明文而失敗（得到空字串），寫回去就把資料洗掉了。
反向（解密回明文）也有提供，讓這個 migration 可以回退；解不開的值留原樣不清空，
寧可留下看不懂的密文讓人察覺有異。

**LINE ID vs line_user_id**：`line_id` 是使用者自己填的 LINE 帳號（用於加群組），
`line_user_id` 是 LINE Bot 取得的內部 id（用於推播）。**兩者不可混用**，故為兩個欄位。

**核准時整批帶進帳號**：`_create_member_with_temp_password()` 新增
`birth_date`／`address`／`national_id`／`line_id` 參數，`registration_review` 核准時一併傳入。
樂器改選填後，原本的 `reg.instrument.family` 會在沒填樂器時炸掉，已加 None 守衛。

**本人永遠看得到自己的**：`ProfileForm` 含這些欄位，團員可自行補填；限制的是別人看不看得到。

---

### 4.3 場地管理（band_public）

**檔案**：`apps/public/models.py`（Venue、VenueTimeSlot）、`apps/public/views.py`

#### 前端管理頁面：venue_list / venue_create / venue_edit / venue_delete

原本場地只能透過 Django Admin 操作，補上前端頁面後：

| View | 對象 | 功能 |
|------|------|------|
| `venue_list` | 幹部 | 依名稱/地址搜尋、依類別（演出/排練）篩選、列出每個場地被幾場演出／排練用到 |
| `venue_create` | 幹部 | 新增場地主體資料，成功後導向 `venue_edit` 才能新增時段 |
| `venue_edit` | 幹部 | 編輯場地主體資料 + 管理該場地的所有時段 |
| `venue_timeslot_delete` | 幹部 | 刪除單一時段 |
| `venue_delete` | **管理員限定**（`admin` 角色或 `superuser`）| 刪除場地，被演出/排練引用時（`PROTECT`）擋下 |

`venue_create` 只建立場地主體、不處理時段，是因為 `VenueTimeSlot` 需要先有 `venue_id` 才能建立，
兩者天生就是「先建父層、再建子層」的順序，用兩個步驟比在同一個表單塞進動態數量的時段列更單純。

時段的新增/刪除各自是獨立的 action（`add_timeslot` 這個 POST 參數判斷是不是新增時段的表單），
跟 `score_parts_manage`、`registration_review` 的核准/拒絕是同樣的「同一頁面多個小 action」寫法。

#### 為什麼列表要寫用途說明與使用次數

2026-09-19 幹部試用回饋：「場地管理的功能我沒有 get 到」。這頁本身沒有錯——它是
**主檔維護頁**，問題出在主檔頁天生看不出「什麼時候該來這裡」：點進去只有一張場地清單
與新增表單，跟「排一場演出」這件事之間的關聯沒有任何地方寫出來。

補了三件事，都是說明性質、不改既有邏輯：

1. **標題下方寫明用途與時機**——先在這裡建好場地，新增演出／排練時才選得到；
   並點明這裡維護的是「場地長什麼樣子」，**不是預約系統**（哪天用哪個場地是在活動裡指定）。
2. **列表加「使用中」欄**，標出被幾場演出／幾場排練用到。這是把主檔跟實際用途連起來最直接的
   方式，也順帶解釋了為什麼有些場地刪不掉（被引用時 `PROTECT` 擋下，見下一節）。
3. **空狀態分兩種**：一筆都還沒建 → 給「新增第一個場地」的引導；搜尋不到 → 維持原本的
   「沒有符合條件」。兩者要傳達的訊息完全不同，共用一句話等於什麼都沒說。

使用次數用兩個 `annotate` 算，`distinct=True` **不能省**：兩個 annotate 各自 JOIN 一張表，
不去重的話 1 場演出 × 2 場排練會互相相乘、兩邊都變成 2（`VenueManageTest` 有測試擋這件事）。

#### 為什麼刪除場地限管理員

跟 `member_delete`、`event_delete` 是同樣的考量：場地被 `PerformanceEvent`／`Rehearsal` 用 `PROTECT`
參照，一般幹部不小心刪掉場地會讓歷史排練/演出紀錄失去場地資訊。這裡不像 `member_delete` 需要
`Collector` 判斷「有沒有關聯紀錄才放行真刪除」——`PROTECT` 本身就是資料庫層級的硬限制，
管理員也無法繞過，`venue_delete` 只是把 `ProtectedError` 包成友善訊息，而不是讓它變 500。

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
                                    ↘ cancelled（已取消）
```

`cancelled` 用於誤建或取消的活動，避免直接刪除造成 cascade 刪除所有排練與紀錄。
幹部可在編輯頁切換為「已取消」，管理員（`admin` 角色或 `superuser`）可進一步刪除。

刪除按鈕原本只放在活動詳情頁（彈出 modal 二次確認），後來補上 `/events` 列表頁本身也能操作——
「即將到來」「過去活動」「已取消」三個分類的每一列都直接附上刪除按鈕，不需要先點進詳情頁。
列表頁一次可能列出多筆活動，用 modal 逐筆彈窗較笨重，改用跟其他列表頁（通訊錄、場地管理、
校友報到）一致的 `onclick="return confirm(...)"` 簡單對話框，警語文字沿用原本 modal 的內容
（提醒會連帶刪除排練、出席紀錄、曲目單）。詳情頁的刪除按鈕改用同一套 `confirm()` 寫法（拿掉原本
的 modal），跟列表頁風格一致；兩處都保留，因為使用情境不同——列表頁適合一次瀏覽多筆活動時快速清理，
詳情頁適合正在檢視某場活動、確認資訊後順手刪除。`event_delete` view 本身沒有變，只是多了一個入口。

`event_list` view 將活動分成三區，已取消僅管理員可見：

```python
can_view_cancelled = request.user.is_superuser or request.user.is_admin_role
upcoming  = base.exclude(status__in=['finished', 'cancelled']).order_by('performance_date')
past      = base.filter(status='finished').order_by('-performance_date')
cancelled = base.filter(status='cancelled') if can_view_cancelled else None
```

跟 `event_delete` 的權限判斷（`is_superuser or is_admin_role`）保持一致——曾經有一版只檢查
`is_superuser`，因為 `role=admin` 帳號在 `User.save()` 時會自動設定 `is_superuser=True`，
實務上行為沒有差異，但寫法上跟其他「管理員限定」功能不對稱，已經統一。

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

#### 請假入口：event_detail 直接提供捷徑

原本申請請假必須「演出活動列表 → 活動詳情 → 排練詳情 → 申請請假」共三層，
只有「下次排練」有首頁 Dashboard 的捷徑（見 §4.11），其餘排練仍要逐層點選。

`event_detail` 的排練列表每一列現在直接附上「請假」連結，省去進 `rehearsal_detail` 這一層：

```python
# event_detail view 額外傳入 now，供 template 判斷排練是否已結束
'now': timezone.now(),
```

按鈕邏輯與 `rehearsal_detail.html` 完全一致（`rehearsal.date > now` 才可點擊，
已結束顯示停用狀態），未做角色區分——幹部本身也是團員，一樣可能需要請假。

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

核准後，`reviewed_by` 和 `reviewed_at` 會一起記錄，留下稽核軌跡；同時把 `result_seen` 設回
`False`，讓首頁 Dashboard 知道「這是團員還沒看過的新結果」（見 §4.11「為什麼待審核清單看不到
核准/拒絕結果」）。

`leave_review_list` 在處理核准/拒絕動作前，會先確認申請狀態仍為 `pending`，
防止幹部透過瀏覽器上一頁重複送出，誤將已審核的申請再次翻轉。

#### leave_delete：刪除請假紀錄限管理員

跟 `member_delete`／`event_delete`／`venue_delete`／`score_delete` 同一套「管理員限定」權限模式。
`LeaveRequest` 沒有被任何其他表格參照，不像場地/樂譜/團員那樣有 `PROTECT`/`CASCADE` 需要處理，
`leave.delete()` 可以直接刪，不需要額外的關聯檢查或 try/except。入口在「請假審核」頁的
「近期審核紀錄」表格每一列，方便清掉測試/誤建的請假紀錄。

---


#### 請假截止：排練當天 23:59（#13-7，2026-09-09 實作）

**規則**：截止點是排練**當天的 23:59:59**，不是排練開始時刻。過了就無法申請，
**不提供任何補請假路徑**（2026-08-12 定案：方向 c 團員事後補請、方向 d 幹部代登記皆不做）。

```python
# apps/events/models.py
def day_end(moment):
    local = timezone.localtime(moment)
    return timezone.make_aware(
        dt.datetime.combine(local.date(), dt.time.max), timezone.get_current_timezone()
    )

class Rehearsal:
    @property
    def leave_deadline(self): return day_end(self.date)
    @property
    def leave_open(self): return timezone.now() <= self.leave_deadline
```

**為什麼由日期部分推算**：`Rehearsal` 只有單一 `date`、沒有結束時間欄位。
這是刻意的推導，不是欄位缺漏——加一個 `end_time` 只為了算截止並不划算。

**必須用本地時區的日期**：資料庫存 UTC，直接取 `.date()` 會在台灣時間的清晨或深夜算錯一天
——台北 8/15 07:00 的排練，UTC 是 8/14 23:00，用 UTC 日期會變成「8/14 截止」，
等於排練當天早上就已經不能請假。測試 `test_deadline_uses_local_date_not_utc` 守住這件事。

**演出表態共用同一條規則**：`PerformanceEvent.intent_deadline` 也呼叫 `day_end()`
（#13-6 當時留的 `TODO(#13-7)` 就此收掉）。兩者共用同一個函式，
不會各自演化出不同的界線——同一場活動的排練與演出若有兩套截止邏輯，團員一定會搞混。

**server 端擋，不只靠前端**：view 層檢查 `leave_open`，避免有人直接 POST 到 URL 繞過
被 disabled 的按鈕。

#### 過了截止就算缺席（顯示層，非批次寫入）

出席報表對「已過截止 ＋ 沒有任何紀錄」的組合顯示為**缺席**；未到截止的維持「無紀錄」
——那代表「還沒發生」，標成缺席會誤導。

```python
def status_of(rehearsal, member):
    status = attendance_map.get((rehearsal.pk, member.pk))
    if status:
        return status
    return RehearsalAttendance.Status.ABSENT if not rehearsal.leave_open else None
```

**刻意用顯示層判斷而非批次寫入資料**：不必養一個排程去掃過期排練，
而且哪天規則調整（例如改回允許補請假），舊資料不會已經被寫死成缺席。

#### 過期按鈕的樣式（#13-8）

幹部回饋「現況過期的請假連結雖已 disabled，但視覺上看不出來」。
**只調透明度不夠**——所以顏色（警告黃 → 灰）、圖示（日曆 → 禁止符號）、
文字（「請假」→「請假已截止」）、游標（`cursor: not-allowed`）一起換。

> Bootstrap 的 `disabled` 會設 `pointer-events: none`，游標樣式因此吃不到，
> 要在外層包一個 `<span>` 才顯示得出禁止游標。

#### 分部長提示（#13-9）

請假送出去只是進了幹部的審核佇列，**分部練習的人力調度沒有人被通知到**。
所以請假流程加一行靜態提示，提醒團員自己去講一聲。

出現在**兩個時機**，不是一個：

| 時機 | 形式 | 為什麼需要 |
|------|------|-----------|
| 填表時 | 表單上的 `alert-warning` | 送出前就知道還有事要做 |
| 送出後 | `messages.success` 帶一句 | 表單那則會隨跳頁消失，而通知分部長是送出**之後**才做的事 |

文字刻意寫成不指名的「自己的分部長」——**系統目前不知道誰是分部長**（見附錄五 #14）。
提示同時說明「系統只會送到幹部審核，不會自動通知分部長」，讓團員知道這不是客套話。
等 #14 做完，這行可以升級成指名顯示、甚至自動 LINE 通知。

### 4.7 財務管理（finance）

**檔案**：`apps/finance/models.py`

幹部前端可管理收支明細（`FinanceRecord` CRUD，刪除限管理員）與會費（期別＋繳納），
詳見附錄五 §7、§9；金額一律驗正數（`MinValueValidator(1)` ＋ view 層 >0 檢查）。

#### 三個 Model 的分工

| Model | 用途 |
|-------|------|
| `FinanceRecord` | 所有收入/支出明細，可關聯到某場演出。分類含保險費（#13-10，2026-09-09 新增）|
| `FeePeriod` | 會費期別主檔（年份+上/下期、全團固定金額、繳費時段），幹部/管理員 CRUD |
| `MembershipFee` | 每位團員對某期（FK→FeePeriod）的繳納狀態，金額自期別快照 |
| `PaymentConfig` | 轉帳收款設定（單例，QRCode＋銀行代號/名稱/戶名/帳號），供團員掃碼或複製轉帳 |

**為什麼會費要拆成期別主檔 + 繳納狀態？（附錄五 §9 S1）**
原本 `MembershipFee.period` 是自由文字、金額每列各自填，缺單一來源。改成 `FeePeriod` 主檔後：
金額由期別統一決定（團員/幹部登記時不重填、快照當下金額避免日後改期別竄改歷史）；建立一期後
每位在團團員天然就是「應繳未繳」（報表以團員 × 期別 join 導出，不預建列）。

`MembershipFee.status`（應繳未繳/待確認/已繳/作廢）取代原本「有無 `paid_at`」的兩態判斷，
`is_paid` 改看 `status==paid`；「待確認」為 S2 團員自助申報預留，S1 只用到 應繳未繳/已繳/作廢。

**為什麼會費與收支明細分開？**
會費有「期別 + 每人繳沒繳」的追蹤需求，和一般收支性質不同，故各自一個 model。但兩者已於 §9 S3 串接：
**確認繳費時自動產生一筆對應的 FinanceRecord 收入**（分類=會費、日期=收款日、金額快照，經
`MembershipFee.finance_record` 連結），作廢/退回/硬刪時連動移除。因此「財務總收入」與「當年度收支」
（`annual_report`，按收款日年份彙總）天然涵蓋會費——**不需、也不可再手動於收支明細登記會費收入**。

會費期別/繳納/確認/自動入帳的完整設計、view、nav、刪除層級，詳見附錄五 §9。

---

### 4.8 樂譜庫存（scores）

**檔案**：`apps/scores/models.py`、`apps/scores/views.py`

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
        if self.full_score:
            raise ValidationError('總譜不應指定所屬總譜。')
    elif self.score_type == self.ScoreType.PART:
        if not self.instrument:
            raise ValidationError('分譜必須指定樂器。')
        if self.full_score and self.full_score.score_type != self.ScoreType.FULL:
            raise ValidationError('所屬總譜必須是總譜類型。')
```

#### 總譜與分譜的關聯

分譜透過 `full_score` FK 指向其所屬的總譜：

```
Score（天空之城，total）
    ├── Score（天空之城，Bb 豎笛，第一部）→ PDF
    ├── Score（天空之城，Bb 豎笛，第二部）→ PDF
    └── Score（天空之城，長笛）→ PDF
```

`full_score` 使用 `CASCADE`，刪掉總譜時所有分譜一併刪除。
透過 `score.parts.all()` 可取得該曲目的所有分譜。

#### 分譜上傳 UI（score_parts_manage）

路由：`/scores/<pk>/parts/`，幹部限定。

UI 為四層式結構：
- 第一層：樂器大分類（木管／銅管／打擊／其他）為主標題 `<h4>`
- 第二層：樂器族群（InstrumentFamily）為次標題 `<h5>`
- 第三層：若族群只有一種樂器，直接列聲部（不重複顯示樂器名）；若有多種則再加一層樂器名
- 第四層：每個樂器下方列出所有聲部（第一部、第二部、第三部、Solo）checkbox
- 勾選後顯示 PDF 上傳欄位
- 已上傳的分譜顯示「已上傳」標示與下載連結，再次上傳可替換

view 在 GET 時預先建立巢狀資料結構（`categories_data`）供 template 直接迭代，
避免 template 內複雜的 dict 查找邏輯。`categories_data` 結構為：
`[{category_label, families: [{family, instruments: [{instrument, sections: [{section, key, existing_part}]}], single}]}]`

#### 樂器族群（InstrumentFamily）

新增族群層級，讓分譜上傳 UI 可按族群分組顯示樂器：

```
木管
  └── 豎笛族
        ├── Eb 豎笛
        ├── Bb 豎笛
        ├── 中音豎笛
        └── 低音豎笛
  └── 薩克斯風族
        ├── 中音薩克斯風
        └── ...
銅管
  └── 小號族
        └── 小號
  └── ...
```

預設資料儲存在 `fixtures/instruments.json`（12 族群、24 種樂器）
與 `fixtures/sections.json`（第一部〜第四部、Solo）。

#### 新增／編輯樂譜（score_create / score_edit）

路由：`/scores/create/`、`/scores/<pk>/edit/`，皆幹部限定。原本「新增樂譜」「編輯」按鈕都直接連到
Django Admin 的頁面，但一般 `officer` 角色沒有 `is_staff`（見 §2 `is_staff` 自動設定），
無法進入 `/admin/`，等於幹部點了按鈕卻進不去——`score_edit` 是後來才發現的同一種問題，
`score_detail.html` 的「編輯」連結曾經漏了修，和 `score_create` 一起補齊。

兩個 view 共用同一套邏輯，避免寫兩份重複的欄位解析與驗證：

```python
def _apply_score_form(request, score):
    """把 POST 資料寫進 score 實例（新建或既有皆可），回傳 errors 清單"""
    ...
    score.title = request.POST.get('title', '').strip()
    ...
    if not errors:
        try:
            score.full_clean()   # 沿用 Model 既有的 clean() 規則，不重複造輪子
        except ValidationError as e:
            ...
    return errors
```

`score_create` 傳入一個空的 `Score()`；`score_edit` 傳入 `get_object_or_404(Score, pk=pk)` 取出的既有實例，
兩者都呼叫 `_apply_score_form()` 寫入欄位再 `full_clean()`，驗證邏輯完全一致。

表單依 `score_type` 用純 JS 顯示/隱藏「樂器」「聲部」欄位（總譜不需要，分譜必填樂器）。

#### 編輯頁的欄位預先帶入：form_data

`score_create` 的 GET 沒有既有資料，欄位一律空白；`score_edit` 的 GET 則要把既有樂譜的值填進表單。
兩者共用同一份 `score_form.html`，為了不在 template 裡到處寫「有 POST 用 POST、沒有就用 score 的值」
這種條件判斷，改在 view 層統一組出一個 `form_data` 字典再傳給 template：

```python
'form_data': request.POST if request.method == 'POST' else _initial_form_data(score),
```

`_initial_form_data()` 把 `score` 的欄位轉成跟表單欄位同名的字典（FK 欄位轉成字串 pk，對應 `<select>` 的 value）。
Template 只需要統一寫 `{{ form_data.title }}`，不論是新增頁（空字典）、編輯頁 GET（既有資料）、
或驗證失敗重新顯示（使用者剛送出的值）都適用同一套寫法。

#### 為什麼 file 欄位沒有值就不覆蓋

```python
file = request.FILES.get('file')
if file:
    score.file = file
```

編輯時如果沒有重新選檔案，`request.FILES` 就不會有 `file` 這個 key，這裡刻意只在有上傳新檔案時才覆寫，
避免使用者只是想改個曲名，卻不小心把已上傳的 PDF 清空。

#### 分譜跟總譜的綁定：score_create / score_edit 也能指定 full_score

早期版本 `score_create` / `score_edit` 完全不提供 `full_score` 欄位，理由是「避免和
`score_parts_manage` 的批次上傳流程產生兩套重複入口」。但這樣一來，如果使用者用「新增樂譜」
分別建一筆總譜跟一筆分譜（而不是透過總譜詳情頁的「管理分譜」上傳），兩筆記錄之間完全沒有關聯，
分譜不會出現在總譜的「分譜清單」裡，變成一筆孤立紀錄——這是實際使用時發現的問題，不是刻意設計。

現在 `score_type` 選「分譜」時，表單多一個「所屬總譜」下拉選單（選填），`_apply_score_form()`
會依 POST 的 `full_score` 設定關聯；選「總譜」時無論 POST 帶了什麼值都會被忽略
（`full_score` 設回 `None`，跟 `instrument`/`section` 同樣的處理方式）。

`score_parts_manage` 的批次上傳流程仍然保留，並沒有被取代——兩者現在是兩條都能正確綁定關聯的路徑，
差別只在於 `score_parts_manage` 一次可以处理多個樂器/聲部的分譜上傳，`score_create`/`score_edit`
一次只處理一筆。

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

`ForeignKey('self', ...)` 是指向同一張表的外鍵，用來表達「改版自哪個版本」（與 `full_score` 語意不同）：

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

#### score_delete：刪除限管理員

跟 `member_delete`／`event_delete`／`venue_delete` 是同一套「管理員限定」的權限模式
（`admin` 角色或 `superuser`）。樂譜被引用的方式有兩種，處理方式不同：

- `Setlist.score`、`ScoreExchangeItem.score` 都是 `PROTECT`——這是資料庫層級的硬限制，
  管理員也無法繞過，`score_delete` 用 `try/except ProtectedError` 包成友善訊息，不會噴 500。
- `Score.full_score`（分譜指向所屬總譜）是 `CASCADE`——刪除總譜會連帶刪除底下所有分譜，
  這是既有預期行為（見前面「總譜與分譜的關聯」一節），不需要額外保護。

不像 `member_delete` 需要 `Collector` 判斷「有沒有關聯紀錄才放行真刪除」，樂譜這邊直接讓
`PROTECT` 擋、`CASCADE` 放行即可，因為分譜隨總譜刪除本來就是設計上允許的，不像團員的出席/請假
歷史需要額外一層保護。

刪除入口放在 `score_list` 跟 `score_detail` 兩處（管理員限定），跟演出活動同樣的考量：
列表頁方便一次瀏覽多筆樂譜時清理，詳情頁方便正在檢視某份樂譜時順手刪除。

#### score_list 顯示分譜的所屬總譜

分譜現在可能綁定 `full_score`（見前一節），列表頁「類型」欄位除了樂器/聲部之外，
再多顯示一行「屬於《總譜名稱》」（連結到該總譜的詳情頁），沒有綁定的分譜則顯示「未綁定總譜」
提示文字，讓幹部一眼看出哪些分譜還是孤立紀錄、需要補綁定。`score_list` 的 `select_related`
補上 `full_score`，避免分頁 30 筆時產生 N+1 查詢。

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

#### 可見性過濾邏輯（`_visible_visibilities` / `_visible_announcements`）

可見性只寫一次，放在 `_visible_visibilities()`；它回傳的順序同時就是列表頁三區
「由上而下」的排列順序，所以「誰看得到」與「怎麼排版」不會各寫一套：

```python
def _visible_visibilities(user):
    """可見的 visibility，依 幹部限定 → 團員限定 → 公開 由上而下排列。"""
    if not user.is_authenticated:
        return (Visibility.PUBLIC,)
    if user.is_officer:
        return (Visibility.OFFICER_ONLY, Visibility.MEMBER_ONLY, Visibility.PUBLIC)
    return (Visibility.MEMBER_ONLY, Visibility.PUBLIC)


def _visible_announcements(user):
    qs = Announcement.objects.filter(published_at__isnull=False).select_related('created_by')
    return qs.filter(visibility__in=_visible_visibilities(user))
```

列表頁與詳情頁共用 `_visible_announcements()`，詳情頁直接對這個 QuerySet 做
`get_object_or_404`，無需再重複寫可見性判斷。

#### 列表頁三區版面（#13-3，2026-08-29）

列表頁由上而下分 **幹部限定 → 團員限定 → 公開** 三區，每區一個標題徽章。
看得到幾區完全跟著 `_visible_visibilities()` 走——幹部三區、團員下兩區、未登入只有公開區。

QuerySet 只查一次、在 Python 端分組（公告量小，`select_related('created_by')` 已避免 N+1），
不是每區各發一次查詢。**某一區沒有公告時仍然顯示標題與「這一區目前沒有公告。」**，
讓版面結構固定，不會因為某層剛好空著就少一塊、讓人誤以為沒有這一層。

#### 導覽列入口必須在登入判斷之外（2026-08-29 修正的 bug）

公開公告本來就允許未登入者瀏覽，`_visible_announcements()` 對未登入者也一直回傳正確結果，
但 `templates/base.html` 曾把公告連結包在 `{% if user.is_authenticated %}` 裡，
未登入者的導覽列上根本沒有入口，只能手打網址才進得去（demo 當天被幹部發現）。
公告連結現在放在登入判斷之外，與「關於百韻」「組織章程」同一層；
`AnnouncementListTest` 有一條測試守住這件事，避免日後整理導覽列時又被搬回 if 裡。

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

首頁對**未登入者**顯示靜態內容；對**已登入者**額外查詢資料，組成個人化 Dashboard：

```python
# 下次排練：當天的排練整天都留著，隔天才換下一場（見下方「為什麼不是 date > now」）
rehearsal, started = _dashboard_rehearsal(timezone.now())
context['next_rehearsal'] = rehearsal
context['next_rehearsal_started'] = started

# 我的待審請假（提醒團員有哪些申請尚未被幹部處理）
context['pending_leaves'] = (
    LeaveRequest.objects
    .filter(member=request.user, status=LeaveRequest.Status.PENDING)
    .select_related('rehearsal__event')
    .order_by('rehearsal__date')
)

# 我的請假審核結果（核准/拒絕後尚未在首頁看過的通知，見下方說明）
reviewed_leaves = list(
    LeaveRequest.objects
    .filter(member=request.user, result_seen=False)
    .exclude(status=LeaveRequest.Status.PENDING)
    .select_related('rehearsal__event')
    .order_by('-reviewed_at')
)
context['reviewed_leaves'] = reviewed_leaves
if reviewed_leaves:
    LeaveRequest.objects.filter(pk__in=[leave.pk for leave in reviewed_leaves]).update(result_seen=True)

# 幹部專屬：待審核的入團申請數（顯示提醒徽章）
if request.user.is_officer:
    context['pending_registrations_count'] = (
        Registration.objects.filter(status=Registration.Status.PENDING).count()
    )
```

**設計考量：**
- 各查詢彼此獨立，無 N+1 問題（`select_related` 處理關聯）
- `pending_registrations_count` 只給幹部，一般團員不需要看這個數字
- import 放在 `if request.user.is_authenticated` 內部，避免未登入時引發不必要的查詢

#### 為什麼「下次排練」不是 `date > now`

原本的查詢是 `filter(date__gt=timezone.now())`，只抓「開始時刻還沒到」的排練。
問題是排練 19:00 開始，**19:01 之後首頁顯示的就是下一場了**——而團員最需要簽到、
看排練日誌的時間點正好在那之後。2026-09-19 幹部試用回饋「我想要排練的時候簽到，
但沒有找到簽到按鈕或 QR code」，追下去發現原因不只是簽到入口，
還有這張卡片在排練當下就換掉了。

改法在 `_dashboard_rehearsal(now)`：

| 情況 | 顯示哪一場 | `next_rehearsal_started` |
|------|-----------|:---:|
| 今天已經有排練開始了 | 今天**最近開始**的那場 | `True` |
| 今天還沒有排練開始 | 最近一場未來的排練 | `False` |
| 兩者皆無 | 不顯示卡片 | `False` |

邊界取「當天 23:59」而不是排練的結束時間，是因為 `Rehearsal` 沒有結束時間欄位，
而請假截止 `day_end`（#13-7）已經是同一套「當天」推導——**不另立第二種時間慣例**。
`Rehearsal.time_slot` 雖然可以間接拿到 `VenueTimeSlot.end_time`，但它是選填的，
用了會變成「有綁時段的排練晚上九點消失、沒綁的留到半夜」，兩種行為更難解釋。

實作上「當天 23:59 還沒過」等價於「`date >= 本地今天 00:00`」，所以不需要在 Python
端逐筆過濾，兩個查詢就夠：先找今天已開始的（`date` 介於今天 00:00 與 now，取最晚的），
沒有才找未來最近的一場。

卡片本身也跟著調整（`templates/public/index.html`）：已開始時標題改成「今天的排練」
並加上「進行中」徽章；另外固定顯示一行**路徑標示**「演出活動 › 活動名 › 第 N 次排練」，
讓人知道這張卡片的內容平常自己要從哪裡點進去——同一輪回饋反映導覽找不到東西，
與其只補捷徑，不如順便教會使用者原本的動線。

#### 為什麼「待審核」清單看不到核准/拒絕結果，要另外查一次

`pending_leaves` 只查 `status=pending`，核准或拒絕後這筆申請直接從清單消失，
團員完全看不到任何結果通知，只能自己想到要去「我的請假」查——這是實測時發現的落差
（見附錄五第 6 項），不是刻意設計。

`reviewed_leaves` 用 `result_seen` 這個欄位解決「團員有沒有看過這個結果」的問題：

```python
result_seen = models.BooleanField('團員已讀審核結果', default=True, ...)
```

- `leave_review_list` 核准/拒絕時把 `result_seen` 設回 `False`，代表「有新結果團員還沒看過」
- 首頁 `index` view 查出所有 `result_seen=False` 的已審核申請，顯示成通知，**同一次 request
  裡就把它們標記回 `result_seen=True`**——不需要團員多點一下「已讀」，看到首頁就算已讀
- 欄位預設值刻意設成 `True`（不是 `False`）：這樣加欄位的 migration 套用時，既有的歷史核准/
  拒絕紀錄不會被當成「新結果」瞬間全部跳出來洗版，只有欄位加入後才審核的申請才會走這套通知流程

沒有用「時間視窗」（例如「審核時間在最近 3 天內」）判斷是否顯示，是因為時間視窗會有兩種問題：
團員太久沒登入就會錯過通知（超出視窗就消失了），或是團員每天都登入就會重複看到同一筆好幾天
（視窗內反覆出現）。已讀旗標可以精準地「看過一次就不再顯示」，不受登入頻率影響。

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

#### score_list：只列總譜（#13-4）

清單**固定只列總譜，分譜完全不出現**——要看分譜一律從總譜詳情頁進去：

```python
scores = (
    Score.objects.filter(score_type=Score.ScoreType.FULL)
    .annotate(part_count=Count('parts'))
)

instrument_id = request.GET.get('instrument', '')  # 樂器 ID
query         = request.GET.get('q', '').strip()   # 曲名關鍵字（icontains）

if instrument_id:
    scores = scores.filter(parts__instrument_id=instrument_id).distinct()

paginator = Paginator(scores, 30)  # 每頁 30 筆
```

**為什麼分譜不列**：一首曲子動輒 20〜30 份分譜，混在清單裡會把總譜完全淹沒，
而「找某首曲子的某個分譜」的實際動線本來就是「先找到曲子、再挑聲部」，
總譜詳情頁的分譜清單正好就是那一步。演出當天的分譜下載另有 `performance_parts` 專屬入口。

**連帶的兩項調整**：

| 項目 | 改法 | 原因 |
|------|------|------|
| 「譜種」篩選器 | 移除 | 清單只剩一種譜種，篩了沒意義 |
| 「樂器」篩選器 | 語意改為「底下有這個樂器分譜的總譜」 | 樂器是分譜才有的屬性（`Score.instrument`），總譜恆為 `NULL`；沿用舊的 `filter(instrument_id=...)` 會永遠篩不出東西 |

樂器篩選改走 `parts__instrument_id` 反向 join。同一總譜底下同一樂器可能有多個聲部
（第一部／第二部…），join 會產生重複列，**必須加 `distinct()`**。

「類型」欄位（每列都是「總譜」，沒有資訊量）改為 **分譜份數**，用 `annotate(Count('parts'))`
一次算完，避免每列各發一次 count 查詢。

#### 未綁定總譜的分譜：清單頁的幹部警告區

`Score.full_score` 是 `null=True`，`clean()` 也沒強制分譜必須綁總譜，
因此可能存在「分譜但沒有所屬總譜」的資料。**#13-4 之後這種資料會失去所有入口**——
清單不列分譜，總譜詳情頁又找不到它，等於憑空消失。

不改 model（加 NOT NULL 要處理既有資料、且 `score_parts_manage` 上傳的分譜本來就一定有總譜），
改在 `score_list` 撈出這批孤兒、以**幹部限定**的警告卡片列出，點進去可編輯補綁定：

```python
orphan_parts = []
if request.user.is_officer:
    orphan_parts = list(
        Score.objects.filter(score_type=Score.ScoreType.PART, full_score__isnull=True)
        ...
    )
```

一般團員看不到——那是資料錯誤，不是他們要處理的事。
分譜詳情頁同步補上「所屬總譜」連結（沒綁的顯示警告），讓進到分譜頁時有回頭路。

#### 分譜的唯一入口（#13-4 的補救）

清單不列分譜之後，**總譜詳情頁的分譜清單就是進入分譜的唯一入口**。
初版只在那裡放了「下載」連結、沒有連到分譜詳情頁，結果是已綁定的分譜
**編輯不到也刪不掉**——庫存清單已經不列它，而分譜清單只給下載。
（`score_detail` / `score_edit` / `score_delete` 三個 view 本身都好好的，缺的只是那條連結。）

修法是分譜清單每一格補一個「詳細」連結。`ScoreDetailViewTest` 有一則測試專門釘住這條路，
避免日後改版又把它拿掉。

順帶調整 `score_delete` 的導向：**刪掉分譜後導回所屬總譜**，不是導回清單。
清單已經不列分譜，導回清單等於把幹部丟在找不到原本那首曲子的地方；
導回總譜則可以接著處理同一首的其他分譜。刪掉總譜時沒有可回去的曲目，維持導回清單。

#### 麵包屑保留列表篩選條件

`score_list` 的「詳細」連結、`score_detail` 的麵包屑「樂譜庫存」連結，
都用 `{% if request.GET %}?{{ request.GET.urlencode }}{% endif %}` 把目前的 query string 原樣轉發：

```
score_list（?q=天空&instrument=3）→ 詳細 → score_detail?q=天空&instrument=3 → 麵包屑 → score_list?q=天空&instrument=3
```

純 template 端處理，不需要 view 額外傳參數（`request` context processor 已在 `settings.py` 啟用）。
沒有帶查詢字串進入詳情頁時，麵包屑就連回不帶參數的預設列表，行為不變。

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

### 報表：團員通訊錄名冊（accounts）

**檔案**：`apps/accounts/views.py`（`member_directory_report`）、路由：`/accounts/directory/report/`

**幹部限定**（含電話／Email），比照上述四張報表：套用 `@media print` 樣式、附報表日期與列印按鈕。
資料與分組跟通訊錄頁一致（依樂器族群分類：木管 → 銅管 → 打擊 → 其他 → 未分類），
沿用通訊錄的 `status` 參數（在團／已退團／全部），預設只印在團名單。入口在通訊錄頁的「列印名冊」
按鈕，會把當前 `status` 篩選一併帶入報表。

> 沒有給它一個 4.x 節號，是因為報表群（4.14〜4.17）與其後 4.18〜4.21 的節號已排定，
> 為一張衍生報表重排全部編號不划算；歸類上它屬於「報表」群組。

---

### 4.18 LINE 群組通知（notifications）

**檔案**：`apps/notifications/utils.py`（推播工具函式）

**設計方向**：Push-only，Bot 加入 LINE 群組後統一推播，不需要個人帳號綁定。

#### 環境設定

```
LINE_CHANNEL_ACCESS_TOKEN=...   # Messaging API channel token
LINE_GROUP_ID=...               # Bot 加入群組後取得，存於 .env
```

#### 核心工具函式

```python
def push_line_message(text: str) -> None:
    """推播純文字訊息到 LINE 群組，失敗時 silent fail（記 log，不中斷主流程）"""
```

呼叫 LINE Push API（`https://api.line.me/v2/bot/message/push`），失敗不拋例外，避免通知失敗影響主要操作。

#### 觸發點與訊息內容

| 觸發事件 | 呼叫位置 | 訊息內容 |
|---------|---------|---------|
| 幹部新增排練 | `rehearsal_create` view | 排練時間、場地、所屬演出 |
| 幹部新增演出活動 | `event_create` view | 演出名稱、類型、預定日期 |
| 排練資訊異動 | `rehearsal_edit` view | 異動後的時間與場地 |
| 幹部發布公告 | `announcement_publish` view | 公告標題（public / member_only，officer_only 不推）|
| 演出曲目確定（手動觸發）| 幹部操作 | 通知團員登入網站下載分譜 |

#### 設計選擇：silent fail

通知失敗不應中斷主要操作（新增排練成功比通知更重要）。
推播失敗時記錄 log，讓幹部知道通知未送出，但 view 照常 redirect。

---

### 4.19 演出分譜下載（scores）

**檔案**：`apps/scores/views.py`（`performance_parts`）、路由：`/scores/performance/<pk>/parts/`
入口：演出活動詳情頁「演出曲目」卡片的「我的分譜」按鈕（有排定曲目時才顯示）。

**登入者可用**，依登入者的樂器族群，自動篩選出這場演出曲目單裡用得到的分譜。

#### 資料查詢邏輯

```python
parts = Score.objects.filter(
    score_type=Score.ScoreType.PART,
    full_score__setlists__event=event,           # 分譜的總譜有被排進這場演出
    instrument__family=request.user.instrument,  # 依登入者的樂器族群
).select_related('instrument', 'section', 'full_score').distinct()
```

關聯路徑是 **PerformanceEvent → Setlist.score（總譜）→ Score.parts（分譜）**，不是直接從分譜連到演出。
分譜透過 `full_score` 掛在總譜下，被 `Setlist` 排進演出的是總譜，所以要用 `full_score__setlists__event`
反查。查完依所屬總譜（曲目）分組，前端一首一首列出。

> **⚠️ 樂器層級差一層（實作時的關鍵修正）**
> `User.instrument` 指向 **`InstrumentFamily`（族群）**，而 `Score.instrument` 指向
> **`InstrumentType`（具體樂器）**，兩者不同層級。所以不能寫 `instrument=request.user.instrument`
> （型別對不上），必須用 `instrument__family=request.user.instrument` 以族群比對。
> 本節早期曾寫成 `setlist__event` ＋ `instrument=user.instrument`，兩處都與實際 Model 對不上，
> 2026-07-31 實作時依真實 schema 修正。

#### 顯示規則：族群內全列，讓團員自選

同族群底下各具體樂器／聲部的分譜全部列出（例：薩克斯風族會同時出現中音、次中音…各聲部），
有 PDF 的顯示下載按鈕，沒 PDF 的顯示「尚未上傳」。

#### 設計選擇：不強制指定聲部

指揮可能在排練過程中調度聲部，事先指定每位團員的聲部會增加維護負擔。
系統只負責篩選「正確樂器族群」的譜，由團員登入後自行判斷要下載哪個聲部——
這也正好呼應「User 只記錄到族群層級」的資料設計：族群篩選是現有欄位能做到的最精準篩選。

#### 邊界情況

| 情況 | 前端顯示 |
|------|---------|
| 登入者未設定樂器族群（`User.instrument` 為空）| 提示請洽幹部設定，並附樂譜庫存連結 |
| 這場沒有該族群的分譜 | 友善訊息（可能尚未上傳或曲目未排定）|

---

### 4.20 關於百韻內容管理（public）

**檔案**：`apps/public/models.py`（`AboutSection`）、`apps/public/views.py`

#### 設計方式：多區塊（方案 B）

「關於百韻」頁面由多個獨立的 `AboutSection` 區塊組成，每個區塊有標題、內文、顯示順序與公開狀態。
幹部可新增、編輯、刪除各區塊，不需要動 HTML。

選擇多區塊而非單一 Model 的理由：彈性高，未來可分區介紹樂團歷史、指導老師、各組組介等，
不需要改 Model 或 Migration，只要新增區塊即可。

#### 草稿機制

`is_visible=False` 的區塊不會出現在公開頁面，但在管理頁仍可見（標示「隱藏」）。
適合先準備好內容再決定是否公開。

#### 公開頁面查詢

```python
sections = AboutSection.objects.filter(is_visible=True)
# ordering = ['order', 'id']，同順序時依建立先後排列
```

#### 刪除設計

刪除區塊無 cascade 風險（無 FK 關聯），附 `confirm()` 對話框確認即可，不需要 modal。

---

### 4.21 組織章程管理（public）

**檔案**：`apps/public/models.py`（`CharterContent`）、`apps/public/views.py`

#### 設計方式：單一可編輯文件

組織章程是一份正式文件，不是可任意增刪排序的多區塊內容，因此採用單一 row 設計，與 `AboutSection` 的多區塊方式不同。

| 比較點 | 關於百韻（AboutSection）| 組織章程（CharterContent）|
|--------|----------------------|------------------------|
| 筆數 | 多筆（每區塊一筆）| 固定一筆（pk=1）|
| 管理介面 | 新增 / 編輯 / 刪除 / 排序 | 只有「編輯全文」|
| 草稿機制 | `is_visible` 欄位 | 無（章程無草稿需求）|

#### 單一 row 的實作方式

```python
# view 取章程：沒有資料時回傳 None，template 顯示佔位文字
charter = CharterContent.objects.first()

# 幹部儲存：pk=1 保證只有一筆，get_or_create 避免重複建立
charter, _ = CharterContent.objects.get_or_create(pk=1)
charter.content = new_content
charter.save()
```

`updated_at = auto_now=True`，每次儲存自動更新，公開頁面顯示「最後更新：XX 年 X 月 X 日」。

---

### 4.22 演出出席意願（events）

**檔案**：`apps/events/views.py`（`performance_intent_set`、`performance_intent_report`、
`event_detail`）、`apps/events/models.py`（`PerformanceAttendance`）

> **沿革**：本節原為「演出請假」（附錄五 §2，2026-08-04 實作）。2026-09-07 依 #13-6 改為
> **出席意願三態**，`PerformanceLeaveRequest` 整個 model 連同審核頁、首頁通知一併移除。
> 原因是幹部回饋「演出應視為該活動的最後一場排練」，不該另開一套審核流程。

#### 三態：待確認 / 確認參加 / 不參加

| 團員做了什麼 | `intent` |
|-------------|----------|
| 按「確認參加」 | `confirmed` |
| 送出「不參加」＋原因 | `declined` |
| **兩者都沒做** | `pending`（待確認）← 由幹部主動聯繫 |

**不需審核**：團員自己按，幹部在統計頁看結果。演出既然當成一次特別團練，就不另開流程。

#### 為什麼是「三態 intent ＋ 布林 attended」，不是別的組合

| 曾經的做法 | 為什麼不行 |
|-----------|-----------|
| 兩個布林 `confirmed` + `on_leave`（舊實作）| 四種組合裡「confirmed=True 且 on_leave=True」是矛盾的，而且**沒有任何程式碼阻止它發生** |
| 用單一欄位同時表示「事前意願」與「事後到場」| 會失去**「說要來但沒到」**這個最需要追蹤的情況 |
| **三態 intent ＋ 獨立的 attended（採用）**| 矛盾狀態直接不可表示；事前、事後各自獨立 |

原本的 `confirmed`（事後到場）一併**改名為 `attended`**——留著 `confirmed` 會和
`intent='confirmed'`（事前確認參加）望文生義撞在一起，這種同名不同義最容易讀錯。

#### 沒有紀錄 = 待確認（統計頁的關鍵）

團員不表態就不會有 `PerformanceAttendance` 列。所以統計頁**從團員名單反推、不是掃 attendance 表**：

```python
members = User.objects.filter(is_active=True).exclude(role__in=[ADMIN, GUEST])
attendances = {a.member_id: a for a in PerformanceAttendance.objects.filter(event=event)}
# 沒有對應紀錄的人 → PENDING
```

只掃 attendance 表會把「都沒表態的人」整批漏掉，而那正是幹部要追的對象（#13-5）。
lookup table 也順便避免逐位團員各查一次的 N+1。

統計頁**依聲部分組**，方便日後分部長（#14）認領自己聲部的待確認名單。

#### 表態期限

`performance_date <= now` 時 server 端直接擋，不只靠前端 disabled——避免直接 POST 繞過。

> ⚠️ **與 #13-7 的連動**：排練請假的截止點即將改為「當天 23:59」，屆時這裡要**一併改**，
> 兩者規則必須同步，否則同一場活動的排練與演出會有兩套不同的截止邏輯。
> 程式碼中已標 `TODO(#13-7)`。

#### Migration 的兩個資料保護

`events/0009` 是手寫調整過的，自動產生的版本會丟資料：

1. **`confirmed` → `attended` 用 `RenameField`**，不是「刪一個加一個」——後者會清空既有到場紀錄。
2. **`on_leave=True` → `intent='declined'` 的資料搬遷**排在 `RemoveField` 之前。
   那些人的「我不參加」是真實表態過的資訊，不該隨欄位一起消失。
   反向不提供：三態塌回布林必然遺失「待確認」與「不參加」的區別。

---

## 附錄二：確認無問題的項目

審計過程中懷疑但確認正確的項目，避免日後重複誤判。

| 疑似問題 | 確認結果 |
|---------|---------|
| `member_directory` instrument=None 會 500 | 已有 `if member.instrument else '未分類'` 守衛（`views.py:53`） |
| `rehearsal.date` 與 `timezone.now()` 型別不符 | `date` 是 `DateTimeField`，timezone-aware 比較正確 |
| `finance/views.py` 空期別時 `periods[0]` IndexError | `if not selected_period and periods:` 空 queryset 為 falsy，已守衛 |
| `setlist_manage` order 傳字串給 IntegerField | Django ORM 自動轉型，正常運作 |
| QR 簽到任何人都可以簽 | 刻意設計：持有 token URL 才能進入，不需角色限制 |

---

## 附錄三：設計選擇備忘

記錄不直覺但有意為之的設計，避免日後被誤當成 bug 修掉。

- **`leave_stats` 只顯示有申請記錄的團員**：沒有申請過的人不出現，避免空資料行造成誤讀。
- **出席報表包含 OFFICER role**：`attendance_report` 排除 `role=ADMIN`，幹部（OFFICER）仍在列，符合業務需求。
- **`borrow_status_report` 逾期判斷為 `due_date < today`**：到期當天不算逾期，符合一般直覺。
- **LINE 群組通知 silent fail**：推播失敗不中斷主流程，記 log 即可，新增排練成功比通知更重要。
- **演出分譜下載不強制指定聲部**：指揮可能在排練中調度聲部，由團員自行選擇，系統只篩選正確樂器。
- **新建團員帳號一律用臨時密碼、不留空**：曾考慮讓密碼留空（unusable password）讓團員自己設定，
  但那樣任何知道帳號的人都能不驗證密碼直接搶先設定新密碼，等於帳號劫持。
  臨時密碼隨機產生、寄信給本人，寄信失敗才退回畫面顯示（見 §4.2），且只出現一次，不寫入 log。
- **團員退團用 `is_active=False`（軟刪除），不是真的刪除**：`User` 被出席/請假/借用/財務/公告等多張表
  CASCADE 參照，真刪除會連帶砍光歷史紀錄。只有完全沒有關聯紀錄的帳號（如剛新增打錯）才允許真刪除，
  用 Django `Collector` 判斷，注意 `collector.fast_deletes` 這個坑（見 §4.2「fast_deletes 的坑」）。
- **`PerformanceAttendance` 用「三態 `intent` ＋ 布林 `attended`」，不是單一欄位也不是兩個布林**：
  `intent` 是事前意願（待確認／確認參加／不參加）、`attended` 是演出當天事後到場，兩者刻意分開——
  共用一個欄位會失去「說要來但沒到」這個最需要追蹤的情況。
  也刻意不沿用舊的兩個布林（`confirmed` + `on_leave`），那組合會產生「兩個都 True」的矛盾狀態
  且無程式碼阻止；三態單一欄位讓矛盾直接不可表示（見 §4.22）。
- **自訂 `LOGGING`，不沿用 Django 預設**：預設的 console handler 帶 `require_debug_true`，
  `django.request`（500 的 traceback）實際上只走 `mail_admins`——也就是 `DEBUG=False` 的測試站
  噴 500 時，Render 的 Logs 什麼都看不到，線上出錯無從查起。改成一律寫 stderr（PaaS 慣例：
  不寫 log 檔，容器重啟就沒了，交給平台收）。等級由 `DJANGO_LOG_LEVEL` 控制，預設 `INFO`，
  但 `django.request` 固定 `ERROR` 且不受它影響。
- **演出「沒有出席紀錄」等於「待確認」，不預先建列**：硬建一筆反而分不出「按過」與「沒按過」，
  而「沒按過的人」正是幹部要追的對象。統計因此從團員名單反推、不掃 attendance 表（見 §4.22）。

---

## 附錄四：待評估項目（未修正）

> 📦 已移至 [BACKLOG.md](BACKLOG.md)（編號不變）。程式碼／文件裡「DESIGN 附錄四」的指引，到 BACKLOG.md 找同編號即可。

## 附錄五：待開發功能構想（未設計，待討論）

> 📦 已移至 [BACKLOG.md](BACKLOG.md)（編號不變，含優先權表與 #1~#16）。程式碼／文件裡「DESIGN 附錄五 #N／§N」的指引，到 BACKLOG.md 找同編號即可。

---

## 附錄一：常見 Django 概念速查

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
