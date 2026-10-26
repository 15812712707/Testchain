# 验证记录

验证日期：2026-10-26。

## 已在本机执行

- Python 3.14.6 / Django 5.2.18 / SQLite。
- 数据库从空库执行全部迁移成功，迁移差异检查通过。
- `manage.py check` 通过。
- 使用独立部署环境变量执行 `manage.py check --deploy`，无警告。
- 静态资源收集和压缩成功，依赖一致性检查通过。
- 42 项自动测试通过，包含真实 HTTP 登录、创建项目、版本、用例、执行、生成报告、存证、下载及文件验证。
- 并发双请求形成连续区块；同报告并发存证保持幂等。
- 数据备份后恢复，可重新通过文件字节与区块链完整性验证。
- Gunicorn 双工作进程启动成功；实际 `/health/` 返回 200，登录页返回 200。
- MySQL 8.4.13 已通过 Homebrew 安装并作为本机服务运行；仅监听 127.0.0.1，root 使用独立随机密码。
- 已建立 testchain 数据库和独立应用账号，应用已切换至 MySQL，原 SQLite 数据先备份再导入。
- 同一套 42 项自动测试在 MySQL 8.4.13 上全部通过，包括真实 HTTP、并发存证和备份恢复。

## 需要外部环境的检查

- MySQL 的原生本机安装已验证。Docker Compose 容器环境尚未在本机执行。
- GitHub Actions 需代码上传至 GitHub 后运行；没有将本地测试结果表述为已通过远程 CI。
- 浏览器页面视觉检查未完成：内置浏览器的自动权限审核超时。页面模板及表单已通过服务端渲染和 HTTP 流程测试。
- 域名、HTTPS 证书和公网服务器由实际部署环境提供。

## 复现

```sh
python manage.py collectstatic --noinput
python manage.py test core.tests -v 2
python manage.py makemigrations --check --dry-run
python manage.py check
```

启用生产环境变量后执行 `python manage.py check --deploy`。对于 MySQL，设置连接参数后执行相同测试命令，或等待仓库中的 CI 作业执行。
