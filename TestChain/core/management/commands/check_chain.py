from django.core.management.base import BaseCommand, CommandError

from core.services import verify_chain


class Command(BaseCommand):
    help = "检查报告文件、区块、PoW 与链头一致性"

    def handle(self, *args, **options):
        valid, detail = verify_chain()
        if not valid:
            raise CommandError(detail)
        self.stdout.write(self.style.SUCCESS(detail))
