# FJCWO-Web 架構文件

> 最後更新：2026-04-14（補充請假申請流程、頁面結構、文件實際比對，共 24 張 Model）
> 本文件記錄系統架構決策與設計規劃，供開發參考。

---

## 一、技術決策紀錄

### 為什麼從 Hugo 改用 Django？

Hugo 是靜態網站生成器，無法做到真正的權限控制。
任何「隱藏」的內容只要按 F12 或直接進入網址就能看到，不適合存放財務資料或會員資訊。

本系統需要以下功能，已超出靜態網站範疇：
- 會員登入與角色區分（團員 / 幹部）
- 幹部限定頁面（財務、通訊錄）
- 多個需要狀態追蹤的借用系統
- AI 語音辨識與摘要

### 技術選型

| 項目 | 選擇 | 理由 |
|------|------|------|
| 後端框架 | Django 6.x | 內建 Auth、Admin 後台、穩定長期維護 |
| 資料庫 | PostgreSQL | 支援 django-tenants 的 Schema 隔離 |
| 前端 | Bootstrap 5 | 輕量、維護簡單、無需 JS 框架 |
| 多租戶 | django-tenants | 預留未來 SaaS 擴充空間 |
| 通知 | LINE Bot | 台灣普及率高，團員不需安裝額外 APP |
| 語音辨識 | OpenAI Whisper | 免費開源，可在自架伺服器執行 |
| AI 摘要 | Claude API | 按使用量計費，金額極低 |
| 部署 | Nginx + Gunicorn | 自架伺服器（汰換電腦 + 中華電信固定 IP）|

### 未來 SaaS 方向

若系統發展成熟，計畫開放給其他管樂團使用。
屆時以**子網域**區隔各樂團（如 `fjcwo.system.com`、`ntuso.system.com`），
資料透過 PostgreSQL Schema 完全隔離，互不干擾。

---

## 二、系統清單

| # | 系統名稱 | 開放對象 | 開發階段 |
|---|---------|---------|---------|
| 1 | 公開網站（關於、章程、活動） | 所有人 | Phase 1 |
| 2 | 會員登入 + 角色管理 | 所有人 | Phase 1 |
| 3 | 演出活動 + 排練管理 + QR 簽到 | 團員 / 幹部 | Phase 2 |
| 4 | LINE Bot 通知 | 團員 / 幹部 | Phase 2 |
| 5 | 財務管理 | 幹部 | Phase 2 |
| 6 | 樂譜庫存管理 | 幹部（瀏覽開放團員）| Phase 2 |
| 7 | 公用財產管理 + 借用（樂器為其中一類）| 團員 / 幹部 | Phase 2 |
| 8 | 場地主檔管理 | 幹部 | Phase 2 |
| 9 | 會議紀錄 + AI 語音辨識摘要 | 幹部 | Phase 3 |
| 10 | 演出介紹手冊自動生成 | 幹部 | Phase 3 |

---

## 三、資料庫設計（Model）

### 樂器主檔（InstrumentType）

獨立主檔，供 User、Score、PartAssignment 選取，避免自由輸入造成不一致。

| 欄位 | 說明 |
|------|------|
| name | 樂器名稱（如：長笛、豎笛、小號）|
| category | 分類（木管 / 銅管 / 打擊 / 其他）|

### 聲部主檔（SectionType）

| 欄位 | 說明 |
|------|------|
| name | 聲部名稱（如：第一部、第二部、第三部）|

### 使用者（User）

自訂 User Model，**必須在建立專案初期完成**，之後難以更改。

| 欄位 | 說明 |
|------|------|
| username | 帳號 |
| password | 密碼 |
| name | 真實姓名 |
| email | Email |
| role | 角色：`member`（團員）/ `officer`（幹部）/ `admin`（管理員）|
| instrument | 樂器（關聯 InstrumentType）|
| section | 聲部（關聯 SectionType）|
| grad_year | 畢業年份 |
| phone | 電話（幹部限定可查）|
| line_user_id | LINE 帳號 ID（用於 Bot 推播）|

### 場地主檔（Venue）

獨立管理，建立活動時從清單選取，不需每次重新輸入。

