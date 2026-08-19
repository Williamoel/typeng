<div align="center">

# TypEng

**把单词打出来，在语境里真正学会它。**

一款极简、开源的英语词汇学习工具，核心是键盘主动拼写、按词性对齐的释义，以及语境填空训练。

[English](README.md) · [下载最新版本](https://github.com/Williamoel/typeng/releases/latest) · [数据来源](SOURCES.md)

![TypEng 网站工作区](docs/design/web-cloze-feedback-concept.png)

</div>

## v0.3 的变化

TypEng 现在既可以作为本地应用使用，也可以部署成公开网站。网站模式允许任何人注册：用户选择一个不重复的中文或英文用户名，以及不少于 6 位的密码。每个账号的词库、单元、学习进度、复习队列、错词和 Cloze 反馈都彼此隔离。

界面也已经重构为黑色纵向导航与两个留有间距的白色工作区。浏览词库、编辑、预览、学习、复习和查看词条都在同一套视觉结构中完成。

## 核心学习方式

- 不做选择题，而是亲手输入答案，训练真正的拼写回忆。
- 同一个单词按词性拆成独立词条，对齐中文释义、英文释义、音标、例句和用法标签。
- 支持普通拼写、仅 Cloze，以及“拼写后追加 Cloze”三种训练路径。
- Cloze 优先使用用户自己写的例句，否则从 Wiktionary 候选中筛选。
- 用户可以反馈例句太难、太简单、不合适或存在错误。
- 每个词库独立维护已掌握、待复习和错词状态。
- 自定义 Unit 的边界保持稳定，但一次学习可以跨 Unit 自动取足设定词数。

## 词库与数据处理

当前版本支持：

- 中考、高考、四级、六级、考研、雅思、托福和 GRE 预设词库；
- 使用 EFLLex 剔除确定过于基础的词汇；
- 使用 Wiktionary 核验词性，并提供英文释义、例句、用法标签和固定搭配；
- 使用 ECDICT 提供中文释义、音标、词频和考试标签；
- 更健壮的 TXT/CSV 导入、按课程划分 Unit、导出、英文搜索、批量编辑和跨词库去重。

体积很大的原始词典只在构建阶段使用。桌面发行包和网站使用紧凑 SQLite 词典缓存。各数据源和许可证边界见 [SOURCES.md](SOURCES.md)。

## 本地运行

推荐 Python 3.12：

```bash
git clone https://github.com/Williamoel/typeng.git
cd typeng
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

浏览器打开 `http://127.0.0.1:5000`。本地模式不显示登录页面，只接受当前电脑访问，数据保存在系统对应的 TypEng 数据目录中。

Windows、macOS 和 Linux 的免配置桌面包会附在每个 [GitHub Release](https://github.com/Williamoel/typeng/releases/latest) 中。

## 在本机体验账号网站模式

```bash
pip install -r requirements-web.txt
export TYPENG_WEB_MODE=1
export TYPENG_SECRET_KEY='替换成一段足够长且固定的随机字符串'
export TYPENG_ALLOWED_HOSTS='127.0.0.1'
export TYPENG_COOKIE_SECURE=0
gunicorn --bind 127.0.0.1:8000 --workers 1 --threads 8 wsgi:app
```

打开 `http://127.0.0.1:8000/register`。正式 HTTPS 部署时必须保持 `TYPENG_COOKIE_SECURE=1`。

### 账号规则

- 用户名为 1–32 个中文、英文字母、数字或下划线；
- Unicode 规范化后必须唯一，英文用户名不区分大小写；
- 密码为 6–256 位，只保存 Werkzeug 生成的密码哈希；
- 每个浏览器设备每天最多提交 100 次注册请求；设备 Cookie 尚未建立时，以来源 IP 兜底；
- 当前不要求邮箱验证，也暂时没有找回密码功能。

## 部署到云端

仓库已经提供 `render.yaml`、`Dockerfile` 和 Gunicorn 入口。最短流程是：

1. 将当前版本推送到 GitHub。
2. 登录 Render，选择 **New → Blueprint**，连接 TypEng 仓库。
3. 使用配置中带 1 GB 持久磁盘的付费 Web Service。
4. 把 `TYPENG_ALLOWED_HOSTS` 设置成 Render 分配的域名，不要填写 `https://`。
5. 部署完成后打开 Render 提供的 `onrender.com` 地址，进入 `/register` 注册。

账号和学习数据位于持久磁盘 `/var/lib/typeng`。不要用无持久磁盘的免费实例承载正式数据，否则重新部署或重启后数据可能消失。容器首次启动会下载 Release 中的紧凑词典缓存。

完整步骤、域名和备份说明见 [网站部署指南](docs/web-deployment.zh-CN.md)。

## 技术结构

```text
Flask 路由与 Session
        │
        ├── 账号认证与设备注册限流
        ├── 用户级词库所有权
        ├── 学习 / 复习服务
        └── Repository 数据访问层
                │
                ├── 可写 SQLite 学习数据库
                └── 紧凑型只读词典缓存
```

网站当前固定为一个 Gunicorn Worker 加多个线程，适合单实例 SQLite。以后如果需要多实例扩容，应迁移到 PostgreSQL 等共享数据库。

## 测试

```bash
PYTHONPATH=. pytest -q
```

测试覆盖导入解析、词典清洗、稳定 Unit、词库隔离、学习和复习流程、注册登录、用户数据边界、每日注册限流，以及紧凑词典构建。

## 项目定位

TypEng 是学生主导的作品集和研究型项目，而不是商业化英语平台。现阶段重点是词典数据质量、可解释的例句选择、真实学习反馈，以及清晰可维护的网站架构。

欢迎贡献。提交 Pull Request 前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

TypEng 程序代码使用 [MIT License](LICENSE)。词典数据保留各自许可证；重新分发前请阅读 [SOURCES.md](SOURCES.md)。
