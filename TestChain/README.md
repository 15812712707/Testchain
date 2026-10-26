# TestChain

软件测试管理与报告存证系统。支持多人协作、项目权限、版本管理、测试用例、执行历史、缺陷跟踪、报告上传/生成/下载、SHA-256 核验、PoW 哈希链和操作审计。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.12+、Django 5.2 |
| 前端 | Django Templates、HTML5、CSS3、原生 JavaScript，响应式页面 |
| 数据库 | MySQL 8.4；本地也支持 SQLite |
| 安全 | Django 密码哈希、Session、CSRF、项目级权限、登录失败限制 |
| 存证 | SHA-256、规范化 JSON、PoW、事务锁、数据库持久化 |
| 部署 | Gunicorn、WhiteNoise、Docker Compose |
| 测试 | Django TestCase、GitHub Actions，SQLite/MySQL 两套任务 |

## 本地运行

安装 Python 3.12 或更新版本后，在项目目录运行：

```sh
sh start.sh
```

macOS 也可双击 `启动TestChain.command`。打开 <http://127.0.0.1:8000>，注册自己的账号。数据库首次启动自动创建，后续启动保留已有数据。若端口占用，运行 `PORT=8001 sh start.sh`。

首次运行需要联网安装依赖。启动脚本用于本地开发；长期运行服务使用下文的 Gunicorn 或 Docker 配置。

运行流程：注册 → 创建项目 → 新增版本 → 添加测试用例 → 执行用例 → 登记并处理缺陷 → 生成或上传报告 → 提交存证 → 上传待验证文件核验。

成员需先注册，负责人在“成员管理”中按用户名添加：

- 项目管理员：管理成员、项目信息及全部测试流程。
- 测试人员：管理版本、用例、执行、缺陷和报告。
- 只读成员：查看、下载、验证报告和检查链。

每个账号只可访问自己创建或受邀加入的项目。超级用户的 `/admin/` 管理后台独立于项目权限，用于系统维护。

## 创建系统管理员

```sh
.venv/bin/python manage.py createsuperuser
```

管理员可管理账号；忘记密码可在服务器运行 `.venv/bin/python manage.py changepassword 用户名`。系统不依赖邮件服务。

## MySQL / Docker 运行

1. 复制 `.env.example` 为 `.env`。
2. 分别生成并设置 `SECRET_KEY`、`DB_PASSWORD`、`MYSQL_ROOT_PASSWORD`，不要使用相同密码。可执行 `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'` 生成随机值。
3. 运行 `docker compose up --build -d`。
4. 打开 <http://127.0.0.1:8000> 并注册账号。
5. 如需系统管理员，执行 `docker compose exec web python manage.py createsuperuser`。

Compose 将数据库放入持久化数据卷，只把网站绑定到本机端口。通过 `docker compose logs -f web` 查看日志，`docker compose down` 停止服务。**`docker compose down -v` 会删除数据库数据。**

不使用 Docker 时，在 `.env` 中设置 `DB_ENGINE=mysql` 及 MySQL 连接参数，然后执行 `python manage.py migrate`。MySQL 用户需要拥有此数据库的建表和读写权限；本机运行测试时另需创建 `test_testchain` 数据库的权限。

## 服务器部署

部署时配置 `.env`：`DEBUG=false`、独立随机 `SECRET_KEY`、实际域名 `ALLOWED_HOSTS`、HTTPS 来源 `CSRF_TRUSTED_ORIGINS`、`COOKIE_SECURE=true`、`SECURE_SSL_REDIRECT=true`。按需要设置 `ALLOW_REGISTRATION=false` 关闭公开注册，再由管理员创建用户。

```sh
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 2 --threads 2 --timeout 120
```

通过 HTTPS 反向代理接入 Gunicorn。提供了 `deploy/nginx.conf.example`。使用该示例时设置 `TRUST_PROXY=true`，只允许可信代理连接应用端口。Docker 环境将同名变量加入 `web.environment`，HTTPS 由代理终结。

本地 HTTP 的 Compose 配置显式使用 `COOKIE_SECURE=false`，线上 HTTPS 必须改为 `true`。报告以数据库二进制字段保存，下载需要登录和项目权限，不公开上传文件目录。单份文件上限 10 MB；代理同步限制请求体大小。

## 测试

```sh
python manage.py collectstatic --noinput
python manage.py test core.tests -v 2
python manage.py makemigrations --check --dry-run
```

覆盖权限隔离、CSRF、账号登录、版本隔离、用例快照、缺陷流程、二进制上传下载、报告生成、存证幂等、篡改检测、并发存证、备份恢复和页面渲染。GitHub Actions 在推送和 PR 时执行 SQLite 与 MySQL 测试。

## 数据与备份

业务字段、文件、区块和链头均持久化到配置的数据库。报告不可通过业务界面覆盖，修改后的报告需新增上传。用例执行记录保留快照，编辑用例不改变历史执行内容。项目和用例通过归档管理，报告和链上记录无删除入口。

停写后执行 `python manage.py backup`，备份生成在 `backups/`。在一个全新、已执行迁移的空实例中运行 `python manage.py loaddata backups/备份文件.json` 恢复。备份包含账号密码哈希与原始报告，勿上传 GitHub。

SQLite 可在停止服务后同时备份 `db.sqlite3`。MySQL 大型部署应使用数据库原生备份及定期恢复演练。

## 存证边界

系统实现的是单服务私有哈希链：多个项目共享顺序链，各项目只展示自己的区块；工作量证明难度固定为三个前导十六进制零。存证事务锁定链头，重复提交同一报告返回同一区块。文件验证优先比较链上指纹，并检查整条链。

这套机制能检测文件和记录是否与保存的版本一致；不能证明报告内容的业务真实性，也不能阻止拥有数据库控制权的人员重算并替换整条链。它不包含公链、多节点共识、代币或法律时间戳。链头备份应保存在独立受控位置，按实际信任模型选择外部锚定服务。

## GitHub

将**本目录**作为仓库根目录上传，保留 `.github/workflows/ci.yml`。`.gitignore` 已排除密码、运行数据库、虚拟环境和备份；`.env.example`、迁移、源码及依赖清单应上传。不要把旧项目目录或自己的数据一起上传。

更多说明见 [数据库设计](docs/database.md)、[接口说明](docs/routes.md)、[架构说明](docs/architecture.md)、[验证记录](docs/verification.md)。