| 欄位 | 說明 |
|------|------|
| name | 場地名稱 |
| type | 場地類別：演出 / 排練 |
| address | 地址 |
| capacity | 容納人數 |
| phone | 場地電話 |
| google_map_url | Google Maps 網址（方便團員導航）|
| contact_person | 場地方聯絡人姓名 |
| contact_phone | 場地方聯絡人電話 |
| transportation | 交通方式（捷運、公車等大眾運輸資訊）|
| motorcycle_parking | 機車可否停放（是 / 否 / 有限制）|
| car_parking | 汽車可否停放（是 / 否 / 有限制）|
| notes | 備註（其他注意事項）|

### 場地時段（VenueTimeSlot）

一個場地可有多個時段，各時段有獨立費用。排練或演出建立時從中選取。

| 欄位 | 說明 |
|------|------|
| venue | 所屬場地（關聯 Venue）|
| is_sun / is_mon / is_tue / is_wed / is_thu / is_fri / is_sat | 適用星期（各自為 Boolean，可多選）|
| start_time | 開始時間 |
| end_time | 結束時間 |
| fee | 該時段費用 |

### 演出活動（PerformanceEvent）

| 欄位 | 說明 |
|------|------|
| name | 活動名稱 |
| type | 類型：音樂會 / 比賽 / 錄音 / 聯演 |
| performance_date | 演出日期時間 |
| performance_venue | 演出場地（關聯 Venue）|
| status | 籌備中 / 確認 / 已結束 |

### 排練（Rehearsal）

每場活動有多次排練，各自有獨立日期與場地。
＊ 標示為必填，其餘可空白（幹部太忙時允許未填）。

| 欄位 | 必填 | 說明 |
|------|------|------|
| event | ✓ | 所屬演出活動（關聯 PerformanceEvent）|
| sequence | ✓ | 排練次數（第幾次排練，可自動依日期順序計算）|
| date | ✓ | 排練日期時間 |
| venue | ✓ | 排練場地（關聯 Venue）|
| time_slot | | 使用時段（關聯 VenueTimeSlot，選填）|
| summary_progress | | 今日進度（排了哪些曲目、哪些段落）|
| summary_improve | | 待改進事項 |
| summary_next | | 下次排練重點 |
| summary_notes | | 給團員的備註 |
| summary_by | | 填寫者（關聯 User）|

### 排練 QR Code Token（RehearsalQRToken）

每場排練產生一個專屬 Token，用於 QR Code 簽到，可控制有效期限與啟用狀態。

| 欄位 | 說明 |
|------|------|
| rehearsal | 哪場排練（關聯 Rehearsal）|
| token | 隨機 UUID |
| created_at | 建立時間 |
| expires_at | 到期時間 |
| is_active | 是否啟用（幹部可手動停用）|

### 排練出席紀錄（RehearsalAttendance）

追蹤每次排練的出席狀況，透過 QR Code 簽到。

| 欄位 | 說明 |
|------|------|
| rehearsal | 哪場排練（關聯 Rehearsal）|
| member | 哪位團員（關聯 User）|
| status | 出席 / 請假 / 缺席 |
| checked_in_at | QR Code 掃描時間（出席才有值）|

### 演出出席確認（PerformanceAttendance）

確認正式演出當天每位上場者是否就位，與排練出席性質不同，獨立記錄。

| 欄位 | 說明 |
|------|------|
| event | 哪場演出（關聯 PerformanceEvent）|
| member | 哪位團員（關聯 User）|
| confirmed | 是否到場（是 / 否）|
| checked_in_at | 確認到場時間 |
| notes | 備註（如：臨時請假原因）|

### 演出曲目（Setlist）

| 欄位 | 說明 |
|------|------|
| event | 所屬演出活動（關聯 PerformanceEvent）|
| score | 哪首曲子（關聯 Score）|
| order | 演出順序 |

### 分譜分配（PartAssignment）

系統根據樂器 + 聲部自動對應，並透過 LINE Bot 通知團員。
（一位團員可能在不同曲目擔任不同樂器或聲部，因此獨立記錄）

`member` 與 `guest_member` 必須恰好填入一個，不可同時填或同時空白。

| 欄位 | 說明 |
|------|------|
| setlist | 哪場演出的哪首曲（關聯 Setlist）|
| member | 正式團員（關聯 User，可空）|
| guest_member | 客座團員（關聯 GuestMember，可空）|
| instrument | 該曲目負責的樂器（關聯 InstrumentType）|
| section | 該曲目負責的聲部（關聯 SectionType）|
| score_part | 對應到哪張分譜（關聯 Score）|

