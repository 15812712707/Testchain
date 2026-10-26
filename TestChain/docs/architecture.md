# 系统架构

```mermaid
flowchart LR
    U[浏览器 HTML/CSS/JS] --> W[Django 路由 / Session / CSRF]
    W --> P[项目权限与表单验证]
    P --> S[测试业务 / 报告 / 存证服务]
    S --> O[Django ORM 与数据库事务]
    O --> D[(MySQL / SQLite)]
    D --> B[账号 · 项目 · 用例 · 执行 · 缺陷]
    D --> R[原始报告字节 · SHA-256]
    D --> C[区块 · 链头 · 审计日志]
```

## 代码结构

- `config/`：环境配置、网站入口、WSGI。
- `core/models.py`：实体、主外键和数据库约束。
- `core/forms.py`：字段验证、项目归属边界与文件校验。
- `core/views.py`：权限验证、页面处理与统计接口。
- `core/services.py`：报告生成、哈希计算、事务存证与整链验证。
- `core/migrations/`：可复现的数据库变更。
- `core/management/commands/`：备份和链检查。
- `templates/`、`static/`：完整网页与响应式样式。
- `core/tests/`：功能、安全边界和一致性测试。

## 存证时序

```mermaid
sequenceDiagram
    participant U as 用户
    participant A as Django
    participant D as 数据库
    U->>A: 上传报告（项目 / 版本 / 文件）
    A->>A: 校验权限、大小、扩展名、版本归属
    A->>D: 原始字节 + SHA-256 + 审计
    U->>A: 提交存证
    A->>D: 事务锁定 ChainState
    A->>A: 检查整链及报告哈希，计算 PoW
    A->>D: 区块 + 链头更新 + 审计，一次提交
    U->>A: 上传待验证文件
    A->>A: 计算 SHA-256，验证链，比较存证哈希
    A-->>U: 一致 / 不一致 / 链完整性错误
```

用户实际执行测试后录入结果；系统负责管理过程和保存报告，不自动启动外部软件测试。文件一致性不等于测试结果真实性。

## 运行模式

本地 SQLite 模式与 MySQL 模式使用同一套业务代码。正式进程由 Gunicorn 承载，静态资源由 WhiteNoise 服务，HTTPS 在可信反向代理终结。数据库迁移在启动时执行，所有业务数据跨进程重启保留。
