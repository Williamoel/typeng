# TypEng 网站部署指南

本指南面向当前的账号网站版。推荐使用 Render 的单实例 Docker Web Service 与持久磁盘：配置简单、GitHub 推送后可自动部署，并自带 HTTPS。

相关官方文档：[Web Service](https://render.com/docs/web-services) · [Docker](https://render.com/docs/docker) · [持久磁盘](https://render.com/docs/disks) · [自定义域名](https://render.com/docs/custom-domains)

## 为什么不能使用临时文件系统

TypEng 当前用 SQLite 保存账号、词库、学习进度和 Cloze 反馈。Render 默认文件系统会在重新部署或重启时被替换，因此必须挂载持久磁盘。Render 官方目前只允许付费 Web Service 使用持久磁盘；免费实例可以演示界面，但不能可靠保存用户数据。

当前架构只运行一个 Gunicorn Worker。持久磁盘只能连接一个服务实例，SQLite 也不适合多实例同时写入。对于早期学生项目和少量访客，这是合理的折中。

## 发布前准备

1. 确认完整测试通过：

   ```bash
   PYTHONPATH=. .venv/bin/pytest -q
   ```

2. 推送主分支并创建版本标签。Release 工作流会生成桌面包和 `typeng-lexicon.sqlite3`。
3. 确认 GitHub Release 页面已经出现紧凑词典资产，再进行第一次正式部署。

## 使用 Render Blueprint 部署

1. 注册或登录 Render，并连接 GitHub。
2. 选择 **New → Blueprint**。
3. 选择 `PeiyanTang/typeng` 仓库。Render 会读取根目录中的 `render.yaml`。
4. 确认配置包含：
   - Docker Runtime；
   - Starter 或其他付费 Web Service；
   - 1 GB 持久磁盘；
   - 挂载目录 `/var/lib/typeng`；
   - 健康检查 `/health`。
5. Render 会要求填写 `TYPENG_ALLOWED_HOSTS`。填写最终域名，例如：

   ```text
   typeng-web-xxxx.onrender.com
   ```

   只填写主机名，不要包含 `https://` 或路径。
6. 创建 Blueprint 并等待构建。`TYPENG_SECRET_KEY` 会由 Render 自动生成，不要在后续部署中更换。
7. 打开 Render 分配的 HTTPS 地址，然后访问 `/register` 创建第一个账号。

容器会从 GitHub 最新 Release 下载 `typeng-lexicon.sqlite3` 到持久磁盘。如果第一次启动早于 Release 资产生成，等待 Release 完成后在 Render 中选择 **Manual Deploy → Deploy latest commit**。

## 关键环境变量

| 名称 | 正式环境值 | 作用 |
| --- | --- | --- |
| `TYPENG_WEB_MODE` | `1` | 开启公开账号网站模式 |
| `TYPENG_SECRET_KEY` | Render 自动生成 | 签名登录 Session 和设备标识 |
| `TYPENG_ALLOWED_HOSTS` | 实际域名 | 拒绝伪造 Host 请求 |
| `TYPENG_COOKIE_SECURE` | `1` | 只通过 HTTPS 发送登录 Cookie |
| `TYPENG_HOME` | `/var/lib/typeng` | 持久数据根目录 |
| `TYPENG_LEXICON_PATH` | `/var/lib/typeng/lexicon/typeng-lexicon.sqlite3` | 紧凑词典位置 |
| `TYPENG_LEXICON_URL` | GitHub Release 下载地址 | 首次启动时下载词典 |

## 数据位置与备份

- `/var/lib/typeng/data/typeng.db`：账号、密码哈希、词库、进度和反馈，是必须备份的数据。
- `/var/lib/typeng/lexicon/typeng-lexicon.sqlite3`：可从 Release 重新下载的词典缓存。
- `/var/lib/typeng/data/secret_key`：本地模式使用；网站模式使用环境变量中的 Secret Key。

Render 持久磁盘提供自动快照，但仍建议定期下载 `typeng.db` 做离线备份。备份 SQLite 时先停止服务，或使用 SQLite 的在线备份命令，避免直接复制正在写入的 WAL 数据库。

## 绑定自己的域名

在 Render 服务的 **Settings → Custom Domains** 中添加域名，然后按照页面提供的 DNS 记录到域名服务商配置。验证完成后 Render 会自动签发和续期 TLS 证书，并将 HTTP 重定向到 HTTPS。

绑定后把新域名加入 `TYPENG_ALLOWED_HOSTS`。多个域名用英文逗号分隔，例如：

```text
typeng.example.com,typeng-web-xxxx.onrender.com
```

## 更新网站

`render.yaml` 已开启自动部署。主分支出现新提交后，Render 会重新构建容器；数据库和词典位于持久磁盘，不随镜像替换。

带持久磁盘的服务更新时会出现短暂重启窗口。升级前先确认测试和数据库迁移均已通过。

## 当前账号边界

- 用户名支持中文、英文、数字和下划线，规范化后全站唯一。
- 密码至少 6 位，以密码哈希保存，管理员无法读取原密码。
- 每个设备每天最多尝试注册 100 次；Cookie 缺失时以 IP 兜底。
- 没有邮箱验证、找回密码、管理员面板或主动封禁功能。
- 所有学习数据按账号所属词库隔离；词典缓存为所有账号共享的只读数据。

如果以后访问量明显增加，下一步应迁移 PostgreSQL、增加密码重置和后台反馈审核，而不是继续横向扩展 SQLite 实例。