### 財務紀錄（FinanceRecord）

| 欄位 | 說明 |
|------|------|
| type | 收入 / 支出 |
| category | 場地費 / 師資費 / 樂器購置費 / 樂器保養費 / 樂譜費 / 會費 / 其他 |
| amount | 金額 |
| date | 日期 |
| description | 說明 |
| attachment | 收據掃描檔 |
| related_event | 關聯演出活動（選填）|
| created_by | 登記者（關聯 User）|

### 樂譜（Score）

| 欄位 | 說明 |
|------|------|
| title | 曲名 |
| composer | 作曲家 |
| arranger | 編曲者 |
| score_type | 總譜（指揮用）/ 分譜（樂器用）|
| instrument | 樂器（分譜才需填，關聯 InstrumentType）|
| section | 聲部（分譜才需填，關聯 SectionType）|
| copyright_status | 公版 / 有版權 / 已授權 |
| physical_quantity | 實體紙本數量 |
| file | 樂譜 PDF |
| parent_score | 基於哪個版本修改（關聯 Score，原版為空）|
| version_note | 改版說明 |
| source | 來源：購買 / 與他團交換 / 捐贈 |
| publisher | 出版商（購買時填）|
| difficulty | 難度：初級 / 中級 / 高級（選填）|

> 版本鏈：原版 → 改版 v1 → 改版 v2，每個版本透過 parent_score 追溯來源。

### 譜的對外交換（ScoreExchange）

一筆紀錄代表一次完整的交換事件，可包含多首曲目，明細另存於 ScoreExchangeItem。

| 欄位 | 說明 |
|------|------|
| other_band | 對方樂團名稱 |
| contact_person | 對方聯絡人姓名 |
| contact_phone | 對方聯絡人電話 |
| exchange_date | 交換日期 |
| notes | 備註 |

### 交換明細（ScoreExchangeItem）

每筆代表這次交換中的一首曲目，區分給出或收入。

| 欄位 | 說明 |
|------|------|
| exchange | 所屬交換事件（關聯 ScoreExchange）|
| direction | 給出（我們給對方）/ 收入（對方給我們）|
| score | 哪首譜（關聯 Score）|

### 公用財產（BandProperty）

所有可借用的公用財產統一在此管理，樂器是其中一種類型。

| 欄位 | 說明 |
|------|------|
| name | 財產名稱 |
| category | 類別：樂器 / 譜架 / 音響設備 / 制服 / 其他 |
| purchase_date | 購入日期 |
| purchase_cost | 購入費用（金額，財務紀錄另存於 FinanceRecord）|
| condition | 良好 / 需保養 / 送修中 |
| storage_location | 保管位置 |
| contact_person | 負責管理的幹部（關聯 User）|
| notes | 備註 |

### 公用財產借用紀錄（AssetBorrow）

統一管理所有公用財產的借用，不限樂器。

| 欄位 | 說明 |
|------|------|
| asset | 哪件財產（關聯 BandProperty）|
| borrower | 借用者（關聯 User）|
| borrowed_at | 借出日期 |
| due_date | 預計歸還日期 |
| returned_at | 實際歸還日期（空白 = 尚未歸還）|
| notes | 備註 |

### 樂器保養紀錄（InstrumentMaintenance）

樂器專屬，記錄保養與維修歷程。（其他財產若有保養需求可用 notes 欄位記錄）

| 欄位 | 說明 |
|------|------|
| asset | 哪件樂器（關聯 BandProperty，限樂器類別）|
| date | 保養日期 |
| description | 保養內容 |
| cost | 費用（關聯 FinanceRecord）|
| performed_by | 負責人（關聯 User）|

### 會費繳納紀錄（MembershipFee）

逐筆追蹤每位團員每期的繳費狀況，供 LINE Bot 判斷催繳對象。

| 欄位 | 說明 |
|------|------|
| member | 哪位團員（關聯 User）|
| period | 繳費期別（如：2026 上半年）|
| amount | 金額 |
| paid_at | 繳費日期（空白 = 尚未繳費）|
| collected_by | 收款幹部（關聯 User）|

### 校友報到申請（Registration）

新校友填寫申請表，幹部審核後建立正式 User 帳號。

