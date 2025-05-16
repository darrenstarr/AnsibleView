from .models import Playbook, ScheduledTask, PlaybookRun, Role
from django.contrib import admin

@admin.register(Playbook)
class PlaybookAdmin(admin.ModelAdmin):
    list_display = ('name', 'git_repo', 'repo_branch', 'project_root', 'modules', 'playbook_file', 'description')
    filter_horizontal = ('allowed_roles',)

@admin.register(ScheduledTask)
class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ('playbook', 'schedule', 'created_by', 'enabled')
    list_filter = ('enabled',)

@admin.register(PlaybookRun)
class PlaybookRunAdmin(admin.ModelAdmin):
    list_display = ('playbook', 'started_at', 'finished_at', 'status', 'triggered_by')
    list_filter = ('status',)
    search_fields = ('output',)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name',)
    filter_horizontal = ('users',)
