import csv
import io
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import F, Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import (
    CaseForm, DefectForm, ExecutionForm, GenerateReportForm, MemberForm,
    ProjectForm, RegisterForm, ReportForm, VerifyForm, VersionForm,
)
from .models import Block, Defect, Execution, LoginAttempt, Membership, Project, TestCase
from .services import anchor_report, audit, fingerprint, generated_report, save_report, statistics, verify_chain


def accessible_projects(user):
    return Project.objects.filter(Q(owner=user) | Q(memberships__user=user)).distinct()


def project_access(write=False, manager=False, allow_archived=False):
    def decorate(view):
        @login_required
        @wraps(view)
        def wrapped(request, project_id, *args, **kwargs):
            project = get_object_or_404(accessible_projects(request.user), pk=project_id)
            membership = project.memberships.filter(user=request.user).first()
            role = "manager" if project.owner_id == request.user.pk else membership.role
            if manager and role != "manager" or write and role not in {"manager", "tester"}:
                raise PermissionDenied("当前账号没有操作权限。")
            if write and project.archived and not allow_archived:
                messages.error(request, "项目已归档，恢复项目后才能修改。")
                return redirect("project", project_id=project.pk)
            request.project_role = role
            return view(request, project, *args, **kwargs)
        return wrapped
    return decorate


def form_page(request, form, title, project=None):
    return render(request, "form.html", {"form": form, "title": title, "project": project})


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)


@require_http_methods(["GET", "POST"])
def sign_in(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        key = fingerprint(request.POST.get("username", "").strip().encode())
        attempt, _ = LoginAttempt.objects.get_or_create(key=key)
        if attempt.updated_at < timezone.now() - timedelta(minutes=15):
            attempt.failures = 0
            attempt.save()
        if attempt.failures >= 5:
            form.add_error(None, "登录失败次数过多，请 15 分钟后重试。")
        elif form.is_valid():
            LoginAttempt.objects.filter(pk=attempt.pk).delete()
            login(request, form.get_user())
            destination = request.POST.get("next", "")
            if not url_has_allowed_host_and_scheme(destination, {request.get_host()}, require_https=request.is_secure()):
                destination = reverse("dashboard")
            return redirect(destination or "dashboard")
        else:
            LoginAttempt.objects.filter(pk=attempt.pk).update(failures=F("failures") + 1, updated_at=timezone.now())
    return render(request, "registration/login.html", {"form": form, "registration_open": settings.ALLOW_REGISTRATION})


@require_http_methods(["GET", "POST"])
def register(request):
    if not settings.ALLOW_REGISTRATION:
        raise PermissionDenied("当前未开放注册，请联系管理员。")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("dashboard")
    return form_page(request, form, "注册账号")


@login_required
@require_http_methods(["GET", "POST"])
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "密码已修改。")
        return redirect("dashboard")
    return form_page(request, form, "修改密码")


@login_required
@require_GET
def dashboard(request):
    projects = accessible_projects(request.user).select_related("owner")
    query = request.GET.get("q", "").strip()
    if query:
        projects = projects.filter(Q(name__icontains=query) | Q(description__icontains=query))
    page = Paginator(projects, 12).get_page(request.GET.get("page"))
    return render(request, "dashboard.html", {"page_obj": page, "query": query})


