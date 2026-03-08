<div align="center">

<img src="logo.png" width="120" height="120" alt="LoosePlan Logo">

# ✨ 松弛排程 · LoosePlan

> *让日程管理，像呼吸一样自然*

[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-Qt6-green?style=flat-square&logo=qt)](https://wiki.qt.io/Qt_6)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010+-0078D6?style=flat-square&logo=windows)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-orange?style=flat-square)](LICENSE)

</div>

---

## 🌟 项目简介

**松弛排程（LoosePlan）** 是一款由 AI 驱动的智能日程管理助手，专为追求高效与松弛感的现代人打造。

不同于传统的待办清单应用，LoosePlan 深度融合 **Kimi AI（Moonshot）** 能力，通过 21 道专业画像问卷，为你构建独属的「记忆图谱」，让 AI 真正理解你的工作节奏、精力曲线与决策偏好。

> 💡 **核心理念**："松弛感不是躺平，而是对节奏的精准掌控。"

---

## 🎯 核心特性

| 特性 | 描述 |
|------|------|
| 🤖 **AI 深度对话** | 基于 Kimi 的智能聊天，支持自然语言创建日程与待办 |
| 🧠 **记忆图谱** | 19 维用户画像持续学习，越用越懂你 |
| 📅 **智能日程** | 月历视图 + 待办统计 + 历史变更追踪 |
| 🔔 **灵动提醒** | 系统通知 + 飞书推送双通道，重要事项不错过 |
| 📊 **每周回顾** | 自动生成周度复盘，让成长可视化 |
| 💎 **极简美学** | macOS 白色极简风格，无边框 + 玻璃拟态设计 |
| 🔒 **本地优先** | 全部数据本地 JSON 存储，隐私零担忧 |

---

## 🚀 快速开始

### 方式一：源码运行（推荐开发者）

```bash
# 1️⃣ 克隆仓库
git clone https://github.com/yourusername/LoosePlan.git
cd LoosePlan

# 2️⃣ 安装依赖
pip install -r requirements.txt

# 3️⃣ 启动应用
python -m app.main
```

### 方式二：一键安装（推荐普通用户）

1. 📥 前往 [Releases](https://github.com/qingshanyu9/LoosePlan/releases) 下载 `LoosePlan-Setup.exe`
2. 🖱️ 双击安装包，按向导完成安装
3. ✨ 桌面快捷方式启动，即刻体验

> 💾 安装包内含完整运行环境，无需额外配置 Python

---

## 🖥️ 系统要求

| 项目 | 要求 |
|------|------|
| **操作系统** | Windows 10 |
| **运行时** | Python 3.10+（源码运行时需要） |
| **内存** | 4GB RAM 以上 |
| **存储** | 100MB 可用空间 |
| **网络** | 需要连接 Kimi API（国内可用） |

---

## ⌨️ 快捷键指南

| 快捷键 | 功能 |
|--------|------|
| `Alt + Shift + L` | 显示主窗口 |
| `Alt + Shift + C` | 打开聊天页面 |
| `Alt + Shift + S` | 打开日程页面 |

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    展示层 (QML)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 聊天页面  │ │ 日程页面  │ │ 记忆图谱  │ │ 每周回顾  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
├─────────────────────────────────────────────────────────┤
│                    逻辑层 (Python)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ Kimi AI  │ │ 飞书集成  │ │ 日程引擎  │ │ 记忆图谱  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
├─────────────────────────────────────────────────────────┤
│                    数据层 (本地 JSON)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 配置文件  │ │ 聊天日志  │ │ 日程数据  │ │ 用户画像  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 技术栈

- **GUI 框架**: [PySide6](https://doc.qt.io/qtforpython/) (Qt6 + QML)
- **AI 引擎**: [Kimi API](https://platform.moonshot.cn/) (Moonshot)
- **企业集成**: [飞书开放平台](https://open.feishu.cn/)
- **数据存储**: 本地 JSON/JSONL（零依赖）

---

## 📂 项目结构

```
LoosePlan/
├── app/                    # 应用主代码
│   ├── main.py            # 程序入口
│   ├── core/              # 核心模块（配置、路径、时钟）
│   ├── services/          # 业务服务（AI、飞书、日程）
│   └── ...
├── qml/                   # QML 界面文件
│   ├── components/        # 可复用组件
│   └── pages/             # 页面定义
├── data/                  # 本地数据目录
│   ├── config.json        # 应用配置
│   ├── profile.json       # 用户画像
│   ├── schedule/          # 日程月文件
│   └── chat/              # 聊天日志
├── requirements.txt       # Python 依赖
└── setup.iss              # 安装包配置
```

---

## 🛣️ 开发计划

- [x] 初始化向导与画像系统
- [x] 聊天与日程核心功能
- [x] 飞书端同步
- [x] 每周回顾与智能提醒
- [ ] 自动订阅
- [ ] 推荐权重
- [ ] 多语言支持
- [ ] 主题切换（暗黑模式）
- [ ] 数据可视化仪表盘

---

## 🤝 贡献指南

欢迎 Issue 和 PR！请确保：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📄 许可证

本项目基于 [MIT](LICENSE) 许可证开源。

---

<div align="center">

**Made with ❤️ by LoosePlan Team**

*让每一天，都有条不紊地松弛着。*

</div>






