from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Block, ChainState, Defect, Execution, Membership, Project, Report, TestCase as Case, Version
from core.services import anchor_report, fingerprint, save_report, statistics, verify_chain


class SystemTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user("owner", password="Own-Test-82_Change")
        cls.tester = user_model.objects.create_user("tester", password="Test-82_Change")
        cls.viewer = user_model.objects.create_user("viewer", password="View-82_Change")
        cls.outsider = user_model.objects.create_user("outsider", password="Out-82_Change")
        cls.project = Project.objects.create(name="支付服务", owner=cls.owner)
        cls.other = Project.objects.create(name="隔离项目", owner=cls.outsider)
        cls.version = Version.objects.create(project=cls.project, name="v1.0")
        cls.other_version = Version.objects.create(project=cls.other, name="private-v1")
        cls.case = Case.objects.create(project=cls.project, title="登录", steps="输入正确账号", expected="成功", creator=cls.owner)
        Membership.objects.create(project=cls.project, user=cls.tester, role="tester")
        Membership.objects.create(project=cls.project, user=cls.viewer, role="viewer")

    def setUp(self):
        self.client.force_login(self.owner)

    def url(self, name, *args):
        return reverse(name, args=[self.project.pk, *args])

    def report(self, data=b"original-report"):
        return save_report(self.project, self.version, "验收报告", "report.txt", data, self.owner)

    def test_anonymous_is_redirected(self):
        self.client.logout()
        response = self.client.get(self.url("project"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_registration_hashes_password_and_logs_in(self):
        self.client.logout()
        response = self.client.post(reverse("register"), {"username": "new-user", "password1": "Secure-test-918!", "password2": "Secure-test-918!"})
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username="new-user")
        self.assertTrue(user.check_password("Secure-test-918!"))
        self.assertNotEqual(user.password, "Secure-test-918!")

    @override_settings(ALLOW_REGISTRATION=False)
    def test_registration_can_be_disabled(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("register")).status_code, 403)

    def test_login_rejects_external_next_url(self):
        self.client.logout()
        response = self.client.post(reverse("login"), {"username": "owner", "password": "Own-Test-82_Change", "next": "https://external.invalid/"})
        self.assertEqual(response.url, "/")

    def test_login_limits_failed_attempts(self):
        self.client.logout()
        for _ in range(5):
            self.client.post(reverse("login"), {"username": "owner", "password": "incorrect"})
        response = self.client.post(reverse("login"), {"username": "owner", "password": "Own-Test-82_Change"})
        self.assertContains(response, "15 分钟后重试")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_csrf_is_required_for_writes(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url("project_archive")).status_code, 403)

    def test_outsider_cannot_access_any_project_route(self):
        report = self.report()
        self.client.force_login(self.outsider)
        for name, args in [("project", []), ("cases", []), ("reports", []), ("report_download", [report.pk]), ("project_api", []), ("events", [])]:
            with self.subTest(route=name):
                self.assertEqual(self.client.get(self.url(name, *args)).status_code, 404)

    def test_viewer_cannot_write(self):
        report = self.report()
        self.client.force_login(self.viewer)
        for name, args in [("case_create", []), ("version_create", []), ("report_upload", []), ("members", []), ("report_anchor", [report.pk])]:
            with self.subTest(route=name):
                self.assertEqual(self.client.post(self.url(name, *args), {}).status_code, 403)

    def test_tester_cannot_manage_members(self):
        self.client.force_login(self.tester)
        self.assertEqual(self.client.post(self.url("members"), {"username": "outsider", "role": "manager"}).status_code, 403)

    def test_manager_can_add_and_remove_member(self):
        response = self.client.post(self.url("members"), {"username": "outsider", "role": "viewer"})
        self.assertEqual(response.status_code, 302)
        member = Membership.objects.get(project=self.project, user=self.outsider)
        self.client.post(self.url("member_remove", member.pk))
        self.assertFalse(Membership.objects.filter(pk=member.pk).exists())

    def test_project_creation(self):
        response = self.client.post(reverse("project_create"), {"name": "API 网关", "description": "接口测试"})
        project = Project.objects.get(name="API 网关")
        self.assertEqual(project.owner, self.owner)
        self.assertRedirects(response, reverse("project", args=[project.pk]))
        self.assertTrue(project.events.filter(action="创建项目").exists())

    def test_duplicate_version_rejected(self):
        response = self.client.post(self.url("version_create"), {"name": "v1.0"})
        self.assertContains(response, "已有同名版本")
        self.assertEqual(self.project.versions.count(), 1)

    def test_case_edit_keeps_execution_snapshot(self):
        self.client.post(self.url("execute", self.case.pk), {"version": self.version.pk, "status": "passed", "actual": "成功"})
        self.client.post(self.url("case_edit", self.case.pk), {"title": "新标题", "steps": "新步骤", "expected": "新预期", "priority": "high"})
        execution = Execution.objects.get()
        self.assertEqual(execution.case_snapshot["title"], "登录")
        self.assertEqual(Case.objects.get(pk=self.case.pk).title, "新标题")

    def test_cross_project_version_cannot_be_used(self):
        response = self.client.post(self.url("execute", self.case.pk), {"version": self.other_version.pk, "status": "passed", "actual": "成功"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Execution.objects.exists())

    def test_statistics_use_latest_execution_per_version(self):
        for status in ["failed", "passed"]:
            Execution.objects.create(case=self.case, version=self.version, status=status, actual="观察结果", executor=self.owner)
        second_version = Version.objects.create(project=self.project, name="v2.0")
        Execution.objects.create(case=self.case, version=second_version, status="blocked", actual="环境不可用", executor=self.owner)
        self.assertEqual(statistics(self.project, self.version)["passed"], 1)
        self.assertEqual(statistics(self.project)["blocked"], 1)

    def test_defect_rejects_foreign_assignee_and_execution(self):
        foreign_case = Case.objects.create(project=self.other, title="其他用例", steps="操作", expected="预期", creator=self.outsider)
        foreign_execution = Execution.objects.create(case=foreign_case, version=self.other_version, status="failed", actual="失败", executor=self.outsider)
        response = self.client.post(self.url("defect_create"), {"title": "问题", "description": "说明", "status": "open", "assignee": self.outsider.pk, "execution": foreign_execution.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Defect.objects.exists())

    def test_defect_lifecycle(self):
        self.client.post(self.url("defect_create"), {"title": "错误提示", "description": "未显示", "status": "open", "assignee": self.tester.pk})
        defect = Defect.objects.get()
        for status in ["fixed", "closed"]:
            self.client.post(self.url("defect_edit", defect.pk), {"title": "错误提示", "description": "已修复", "status": status, "assignee": self.tester.pk})
            defect.refresh_from_db()
            self.assertEqual(defect.status, status)

    def test_binary_upload_download_preserves_exact_bytes(self):
        payload = b"%PDF-1.7\n\x00\xff\r\n\x80content"
        response = self.client.post(self.url("report_upload"), {"title": "PDF报告", "version": self.version.pk, "file": SimpleUploadedFile("测试.pdf", payload)})
        self.assertEqual(response.status_code, 302)
        report = Report.objects.get()
        self.assertEqual(report.sha256, fingerprint(payload))
        self.assertEqual(report.size, len(payload))
        downloaded = self.client.get(self.url("report_download", report.pk))
        self.assertEqual(b"".join(downloaded.streaming_content), payload)
        self.assertEqual(downloaded["Cache-Control"], "private, no-store")

    def test_upload_rejects_unsupported_file(self):
        response = self.client.post(self.url("report_upload"), {"title": "脚本", "version": self.version.pk, "file": SimpleUploadedFile("payload.html", b"<script>bad</script>")})
        self.assertContains(response, "扩展名暂不支持")
        self.assertFalse(Report.objects.exists())

    @override_settings(REPORT_MAX_BYTES=5)
    def test_upload_size_limit(self):
        self.client.post(self.url("report_upload"), {"title": "超限", "version": self.version.pk, "file": SimpleUploadedFile("report.txt", b"too long")})
        self.assertFalse(Report.objects.exists())

    def test_generated_report_contains_version_results(self):
        self.client.post(self.url("execute", self.case.pk), {"version": self.version.pk, "status": "failed", "actual": "返回500"})
        response = self.client.post(self.url("report_generate"), {"title": "回归报告", "version": self.version.pk})
        self.assertEqual(response.status_code, 302)
        report = Report.objects.get()
        text = bytes(report.data).decode()
        self.assertIn("返回500", text)
        self.assertIn("v1.0", text)
        self.assertTrue(report.generated)

    def test_anchor_is_idempotent_and_chain_survives_reload(self):
        report = self.report()
        self.client.post(self.url("report_anchor", report.pk))
        self.client.post(self.url("report_anchor", report.pk))
        self.assertEqual(Block.objects.count(), 1)
        block = Block.objects.get()
        self.assertEqual(block.payload["sha256"], report.sha256)
        self.assertTrue(block.block_hash.startswith("000"))
        self.assertEqual(ChainState.objects.get(pk=1).next_height, 1)
        self.assertTrue(verify_chain()[0])

    def test_multiple_blocks_link_correctly(self):
        first = anchor_report(self.report().pk, self.owner)
        second = anchor_report(self.report(b"new report").pk, self.owner)
        self.assertEqual(second.previous_hash, first.block_hash)
        self.assertEqual(second.height, 1)
        self.assertTrue(verify_chain()[0])

    def test_report_verification_uses_chain_record(self):
        report = self.report()
        anchor_report(report.pk, self.owner)
        for data, expected in [(b"original-report", "文件与链上存证一致"), (b"modified-report", "文件与链上存证不一致")]:
            response = self.client.post(self.url("report_verify", report.pk), {"file": SimpleUploadedFile("report.txt", data)})
            self.assertContains(response, expected)

    def test_tampering_report_bytes_breaks_chain(self):
        report = self.report()
        anchor_report(report.pk, self.owner)
        Report.objects.filter(pk=report.pk).update(data=b"tampered")
        self.assertFalse(verify_chain()[0])
        with self.assertRaises(ValidationError):
            anchor_report(self.report(b"another").pk, self.owner)

    def test_tampering_nonce_breaks_chain(self):
        block = anchor_report(self.report().pk, self.owner)
        Block.objects.filter(pk=block.pk).update(nonce=block.nonce + 1)
        self.assertFalse(verify_chain()[0])

    def test_tampering_metadata_breaks_chain(self):
        report = self.report()
        anchor_report(report.pk, self.owner)
        Report.objects.filter(pk=report.pk).update(filename="changed.txt")
        self.assertFalse(verify_chain()[0])

    def test_deleting_tail_block_is_detected(self):
        anchor_report(self.report().pk, self.owner)
        Block.objects.all().delete()
        self.assertFalse(verify_chain()[0])

    def test_archived_project_rejects_writes(self):
        report = self.report()
        self.client.post(self.url("project_archive"))
        response = self.client.post(self.url("report_anchor", report.pk))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Block.objects.exists())
        self.assertEqual(self.client.get(self.url("reports")).status_code, 200)
        self.client.post(self.url("project_archive"))
        self.client.post(self.url("report_anchor", report.pk))
        self.assertTrue(Block.objects.exists())

    def test_mutations_cannot_use_get(self):
        self.assertEqual(self.client.get(self.url("project_archive")).status_code, 405)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)

    def test_csv_escapes_spreadsheet_formulas(self):
        Execution.objects.create(case=self.case, version=self.version, status="failed", actual="=HYPERLINK(\"https://example.invalid\")", executor=self.owner)
        response = self.client.get(self.url("export_csv"))
        self.assertIn("'=HYPERLINK", response.content.decode())

    def test_database_rejects_duplicate_membership(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Membership.objects.create(project=self.project, user=self.viewer, role="viewer")

    def test_all_primary_pages_render_and_escape_user_text(self):
        self.project.name = "<script>alert(1)</script>"
        self.project.save()
        report = self.report()
        anchor_report(report.pk, self.owner)
        for name, args in [("project", []), ("cases", []), ("executions", []), ("defects", []), ("reports", []), ("report", [report.pk]), ("chain", []), ("events", []), ("members", [])]:
            with self.subTest(route=name):
                response = self.client.get(self.url(name, *args))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "<script>alert(1)</script>")

    def test_paginated_search_preserves_filters(self):
        Case.objects.bulk_create([Case(project=self.project, title=f"搜索用例 {number}", steps="步骤", expected="结果", creator=self.owner) for number in range(25)])
        response = self.client.get(self.url("cases"), {"q": "搜索", "priority": "normal"})
        self.assertContains(response, "page=2")
        self.assertEqual(len(response.context["page_obj"]), 20)

    def test_project_api_requires_membership(self):
        response = self.client.get(self.url("project_api"))
        self.assertEqual(response.json()["statistics"]["total"], 1)
        self.assertNotIn("data", response.json())

    def test_health_checks_database(self):
        self.assertEqual(self.client.get(reverse("health")).json(), {"status": "ok"})

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_health_probe_works_when_https_is_enforced(self):
        self.assertEqual(self.client.get(reverse("health")).status_code, 200)
        self.assertEqual(self.client.get(reverse("login")).status_code, 301)
