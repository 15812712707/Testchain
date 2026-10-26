from django.conf import settings
from django.db import models
from django.db.models import Q


class Project(models.Model):
    name = models.CharField("项目名称", max_length=120)
    description = models.TextField("项目说明", blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_projects")
    archived = models.BooleanField("已归档", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        MANAGER = "manager", "项目管理员"
        TESTER = "tester", "测试人员"
        VIEWER = "viewer", "只读成员"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField("角色", max_length=12, choices=Role.choices, default=Role.TESTER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "user"], name="unique_project_member"),
            models.CheckConstraint(condition=Q(role__in=["manager", "tester", "viewer"]), name="valid_member_role"),
        ]


class Version(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="versions")
    name = models.CharField("版本名称", max_length=60)
    description = models.TextField("版本说明", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["project", "name"], name="unique_project_version")]

    def __str__(self):
        return self.name


class TestCase(models.Model):
    class Priority(models.TextChoices):
        HIGH = "high", "高"
        NORMAL = "normal", "中"
        LOW = "low", "低"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="cases")
    title = models.CharField("用例标题", max_length=200)
    steps = models.TextField("操作步骤")
    expected = models.TextField("预期结果")
    priority = models.CharField("优先级", max_length=8, choices=Priority.choices, default=Priority.NORMAL)
    archived = models.BooleanField(default=False)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        constraints = [models.CheckConstraint(condition=Q(priority__in=["high", "normal", "low"]), name="valid_case_priority")]

    def __str__(self):
        return self.title


class Execution(models.Model):
    class Status(models.TextChoices):
        PASSED = "passed", "通过"
        FAILED = "failed", "失败"
        BLOCKED = "blocked", "阻塞"

    case = models.ForeignKey(TestCase, on_delete=models.PROTECT, related_name="executions")
    version = models.ForeignKey(Version, on_delete=models.PROTECT, related_name="executions")
    status = models.CharField("执行结果", max_length=8, choices=Status.choices)
    actual = models.TextField("实际结果")
    executor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    case_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["version", "case", "-id"], name="execution_latest_idx")]
        constraints = [models.CheckConstraint(condition=Q(status__in=["passed", "failed", "blocked"]), name="valid_execution_status")]


class Defect(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "待处理"
        FIXED = "fixed", "待回归"
        CLOSED = "closed", "已关闭"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="defects")
    execution = models.ForeignKey(Execution, on_delete=models.PROTECT, related_name="defects", null=True, blank=True)
    title = models.CharField("缺陷标题", max_length=200)
    description = models.TextField("缺陷说明")
    status = models.CharField("处理状态", max_length=8, choices=Status.choices, default=Status.OPEN)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_defects")
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_defects")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=Q(status__in=["open", "fixed", "closed"]), name="valid_defect_status")]


class Report(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="reports")
    version = models.ForeignKey(Version, on_delete=models.PROTECT, related_name="reports")
    title = models.CharField("报告名称", max_length=160)
    filename = models.CharField(max_length=200)
    data = models.BinaryField()
    sha256 = models.CharField(max_length=64, db_index=True)
    size = models.PositiveIntegerField()
    generated = models.BooleanField(default=False)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ChainState(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    tip_hash = models.CharField(max_length=64, default="0" * 64)
    next_height = models.PositiveIntegerField(default=0)


class Block(models.Model):
    height = models.PositiveIntegerField(unique=True)
    report = models.OneToOneField(Report, on_delete=models.PROTECT, related_name="block")
    payload = models.JSONField()
    previous_hash = models.CharField(max_length=64)
    block_hash = models.CharField(max_length=64, unique=True)
    nonce = models.PositiveBigIntegerField()
    difficulty = models.PositiveSmallIntegerField()
    timestamp = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["height"]


class AuditEvent(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class LoginAttempt(models.Model):
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
