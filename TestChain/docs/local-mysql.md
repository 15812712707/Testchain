# 本机 MySQL

安装日期：2026-10-26。MySQL 8.4.13，Apple Silicon Homebrew 安装。

| 项目 | 配置 |
| --- | --- |
| 地址 | 127.0.0.1 |
| 端口 | 3306 |
| 数据库 | testchain |
| 应用账号 | testchain |
| 应用连接配置 | 项目根目录 `.env` |
| 管理员连接配置 | 项目目录 `backups/mysql-admin.cnf` |
| MySQL 程序 | `/opt/homebrew/opt/mysql@8.4/bin/` |
| MySQL 数据 | `/opt/homebrew/var/mysql/` |
| 迁移前备份 | `backups/before-mysql.json`，原 `db.sqlite3` 同时保留 |

密码仅保存在本机配置文件中，权限为仅当前用户可读写；不写入说明书，不打包进源码。

MySQL 已设置为当前用户登录后自动启动。管理命令：

```sh
brew services start mysql@8.4
brew services stop mysql@8.4
brew services restart mysql@8.4
```

在项目目录打开管理员终端：

```sh
/opt/homebrew/opt/mysql@8.4/bin/mysql --defaults-extra-file=backups/mysql-admin.cnf
```

日常应用使用独立账号，只拥有 `testchain` 数据库权限。运行测试使用有权建立临时测试库的独立维护账号，不要给日常应用账号增加全局权限。

本文件描述此电脑的安装情况；其他电脑运行时仍需按 README 安装并配置自己的数据库。GitHub 和源码压缩包不包含当前机器的数据库或密码。