| 欄位 | 說明 |
|------|------|
| name | 姓名 |
| instrument | 樂器（關聯 InstrumentType）|
| grad_year | 畢業年份 |
| phone | 電話 |
| email | Email |
| status | 待審核 / 已核准 / 已拒絕 |
| reviewed_by | 審核幹部（關聯 User）|
| reviewed_at | 審核時間 |

### 請假申請（LeaveRequest）

團員事先提出請假，幹部審核，核准後出席紀錄自動標記為「請假」。

| 欄位 | 說明 |
|------|------|
| member | 申請者（關聯 User）|
| rehearsal | 哪場排練（關聯 Rehearsal）|
| reason | 請假原因 |
| status | 待審核 / 核准 / 拒絕 |
| created_at | 申請時間（自動填入）|
| reviewed_by | 審核幹部（關聯 User）|
| reviewed_at | 審核時間 |

### 客座團員（GuestMember）

演出時從別團借調的臨時成員，不需正式帳號，但需出現在分譜分配與演出出席中。

| 欄位 | 說明 |
|------|------|
| name | 姓名 |
| instrument | 樂器（關聯 InstrumentType）|
| section | 聲部（關聯 SectionType）|
| from_band | 來自哪個樂團 |
| event | 參與哪場演出（關聯 PerformanceEvent）|
| phone | 聯絡電話 |

### 公告（Announcement）

| 欄位 | 說明 |
|------|------|
| title | 標題 |
| content | 內容 |
| visibility | public / member_only / officer_only |
| event_date | 活動日期（選填）|
| created_by | 發布者（關聯 User）|
| published_at | 發布時間（草稿時為空）|

### 會議紀錄（MeetingRecord）

| 欄位 | 說明 |
|------|------|
| title | 會議名稱 |
| date | 會議日期 |
| attendees | 出席者（關聯多位 User）|
| audio_file | 原始錄音檔 |
| transcript | 完整逐字稿（Whisper 產生）|
| summary | AI 摘要與決議事項（Claude API 產生）|
| status | 草稿（待審）/ 已發布 |

---

## 四、頁面與權限結構

```
未登入（所有人）
├── 首頁
├── 關於百韻
├── 組織章程
├── 公開活動公告
├── 校友報到申請
└── 校友報到申請狀態查詢（用 Email 查）

登入後（一般團員）
├── 個人資料編輯
├── 演出活動列表 / 詳情
├── 排練詳情（含排練摘要）
├── 請假申請（針對特定排練）
├── 我的請假紀錄
├── 分譜查詢（我被分配到哪些譜）※ 規劃中
├── 公用樂器借用申請 ※ 規劃中
├── 樂譜瀏覽 / 搜尋 / 下載
└── 會員限定公告 ※ 規劃中

幹部專區
├── 財務管理（Model + Admin）※ 尚無前端頁面
├── 演出活動管理（建立、排練、演出曲目分配）
├── QR Code 簽到管理
├── 場地主檔管理（Model + Admin）※ 尚無前端頁面
├── 會員通訊錄（按樂器分組，電話幹部限定）
├── 校友報到審核
├── 請假審核
├── 樂譜庫存管理（Model + Admin，瀏覽有前端）
├── 公用財產管理（Model + Admin）※ 尚無前端頁面
├── 會議紀錄管理（上傳錄音、審核 AI 摘要）※ Phase 3
└── 幹部限定公告 ※ 規劃中
```

> **「※ 規劃中」** 表示 Model 已建立、路由尚未實作前端頁面；
> **「※ 尚無前端頁面」** 表示目前操作入口為 Django Admin。

---

## 五、系統流程說明

### 演出通知流程

```
幹部建立演出活動 + 排練時間表
        ↓
設定演出曲目（從樂譜庫選取）
        ↓
系統根據「樂器 + 分部」自動產生分譜分配名單
        ↓
LINE Bot 發通知給每位團員（含分部資訊）
        ↓
團員回覆確認出席 or 請假
        ↓
幹部查看出席總覽，處理異動補位
        ↓
每次排練：幹部顯示 QR Code → 團員掃碼簽到
        ↓
音樂會結束，活動標記為已結束
```

### QR 簽到流程

```
幹部在排練前產生當天專屬 QR Code
        ↓
貼在排練室門口或用手機螢幕顯示
        ↓
團員用手機鏡頭掃描（不需安裝 APP）
        ↓
自動開啟網頁，點「簽到」完成
        ↓
幹部後台即時看到出席狀況
```

