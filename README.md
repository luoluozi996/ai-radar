# AI 内容日报 · AI Radar

每日自动化 AI 内容聚合与简报生成工具。自动抓取多源内容，调用 AI 生成摘要、雷达评分与双语简报，帮助 AI 从业者高效获取当日关键信息。

## 它能做什么

- **多源内容聚合**：支持 RSS、X(Twitter)、邮件简报等多种输入源，可扩展配置
- **AI 摘要生成**：调用大语言模型自动生成中文摘要与关键要点，并翻译为英文版本
- **雷达评分系统**：从 Impact、Novelty、Relevance 三个维度对内容进行加权评分，排序筛选高价值信息
- **多渠道分发**：支持输出为 Markdown、HTML 邮件，可扩展适配其他分发渠道

## 快速开始

### 环境要求
- Python 3.9+
- 任意大语言模型 API（OpenAI / DeepSeek / Gemini 均可）
  
## 安装与运行

1. 克隆仓库

```bash
git clone https://github.com/你的用户名/ai-radar.git
cd ai-radar

pip install -r requirements.txt

cp .env.example .env
# 编辑 .env 文件，填入你的 API Key

python main.py
```

### 项目结构

```text
ai-radar/
├── src/
│   ├── collector/       # 数据采集模块
│   ├── processor/       # AI 处理与摘要生成
│   └── publisher/       # 内容输出与分发
├── config/              # 配置文件（数据源、API、评分权重）
├── output/              # 生成内容输出目录
├── main.py              # 程序入口
├── requirements.txt     # 项目依赖
└── README.md
```

## 当前使用的模型

可根据配置灵活替换，目前已测试兼容：

- DeepSeek Chat
- Gemini 3 Flash
- OpenAI GPT-5

## 后续计划

- 支持更多数据源（YouTube 频道、ArXiv 论文）
- 增加多语言版本（日语、西班牙语）
- 部署为在线服务（Web 界面/API）
- 增加用户自定义评分设置

## 致谢

本项目受个人学习与求职转型驱动，旨在验证 AI 工作流从数据采集到内容分发的端到端落地能力。
