from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Playbook(models.Model):
    name = models.CharField(max_length=255)
    git_repo = models.URLField(help_text="Git repository URL for the playbook", default="")
    repo_branch = models.CharField(max_length=255, default="main", help_text="Branch to use from the repository")
    project_root = models.CharField(max_length=1024, help_text="Root path of the Ansible project after clone", default="")
    modules = models.TextField(blank=True, help_text="Comma-separated list of additional Ansible modules to install", default="")
    playbook_file = models.CharField(max_length=1024, help_text="Playbook YAML file to run (relative to project root)", default="")
    description = models.TextField(blank=True)
    allowed_roles = models.ManyToManyField('Role', blank=True)

    def __str__(self):
        return self.name

class ScheduledTask(models.Model):
    playbook = models.ForeignKey(Playbook, on_delete=models.CASCADE)
    schedule = models.CharField(max_length=100)  # cron format
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.playbook.name} @ {self.schedule}"

class PlaybookRun(models.Model):
    playbook = models.ForeignKey(Playbook, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, default='pending')
    output = models.TextField(blank=True)
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    artifact_path = models.CharField(max_length=1024, blank=True, null=True, help_text='Path to the artifact directory for this run')
    git_command = models.TextField(blank=True, null=True, help_text='The git command used for this run')
    git_stdout = models.TextField(blank=True, null=True, help_text='Stdout from git clone')
    git_stderr = models.TextField(blank=True, null=True, help_text='Stderr from git clone')
    ansible_command = models.TextField(blank=True, null=True, help_text='The ansible-runner command used for this run')

    def __str__(self):
        return f"{self.playbook.name} run at {self.started_at}"

class Role(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('operator', 'Operator'),
        ('viewer', 'Viewer'),
    ]
    name = models.CharField(max_length=20, choices=ROLE_CHOICES, unique=True)
    users = models.ManyToManyField(User, blank=True)

    def __str__(self):
        return self.get_name_display()
