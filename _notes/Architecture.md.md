FJCWO-Web/ (專案根目錄)
├── content/                 # 🌐 公開網頁內容 (LoveIt 渲染區)
│   ├── _index.md            # 首頁：配置 params.home.profile (打字機文字)
│   ├── docs/                # 📜 服務選單
│   │   ├── rules.md         # 組織章程
│   │   ├── registration.md  # 立案進度
│   │   └── about.md         # 關於百韻
│   ├── archive/             # 📚 歷史典藏
│   │   ├── history.md       # 大事紀
│   │   └── scores.md        # 譜庫索引
│   └── alumni/              # 🤝 校友專區
│       ├── join-us.md       # 報到頁面
│       └── membership.md    # 會員說明
│
├── static/                  # 🖼️ 靜態資源 (直通 public/ 不編譯)
│   ├── images/              # 🎨 視覺識別與 Favicon 核心
│   │   ├── fjcwo_navbar.png # Navbar 專用長條 Logo (50px 高度優化)
│   │   ├── favicon.ico      # 瀏覽器通用小圖示
│   │   ├── apple-touch-icon.png # iOS 設備圖示
│   │   ├── favicon.svg      # Safari 向量標籤
│   │   ├── web-app-manifest-192x192.png # Android 圖示
│   │   └── site.webmanifest # PWA 設定檔
│   └── pdf/                 # 📄 樂譜、公文下載區
│
├── _notes/                  # 📝 專案開發記錄 (不公開、不編譯)
│   ├── Architecture.md      # 本架構圖 (已更新為 LoveIt + 多尺寸 Icon)
│   ├── Debug-Log.md         # 包含 Git Push 與 CSS 透明度除錯紀錄
│   └── Task-List.md         # 功能開發進度
│
├── .private/                # 🔒 極機敏資料 (由 .gitignore 排除)
│   ├── accounting/          # 財務細目
│   └── members/             # 會員通訊錄
│
├── .gitignore               # 🛡️ 安全防線 (已包含 public/, resources/, .private/)
├── hugo.toml                # ⚙️ 核心設定 (LoveIt 參數：header, footer, home)
└── themes/
    └── LoveIt/              # 🎨 主題引擎 (Git Submodule)