@login_required
@require_http_methods(["GET", "POST"])
def project_create(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            audit(project, request.user, "创建项目")
        return redirect("project", project_id=project.pk)
    return form_page(request, form, "创建项目")


@project_access()
@require_GET
def project_detail(request, project):
    version_id = request.GET.get("version", "")
    version = get_object_or_404(project.versions, pk=version_id) if version_id.isdigit() else None
    return render(request, "project.html", {
        "project": project, "stats": statistics(project, version), "version": version,
        "versions": project.versions.all(), "recent": project.events.select_related("actor")[:10],
        "open_defects": project.defects.exclude(status="closed").count(),
        "report_count": project.reports.count(),
    })


@project_access(write=True, manager=True)
@require_http_methods(["GET", "POST"])
def project_edit(request, project):
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            audit(project, request.user, "修改项目信息")
        return redirect("project", project_id=project.pk)
    return form_page(request, form, "编辑项目", project)


@project_access(write=True, manager=True, allow_archived=True)
@require_POST
def project_archive(request, project):
    with transaction.atomic():
        project = Project.objects.select_for_update().get(pk=project.pk)
        project.archived = not project.archived
        project.save(update_fields=["archived"])
        audit(project, request.user, "归档项目" if project.archived else "恢复项目")
    return redirect("project", project_id=project.pk)


@project_access(write=True)
@require_http_methods(["GET", "POST"])
def version_create(request, project):
    form = VersionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if project.versions.filter(name=form.cleaned_data["name"]).exists():
            form.add_error("name", "当前项目已有同名版本。")
        else:
            with transaction.atomic():
                version = form.save(commit=False)
                version.project = project
                version.save()
                audit(project, request.user, f"新增版本 {version.name}")
            return redirect("project", project_id=project.pk)
    return form_page(request, form, "新增版本", project)


@project_access()
@require_GET
def case_list(request, project):
    cases = project.cases.all()
    query = request.GET.get("q", "").strip()
    if request.GET.get("archived") != "1":
        cases = cases.filter(archived=False)
    if query:
        cases = cases.filter(Q(title__icontains=query) | Q(steps__icontains=query))
    priority = request.GET.get("priority", "")
    if priority:
        cases = cases.filter(priority=priority)
    return render(request, "cases.html", {
        "project": project, "page_obj": Paginator(cases, 20).get_page(request.GET.get("page")),
        "query": query, "priorities": TestCase.Priority.choices,
    })


@project_access(write=True)
@require_http_methods(["GET", "POST"])
def case_edit(request, project, case_id=None):
    case = get_object_or_404(project.cases, pk=case_id) if case_id else None
    form = CaseForm(request.POST or None, instance=case)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            updated = form.save(commit=False)
            updated.project = project
            if not case:
                updated.creator = request.user
            updated.save()
            audit(project, request.user, f"{'修改' if case else '新增'}用例 #{updated.pk}")
        return redirect("cases", project_id=project.pk)
    return form_page(request, form, "编辑测试用例" if case else "新增测试用例", project)


@project_access(write=True)
@require_POST
def case_archive(request, project, case_id):
    case = get_object_or_404(project.cases, pk=case_id)
    with transaction.atomic():
        case.archived = not case.archived
        case.save(update_fields=["archived"])
        audit(project, request.user, f"{'归档' if case.archived else '恢复'}用例 #{case.pk}")
    return redirect("cases", project_id=project.pk)


@project_access(write=True)
@require_http_methods(["GET", "POST"])
def execute_case(request, project, case_id):
    case = get_object_or_404(project.cases, pk=case_id, archived=False)
    form = ExecutionForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            execution = form.save(commit=False)
            execution.case = case
            execution.executor = request.user
            execution.case_snapshot = {"title": case.title, "steps": case.steps, "expected": case.expected, "priority": case.priority}
            execution.save()
            audit(project, request.user, f"执行用例 #{case.pk}：{execution.get_status_display()}")
        return redirect("executions", project_id=project.pk)
    return render(request, "execute.html", {"project": project, "case": case, "form": form})


@project_access()
@require_GET
def execution_list(request, project):
    rows = Execution.objects.filter(case__project=project).select_related("case", "version", "executor")
    for param in ["status", "version_id"]:
        value = request.GET.get(param)
        if value and (param != "version_id" or value.isdigit()):
            rows = rows.filter(**{param: value})
    return render(request, "executions.html", {
        "project": project, "page_obj": Paginator(rows, 20).get_page(request.GET.get("page")),
        "statuses": Execution.Status.choices,
    })


@project_access()
@require_GET
def defect_list(request, project):
    defects = project.defects.select_related("assignee", "execution")
    if request.GET.get("status"):
        defects = defects.filter(status=request.GET["status"])
    return render(request, "defects.html", {
        "project": project, "page_obj": Paginator(defects, 20).get_page(request.GET.get("page")),
        "statuses": Defect.Status.choices,
    })


@project_access(write=True)
@require_http_methods(["GET", "POST"])
def defect_edit(request, project, defect_id=None):
    defect = get_object_or_404(project.defects, pk=defect_id) if defect_id else None
    form = DefectForm(request.POST or None, instance=defect, project=project)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            updated = form.save(commit=False)
            updated.project = project
            if not defect:
                updated.creator = request.user
            updated.save()
            audit(project, request.user, f"更新缺陷 #{updated.pk}：{updated.get_status_display()}")
        return redirect("defects", project_id=project.pk)
    return form_page(request, form, "编辑缺陷" if defect else "登记缺陷", project)


@project_access(write=True, manager=True)
@require_http_methods(["GET", "POST"])
def members(request, project):
    form = MemberForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = get_user_model().objects.get(username=form.cleaned_data["username"])
        if user.pk == project.owner_id:
            form.add_error("username", "项目负责人已拥有管理权限。")
        else:
            with transaction.atomic():
                Membership.objects.update_or_create(project=project, user=user, defaults={"role": form.cleaned_data["role"]})
                audit(project, request.user, f"设置成员 {user.username} 为 {form.cleaned_data['role']}")
            return redirect("members", project_id=project.pk)
    return render(request, "members.html", {
        "project": project, "form": form, "members": project.memberships.select_related("user"),
    })


@project_access(write=True, manager=True)
@require_POST
def member_remove(request, project, member_id):
    member = get_object_or_404(project.memberships, pk=member_id)
    username = member.user.username
    with transaction.atomic():
        member.delete()
        audit(project, request.user, f"移除成员 {username}")
    return redirect("members", project_id=project.pk)


@project_access()
@require_GET
def report_list(request, project):
    reports = project.reports.select_related("version", "creator", "block")
    return render(request, "reports.html", {
        "project": project, "page_obj": Paginator(reports, 20).get_page(request.GET.get("page")),
    })


@project_access(write=True)
@require_http_methods(["GET", "POST"])
def report_create(request, project, generate=False):
    form_class = GenerateReportForm if generate else ReportForm
    form = form_class(request.POST or None, request.FILES or None, project=project)
    if request.method == "POST" and form.is_valid():
        title = form.cleaned_data["title"]
        version = form.cleaned_data["version"]
        data = generated_report(project, version, title) if generate else form.cleaned_data["file"].read()
        filename = "test-report.txt" if generate else form.cleaned_data["file"].name
        try:
            report = save_report(project, version, title, filename, data, request.user, generate)
            return redirect("report", project_id=project.pk, report_id=report.pk)
        except ValidationError as error:
            form.add_error(None, error)
    return form_page(request, form, "生成测试报告" if generate else "上传测试报告", project)


@project_access()
@require_GET
def report_detail(request, project, report_id):
    report = get_object_or_404(project.reports.select_related("version", "creator", "block"), pk=report_id)
    return render(request, "report.html", {"project": project, "report": report, "form": VerifyForm()})


@project_access()
@require_GET
def report_download(request, project, report_id):
    report = get_object_or_404(project.reports, pk=report_id)
    response = FileResponse(io.BytesIO(bytes(report.data)), as_attachment=True, filename=report.filename, content_type="application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    return response


@project_access(write=True)
@require_POST
def report_anchor(request, project, report_id):
    report = get_object_or_404(project.reports, pk=report_id)
    try:
        block = anchor_report(report.pk, request.user)
        messages.success(request, f"存证完成，区块高度 {block.height}。")
    except ValidationError as error:
        messages.error(request, "；".join(error.messages))
    return redirect("report", project_id=project.pk, report_id=report.pk)


@project_access()
@require_POST
def report_verify(request, project, report_id):
    report = get_object_or_404(project.reports.select_related("version", "block"), pk=report_id)
    form = VerifyForm(request.POST, request.FILES)
    result = None
    if form.is_valid():
        digest = fingerprint(form.cleaned_data["file"].read())
        block = Block.objects.filter(report=report).first()
        if block:
            valid, detail = verify_chain()
            if not valid:
                result = {"ok": False, "message": f"链完整性验证失败：{detail}", "hash": digest}
            else:
                match = digest == block.payload["sha256"]
                result = {"ok": match, "message": "文件与链上存证一致" if match else "文件与链上存证不一致", "hash": digest}
        else:
            match = digest == report.sha256
            result = {"ok": match, "message": "文件与上传版本一致（尚未存证）" if match else "文件与上传版本不一致", "hash": digest}
        audit(project, request.user, f"验证报告 #{report.pk}：{result['message']}")
    return render(request, "report.html", {"project": project, "report": report, "form": form, "result": result})


@project_access()
@require_GET
def chain_browser(request, project):
    blocks = Block.objects.filter(report__project=project).select_related("report").order_by("-height")
    return render(request, "chain.html", {"project": project, "page_obj": Paginator(blocks, 10).get_page(request.GET.get("page"))})


@project_access()
@require_POST
def chain_check(request, project):
    valid, detail = verify_chain()
    audit(project, request.user, f"验证链完整性：{'通过' if valid else '失败'}")
    (messages.success if valid else messages.error)(request, detail)
    return redirect("chain", project_id=project.pk)


@project_access()
@require_GET
def events(request, project):
    rows = project.events.select_related("actor")
    return render(request, "events.html", {"project": project, "page_obj": Paginator(rows, 30).get_page(request.GET.get("page"))})


@project_access()
@require_GET
def export_csv(request, project):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="testchain-executions.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["用例编号", "用例标题", "版本", "结果", "实际结果", "执行人", "执行时间"])
    rows = Execution.objects.filter(case__project=project).select_related("case", "version", "executor")
    for row in rows.iterator():
        values = [row.case_id, row.case_snapshot.get("title", row.case.title), row.version.name, row.get_status_display(), row.actual, row.executor.username, row.created_at.isoformat()]
        writer.writerow(["'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value for value in values])
    return response


@project_access()
@require_GET
def project_api(request, project):
    return JsonResponse({
        "id": project.pk, "name": project.name, "archived": project.archived,
        "statistics": statistics(project),
        "versions": list(project.versions.values("id", "name")),
    }, json_dumps_params={"ensure_ascii": False})
