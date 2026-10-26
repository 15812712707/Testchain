# 路由与接口

网站采用服务端渲染，页面表单 POST 需要 Session Cookie 和 CSRF token。未登录访问业务页面跳转登录；无项目访问权返回 404；只读成员调用写操作返回 403。写操作不接受 GET。

| 路径 | 方法 | 用途 |
| --- | --- | --- |
| `/health/` | GET | 数据库健康检查 JSON |
| `/register/` | GET/POST | 注册，支持通过环境变量关闭 |
| `/login/` | GET/POST | 登录，连续 5 次失败后限制 15 分钟 |
| `/logout/` | POST | 退出 |
| `/account/password/` | GET/POST | 修改密码 |
| `/` | GET | 当前用户可访问的项目，支持 q/page |
| `/projects/new/` | GET/POST | 创建项目 |
| `/projects/{p}/` | GET | 概览，可选 version 参数 |
| `/projects/{p}/edit/` | GET/POST | 修改项目，管理员 |
| `/projects/{p}/archive/` | POST | 归档或恢复，管理员 |
| `/projects/{p}/versions/new/` | GET/POST | 新建版本 |
| `/projects/{p}/cases/` | GET | 用例列表，q/priority/archived/page |
| `/projects/{p}/cases/new/` | GET/POST | 新增用例 |
| `/projects/{p}/cases/{id}/edit/` | GET/POST | 编辑用例 |
| `/projects/{p}/cases/{id}/archive/` | POST | 归档或恢复用例 |
| `/projects/{p}/cases/{id}/execute/` | GET/POST | 追加执行结果与用例快照 |
| `/projects/{p}/executions/` | GET | 执行历史，version_id/status/page |
| `/projects/{p}/defects/` | GET | 缺陷，status/page |
| `/projects/{p}/defects/new/` | GET/POST | 登记缺陷 |
| `/projects/{p}/defects/{id}/edit/` | GET/POST | 修改缺陷处理状态和负责人 |
| `/projects/{p}/members/` | GET/POST | 查询/添加/调整成员，管理员 |
| `/projects/{p}/members/{id}/remove/` | POST | 移除成员，管理员 |
| `/projects/{p}/reports/` | GET | 报告列表 |
| `/projects/{p}/reports/upload/` | GET/POST multipart | 上传文件，title/version/file |
| `/projects/{p}/reports/generate/` | GET/POST | 根据版本的最近执行结果生成 UTF-8 文本报告 |
| `/projects/{p}/reports/{id}/` | GET | 报告详情 |
| `/projects/{p}/reports/{id}/download/` | GET | 授权下载原始字节，attachment |
| `/projects/{p}/reports/{id}/anchor/` | POST | 存证，幂等 |
| `/projects/{p}/reports/{id}/verify/` | POST multipart | 验证 file，页面显示结果 |
| `/projects/{p}/chain/` | GET | 当前项目的区块 |
| `/projects/{p}/chain/check/` | POST | 整链验证 |
| `/projects/{p}/events/` | GET | 操作审计 |
| `/projects/{p}/export/` | GET | 执行历史 CSV，处理电子表格公式注入 |
| `/api/projects/{p}/` | GET | 当前项目统计、版本 JSON，使用相同项目权限 |
| `/admin/` | GET/POST | 系统账号管理与受控数据查询 |

系统以网页表单为主要交互方式。JSON 统计接口用于扩展集成，不提供无权限的公共业务 API。