### 請假申請流程

```
團員進入排練詳情頁 → 點「申請請假」
        ↓
leave_request_create（GET）：顯示申請表單
系統先查有無既有申請，有則在頁面提示
        ↓
團員填寫請假原因，送出 POST
（排練已結束 / 已有申請 / 原因為空 → 擋回並提示）
        ↓
建立 LeaveRequest（status=pending）
        ↓
幹部進入 leave_review_list：分「待審核」與「已審核」兩區
        ↓
幹部按「核准」
  → LeaveRequest.status = approved
  → 記錄 reviewed_by / reviewed_at
  → get_or_create RehearsalAttendance，設 status = leave
        ↓
幹部按「拒絕」
  → LeaveRequest.status = rejected
  → 記錄 reviewed_by / reviewed_at
  → 出席紀錄不異動
```

### 會議記錄 AI 流程

```
幹部上傳會議錄音檔（MP3 / M4A）
        ↓
OpenAI Whisper 語音轉逐字稿
        ↓
Claude API 產生摘要與重點決議
        ↓
幹部人工審核後發布
```

---

## 六、專案目錄結構

```
FJCWO-Web/
├── config/                 # Django 設定檔
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── accounts/           # 登入、會員、角色
│   ├── events/             # 演出活動、排練、出席、QR 簽到
│   ├── scores/             # 樂譜庫存、對外交換
│   ├── assets/             # 公用財產、借用、樂器保養
│   ├── finance/            # 財務管理
│   ├── notifications/      # LINE Bot 通知
│   ├── meetings/           # 會議紀錄、AI 摘要
│   ├── announcements/      # 公告
│   └── public/             # 公開頁面、場地主檔
├── templates/              # HTML 模板
│   ├── base.html
│   ├── accounts/
│   ├── events/
│   ├── public/
│   ├── registration/
│   └── scores/
├── static/
│   └── images/             # favicon、logo 等靜態圖檔
├── fixtures/               # 測試用初始資料（loaddata 用）
│   └── venues.json         # 場地 + 場地時段
├── _notes/                 # 開發文件（不進 production）
│   ├── Architecture.md
│   ├── DESIGN.md
│   ├── SETUP.md
│   └── TESTING.md
├── .env                    # 環境變數（不進 git）
├── .env.example            # 環境變數範本
├── requirements.txt
└── manage.py
```

---

## 七、開發階段規劃

### Phase 1 — 基礎建設
- [x] 建立 Django 專案 + PostgreSQL 連線
- [x] 建立自訂 User Model（含角色、樂器、分部欄位）
- [x] 登入 / 登出 / 權限控制機制
- [x] 把現有 Hugo 公開頁面搬進 Django templates

### Phase 2 — 核心功能
- [x] 場地主檔管理（Model + Admin + VenueTimeSlot 多時段）
- [x] 演出活動 + 排練管理（Model + Admin + views + templates）
- [x] QR Code 簽到系統（Model + Admin + views + templates）
- [x] 曲目分配（Model + Admin，LINE Bot 通知待做）
- [x] 財務管理（Model + Admin）
- [x] 樂譜庫存管理（Model + Admin + views + templates）
- [x] 公用財產管理 + 借用系統（Model + Admin）
- [x] 會員通訊錄（按樂器分組，電話/Email 幹部限定）
- [x] 請假申請頁面（申請、我的紀錄、幹部審核）

### Phase 3 — 進階功能
- [ ] 會議紀錄 + Whisper 語音辨識
- [ ] Claude API 摘要生成
- [ ] 演出介紹手冊自動生成
- [ ] 手機版 UI 調整

### Phase 4 — SaaS 擴充（未來）
- [ ] 導入 django-tenants
- [ ] 子網域隔離各樂團資料
- [ ] 訂閱 / 付款流程

---

## 八、伺服器規劃

| 項目 | 說明 |
|------|------|
| 硬體 | 汰換電腦 + 擴充 HDD |
| 網路 | 中華電信固定 IP |
| OS | Ubuntu Server 24.04 LTS |
| Web Server | Nginx + Gunicorn |
| 隔離 | Docker 將 NAS 與 Web Server 分開 |
| SSL | Let's Encrypt（免費）|

**必做安全設定：**
- 防火牆只開 Port 80、443、22
- SSH 改用金鑰登入，關閉密碼登入
- 定期備份資料

