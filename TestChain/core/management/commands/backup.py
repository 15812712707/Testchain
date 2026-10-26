from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import ChainState
from core.services import verify_chain


class Command(BaseCommand):
    help = "备份账号、业务数据、报告原件和区块；执行前暂停业务写入"

    def add_arguments(self, parser):
        parser.add_argument("--output", type=Path)

    def handle(self, *args, **options):
        output = options["output"] or settings.BASE_DIR / "backups" / f"testchain-{timezone.now():%Y%m%d-%H%M%S-%f}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with transaction.atomic():
                ChainState.objects.select_for_update().get(pk=1)
                valid, detail = verify_chain()
                if not valid:
                    raise CommandError(f"备份中止，{detail}")
                with output.open("x", encoding="utf-8") as stream:
                    output.chmod(0o600)
                    call_command(
                        "dumpdata", natural_foreign=True, indent=2, stdout=stream,
                        exclude=["contenttypes", "auth.permission", "sessions", "admin.logentry"],
                    )
        except FileExistsError as error:
            raise CommandError("输出文件已存在，请使用其他文件名。") from error
        self.stdout.write(self.style.SUCCESS(f"备份完成：{output}"))
