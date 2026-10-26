from django.contrib import admin

from .models import AuditEvent, Block, Defect, Execution, Membership, Project, Report, TestCase, Version


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "archived", "created_at"]
    search_fields = ["name", "owner__username"]
    list_filter = ["archived"]


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Report)
class ReportAdmin(ReadOnlyAdmin):
    list_display = ["id", "title", "project", "sha256", "created_at"]
    exclude = ["data"]


@admin.register(Block)
class BlockAdmin(ReadOnlyAdmin):
    list_display = ["height", "report", "block_hash", "created_at"]


@admin.register(AuditEvent)
class AuditAdmin(ReadOnlyAdmin):
    list_display = ["created_at", "actor", "project", "action"]
    list_filter = ["project"]


admin.site.register([Membership, Version, TestCase, Defect], ReadOnlyAdmin)
admin.site.register(Execution, ReadOnlyAdmin)
admin.site.site_header = "TestChain 系统管理"
admin.site.site_title = "TestChain"
