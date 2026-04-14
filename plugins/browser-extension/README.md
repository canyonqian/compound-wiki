# 🧠 Compound Wiki — Smart Browser Extension

> **智能浏览器扩展：自动识别有价值的内容，自动保存到你的 Wiki，全程无感。**

## 它能做什么？

```
旧方式（手动）:
  打开文章 → 读 → 觉得不错 → 点书签按钮 → 保存

新方式（全自动）:
  打开文章 → 正常阅读 → 系统后台静默分析
  ↓ （你什么都不用做）
  读完了切走 → 系统自动判断值得保存 → 自动抓取 → 自动存入 Wiki
  ↓
  右下角弹出："🧠 已存入 Wiki"
```

**核心能力：**

| 能力 | 说明 |
|------|------|
| 🧠 **智能内容检测** | 6维评分引擎，自动判断文章是否值得保存 |
| 👀 **阅读行为追踪** | 追踪滚动深度、停留时长、高亮、复制等行为 |
| 📄 **正文智能提取** | Readability 算法提取正文，去广告/导航/footer |
| 🏷️ **自动分类标签** | 根据内容类型+来源自动生成标签 |
| 🔌 **无缝对接后端** | 捕获后直接触发 INGEST 全流程，Wiki 页面自动生成 |
| 🤫 **静默通知** | 不打断浏览，右下角气泡提示即可 |

## 快速安装

### 方式一：开发者模式加载（推荐）

1. **确保 Compound Wiki 后端正在运行**
   ```bash
   python auto/agent.py start
   ```

2. **打开 Chrome/Edge 扩展管理页面**
   - Chrome: `chrome://extensions/`
   - Edge: `edge://extensions/`

3. **开启"开发者模式"**（右上角开关）

4. **点击"加载已解压的扩展程序"**
   - 选择 `plugins/browser-extension/` 目录

5. **图标出现在工具栏** — 完成！

### 方式二：作为 Bookmarklet 使用（无需安装）

1. 启动 Compound Wiki 后端
2. 浏览器打开 `http://localhost:9877/bookmarklet.js`
3. 把页面上的 **📎 Save to Wiki** 按钮**拖到书签栏**
4. 在任意网页点击该书签即可保存

## 工作原理

### 6 维评分引擎

系统从 6 个维度评估一个网页是否值得自动保存：

```
维度              权重    说明
───────────────────────────────
📊 内容密度        25%     正文占页面的比例（过滤导航/广告页）
📏 阅读深度        20%     滚动比例（扫一眼 vs 读完）
⏱️ 停留时长        20%     有效阅读时间
🔒 来源可信度      15%     域名白名单/黑名单/已知质量站点
👆 交互信号        10%     高亮文字、复制操作、返回重读
⭐ 内容质量        10%     字数/结构/元数据完整性
```

### 决策阈值

| 分数 | 行为 |
|------|------|
| **≥ 80** | ⚡ **立即自动捕获**（高质量 + 深度阅读） |
| **≥ 60** | 🔍 观察模式（离开页面时再判断） |
| **< 40** | ❌ 忽略（首页/导航/短内容） |

### 域名信任系统

内置了 25+ 个域名的信任评分：

**加分域名（高价值）：**
- `arxiv.org` (+30) · `distill.pub` (+35) · `paperswithcode.com` (+25)
- `github.com` (+20) · `dev.to` (+15) · `lesswrong.com` (+25)
- `zhuanlan.zhihu.com` (+15) · `sspai.com` (+12)

**减分域名（低价值）：**
- `google.com` (-50) · `facebook.com` (-45)
- `amazon.com` (-40) · `twitter.com` (-30)

## 使用方法

### 完全自动模式（默认）

```
1. 安装扩展
2. 正常上网浏览
3. 遇到好文章就正常读
4. 读完切走 → 系统自动保存 ✅
```

### 手动强制保存

两种方式：

1. **点击扩展图标** → 弹出面板 → 点击 **💾 Force Save Now**
2. **右键菜单** → "🧠 Save to Compound Wiki"

### 查看 Popup 面板

点击浏览器工具栏的 Compound Wiki 图标：

