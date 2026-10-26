from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase

from core.models import Block, ChainState, Project, Report, Version
from core.services import anchor_report, save_report, verify_chain


class BackupTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("backup-user", password="test-password")
        self.project = Project.objects.create(name="备份项目", owner=self.user)
        self.version = Version.objects.create(project=self.project, name="v1")
        self.report = save_report(self.project, self.version, "报告", "report.txt", b"original", self.user)
        anchor_report(self.report.pk, self.user)

    def test_backup_and_restore_preserve_binary_and_chain(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "backup.json"
            call_command("backup", output=output, stdout=StringIO())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            Report.objects.filter(pk=self.report.pk).update(data=b"corrupted")
            self.assertFalse(verify_chain()[0])
            call_command("loaddata", str(output), stdout=StringIO())
            self.report.refresh_from_db()
            self.assertEqual(bytes(self.report.data), b"original")
            self.assertTrue(verify_chain()[0])

    def test_check_chain_command_fails_on_corruption(self):
        Block.objects.update(block_hash="f" * 64)
        with self.assertRaises(CommandError):
            call_command("check_chain", stdout=StringIO())


class ConcurrentAnchoringTests(TransactionTestCase):
    def setUp(self):
        ChainState.objects.get_or_create(pk=1)
        self.user = get_user_model().objects.create_user("concurrent-user")
        project = Project.objects.create(name="并发测试", owner=self.user)
        version = Version.objects.create(project=project, name="v1")
        self.reports = [save_report(project, version, f"报告 {index}", "report.txt", str(index).encode(), self.user) for index in range(2)]

    def anchor(self, report_id):
        close_old_connections()
        try:
            user = get_user_model().objects.get(pk=self.user.pk)
            return anchor_report(report_id, user).height
        finally:
            close_old_connections()

    def test_concurrent_requests_produce_one_contiguous_chain(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            heights = list(pool.map(self.anchor, [report.pk for report in self.reports]))
        self.assertEqual(sorted(heights), [0, 1])
        self.assertEqual(Block.objects.count(), 2)
        self.assertTrue(verify_chain()[0])

    def test_concurrent_duplicate_requests_are_idempotent(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            heights = list(pool.map(self.anchor, [self.reports[0].pk] * 2))
        self.assertEqual(heights, [0, 0])
        self.assertEqual(Block.objects.count(), 1)
        self.assertTrue(verify_chain()[0])
