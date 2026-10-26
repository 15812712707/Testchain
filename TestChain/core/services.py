import hashlib
import json
import time
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import OperationalError, transaction
from django.db.models import F, Max
from django.utils import timezone

from .models import AuditEvent, Block, ChainState, Execution, Project, Report


def fingerprint(data):
    return hashlib.sha256(data).hexdigest()


def canonical_hash(height, previous_hash, payload, timestamp, difficulty, nonce):
    document = {
        "height": height, "previous_hash": previous_hash, "payload": payload,
        "timestamp": timestamp, "difficulty": difficulty, "nonce": nonce,
    }
    return fingerprint(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


@transaction.atomic
def verify_chain():
    state = ChainState.objects.select_for_update().get(pk=1)
    previous_hash = "0" * 64
    count = 0
    for expected_height, block in enumerate(Block.objects.select_related("report").order_by("height")):
        count += 1
        if block.height != expected_height or block.previous_hash != previous_hash:
            return False, f"区块 #{block.height} 的顺序或前序哈希不正确"
        if block.difficulty != settings.CHAIN_DIFFICULTY:
            return False, f"区块 #{block.height} 的难度不正确"
        actual = canonical_hash(block.height, block.previous_hash, block.payload, block.timestamp, block.difficulty, block.nonce)
        if actual != block.block_hash or not actual.startswith("0" * block.difficulty):
            return False, f"区块 #{block.height} 的哈希或工作量证明不正确"
        if block.payload != report_payload(block.report):
            return False, f"区块 #{block.height} 的报告元数据不匹配"
        if fingerprint(bytes(block.report.data)) != block.payload["sha256"]:
            return False, f"区块 #{block.height} 对应的报告文件已改变"
        previous_hash = block.block_hash
    if state.tip_hash != previous_hash or state.next_height != count:
        return False, "链头记录与实际区块不一致"
    return True, f"验证通过，共 {count} 个区块"


def report_payload(report):
    return {
        "report_id": report.pk, "project_id": report.project_id, "version_id": report.version_id,
        "sha256": report.sha256, "size": report.size, "filename": report.filename,
        "creator_id": report.creator_id, "created_at": report.created_at.isoformat(timespec="milliseconds"),
    }


def anchor_report(report_id, actor):
    for attempt in range(5):
        try:
            with transaction.atomic():
                state = ChainState.objects.select_for_update().get(pk=1)
                ChainState.objects.filter(pk=1).update(next_height=F("next_height") + 0)
                report = Report.objects.select_for_update().select_related("project").get(pk=report_id)
                if report.project.archived:
                    raise ValidationError("项目已归档，不能继续存证。")
                existing = Block.objects.filter(report=report).first()
                if existing:
                    return existing
                valid, detail = verify_chain()
                if not valid:
                    raise ValidationError(f"存证中止：{detail}")
                if fingerprint(bytes(report.data)) != report.sha256:
                    raise ValidationError("报告文件与保存的哈希不一致，不能存证。")
                payload = report_payload(report)
                timestamp = timezone.now().isoformat()
                difficulty = settings.CHAIN_DIFFICULTY
                nonce = 0
                while True:
                    block_hash = canonical_hash(state.next_height, state.tip_hash, payload, timestamp, difficulty, nonce)
                    if block_hash.startswith("0" * difficulty):
                        break
                    nonce += 1
                block = Block.objects.create(
                    height=state.next_height, report=report, payload=payload,
                    previous_hash=state.tip_hash, block_hash=block_hash, timestamp=timestamp,
                    difficulty=difficulty, nonce=nonce,
                )
                state.tip_hash = block_hash
                state.next_height += 1
                state.save(update_fields=["tip_hash", "next_height"])
                audit(report.project, actor, f"报告 #{report.pk} 完成存证，区块 #{block.height}")
                return block
        except OperationalError as error:
            if not any(marker in str(error).lower() for marker in ["locked", "deadlock", "1213", "1205"]):
                raise
            if attempt == 4:
                raise ValidationError("当前存证请求较多，请稍后重试。") from error
            time.sleep(0.05 * (attempt + 1))


def audit(project, actor, action):
    AuditEvent.objects.create(project=project, actor=actor, action=action)


def latest_executions(project, version=None):
    rows = Execution.objects.filter(case__project=project)
    if version:
        rows = rows.filter(version=version)
    latest_ids = rows.values("case_id").annotate(latest_id=Max("id")).values("latest_id")
    return Execution.objects.filter(id__in=latest_ids).select_related("case", "version", "executor")


def statistics(project, version=None):
    latest = list(latest_executions(project, version))
    active_ids = set(project.cases.filter(archived=False).values_list("pk", flat=True))
    latest = [execution for execution in latest if execution.case_id in active_ids]
    total = len(active_ids)
    passed = sum(execution.status == "passed" for execution in latest)
    return {
        "total": total, "executed": len(latest), "passed": passed,
        "failed": sum(execution.status == "failed" for execution in latest),
        "blocked": sum(execution.status == "blocked" for execution in latest),
        "pending": total - len(latest), "rate": round(passed * 100 / total) if total else 0,
    }


def save_report(project, version, title, filename, data, actor, generated=False):
    if version.project_id != project.pk:
        raise ValidationError("报告版本不属于当前项目。")
    if not data or len(data) > settings.REPORT_MAX_BYTES:
        raise ValidationError("报告文件必须非空且不能超过 10 MB。")
    with transaction.atomic():
        locked_project = Project.objects.select_for_update().get(pk=project.pk)
        if locked_project.archived:
            raise ValidationError("项目已归档。")
        report = Report.objects.create(
            project=project, version=version, title=title,
            filename=Path(filename.replace("\\", "/")).name[:200], data=data,
            sha256=fingerprint(data), size=len(data), creator=actor, generated=generated,
        )
        audit(project, actor, f"{'生成' if generated else '上传'}报告 #{report.pk}：{title}")
        return report


def generated_report(project, version, title):
    stats = statistics(project, version)
    lines = [
        title, f"项目：{project.name}", f"版本：{version.name}",
        f"生成时间：{timezone.localtime().isoformat()}",
        f"有效用例：{stats['total']} | 通过：{stats['passed']} | 失败：{stats['failed']} | 阻塞：{stats['blocked']} | 未执行：{stats['pending']}",
        "", "执行记录（每个用例在该版本的最近一次执行）：",
    ]
    for execution in latest_executions(project, version).order_by("case_id"):
        snapshot = execution.case_snapshot
        lines.extend([
            "", f"用例 #{execution.case_id}：{snapshot.get('title', execution.case.title)}",
            f"步骤：{snapshot.get('steps', '')}", f"预期：{snapshot.get('expected', '')}",
            f"结果：{execution.get_status_display()}", f"实际：{execution.actual}",
            f"执行人：{execution.executor.username} | 时间：{timezone.localtime(execution.created_at).isoformat()}",
        ])
    lines.extend(["", "缺陷记录："])
    for defect in project.defects.filter(execution__version=version).select_related("assignee"):
        lines.append(f"#{defect.pk} {defect.title} | {defect.get_status_display()} | {defect.description}")
    return "\n".join(lines).encode("utf-8")