```
┌──────────────────────────────┐
│  🧠 Compound Wiki    [SMART] │
│                              │
│  ● Connected          5 today│
│                              │
│  📊 Current Page             │
│  Andrej Karpathy's LLM Wiki  │
│                              │
│   ╭────╮                     │
│   │ 86 │  ← 圆环分数显示     │
│   ╰────╯                     │
│  ⚡ Will Auto-Capture         │
│                              │
│  📊 ████████░░ Density 82    │
│  📏 ██████████ Depth   88    │
│  ⏱️ ████████░░ Dwell   75    │
│                              │
│   92%    3m15s    2           │
│ Scroll  Reading Highlights   │
│                              │
│ [💾 Force Save Now] [⚙️]    │
│  🤖 Auto-Capture  [ON]       │
│                              │
│  🕐 Recently Saved            │
│  • LLM-Wiki article (85) 2m  │
│  • RAG vs Wiki (72)   15m    │
└──────────────────────────────┘
```

## 配置选项

在 Popup 中可以调整：

| 选项 | 默认值 | 说明 |
|------|--------|------|
| Auto-Capture | ON | 总开关，关闭后只手动保存 |
| 最小分数阈值 | 60 | 低于此分不自动捕获 |
| 最小停留时间 | 15秒 | 页面停留不足此时间不捕获 |
| 通知显示 | ON | 是否显示气泡通知 |

## 数据流

```
Browser (Content Script)
  │
  ├─ 分析页面内容（Readability算法提取正文）
  ├─ 追踪阅读行为（滚动/停留/高亮/复制）
  └─ 计算6维评分
       │
       ▼  score ≥ threshold
  Browser (Background Service Worker)
  │
  ├─ 元数据增强（作者/日期/分类）
  └─ POST /auto-clip
       │
       ▼
  Compound Wiki Backend (:9877)
  │
  ├─ 接收并验证数据
  ├─ 存入 raw/ 目录（带完整 frontmatter）
  ├─ 加入 INGEST 队列
  ├─ 调用 LLM 处理
  └─ 生成/更新 Wiki 页面
       │
       ▼
  wiki/concept/ 或 wiki/entity/
  （双链网络自动增长 🎉）
```

## 文件结构

```
browser-extension/
├── manifest.json          ← 扩展清单（Manifest V3）
├── background.js          ← 后台服务 worker
├── content.js             ← 页面注入脚本（分析+追踪+评分+自动捕获）
├── lib/
│   ├── readability.js     ← 正文提取算法
│   └── scorer.js          ← 6维评分引擎（可独立使用）
├── popup/
│   ├── popup.html         ← 弹窗 UI
│   ├── popup.css          ← 弹窗样式
│   └── popup.js           ← 弹窗逻辑
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
├── ARCHITECTURE.md        ← 详细架构文档
└── README.md              ← 本文件
```

## 兼容性

| 浏览器 | 支持状态 |
|--------|---------|
| Google Chrome | ✅ 完整支持 |
| Microsoft Edge | ✅ 完整支持（Chromium 内核） |
| Brave | ✅ 完整支持 |
| Arc | ✅ 支持 |
| Firefox | ⚠️ 部分支持（Manifest V3 适配中） |

## 与其他工具对比

| 功能 | Pocket | Notion Web Clipper | **Compound Wiki Extension** |
|------|--------|-------------------|----------------------------|
| 手动保存 | ✅ | ✅ | ✅ |
| **自动识别** | ❌ | ❌ | **✅ 核心功能** |
| **阅读行为感知** | ❌ | ❌ | **✅ 6维追踪** |
| **智能评分** | ❌ | ❌ | **✅ 多维加权** |
| **正文提取** | 基本 | 基本 | **✅ Readability算法** |
| **去噪处理** | 部分 | 部分 | **✅ 广告/导航/footer** |
| **自动分类** | 标签手动 | 无 | **✅ AI自动** |
| **后续处理** | 仅存储 | 仅存储 | **✅ LLM整理+Wiki生成** |
| **知识复利** | ❌ | ❌ | **✅ 双链网络增长** |
| 开源免费 | ✅ | ✅ | **✅ MIT** |

## 故障排除

### "Cannot reach Wiki server"
- 确保 `python auto/agent.py start` 正在运行
- 检查端口 9877 是否被占用
- 扩展会自动将内容排队，恢复连接后重试

### 没有自动捕获
- 检查 Popup 中的分数是否达到阈值
- 某些页面（chrome://, about:, 扩展商店等）无法注入脚本
- 确认 Auto-Capture 开关为 ON

### 捕获了不需要的内容
- 在 Popup 中调高最小分数阈值（建议 70+）
- 或者关闭自动捕获，改用手动模式

## License

MIT © Compound Wiki Contributors
