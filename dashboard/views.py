from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Playbook, PlaybookRun, ScheduledTask, Role
from django.contrib import messages
from django.utils import timezone
import ansible_runner
import logging
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
import os
import shutil
import subprocess
from threading import Thread
import json
from django.contrib.auth import logout

logger = logging.getLogger('dashboard')

def is_admin(user):
    return user.is_authenticated and user.role_set.filter(name='admin').exists()

def is_operator(user):
    return user.is_authenticated and user.role_set.filter(name='operator').exists()

def is_viewer(user):
    return user.is_authenticated and user.role_set.filter(name='viewer').exists()

@login_required
def dashboard_home(request):
    playbooks = Playbook.objects.all()
    if request.method == 'POST' and request.user.is_authenticated and (request.user.role_set.filter(name='admin').exists() or request.user.role_set.filter(name='operator').exists()):
        playbook_id = request.POST.get('run_playbook_id')
        if playbook_id:
            playbook = get_object_or_404(Playbook, pk=playbook_id)
            runner = ansible_runner.run(private_data_dir='.', playbook=playbook.playbook_file, verbosity=4)
            output = runner.stdout.read() if hasattr(runner.stdout, 'read') else str(runner.stdout)
            PlaybookRun.objects.create(
                playbook=playbook,
                status=runner.status,
                output=output,
                triggered_by=request.user
            )
            logger.debug(f'Playbook {playbook.name} run by {request.user.username}: {output}')
            messages.success(request, f'Playbook {playbook.name} executed.')
            return redirect('log_list')
    return render(request, 'dashboard/home.html', {'playbooks': playbooks})

@login_required
def api_playbook_detail(request, pk):
    playbook = get_object_or_404(Playbook, pk=pk)
    data = {
        'id': playbook.pk,
        'name': playbook.name,
        'git_repo': playbook.git_repo,
        'repo_branch': playbook.repo_branch,
        'project_root': playbook.project_root,
        'modules': playbook.modules,
        'playbook_file': playbook.playbook_file,
        'description': playbook.description,
    }
    return JsonResponse(data)

@login_required
def playbook_list(request):
    playbooks = Playbook.objects.all()
    if request.method == 'POST':
        if 'run_playbook_id' in request.POST:
            playbook_id = request.POST.get('run_playbook_id')
            if playbook_id:
                playbook = get_object_or_404(Playbook, pk=playbook_id)
                import uuid
                import traceback
                artifact_id = str(uuid.uuid4())
                artifact_dir = os.path.abspath(os.path.join('artifacts', artifact_id))
                src_dir = os.path.join(artifact_dir, 'src')
                os.makedirs(src_dir, exist_ok=True)
                run = PlaybookRun.objects.create(
                    playbook=playbook,
                    status='running',
                    output='\x1b[34m[INFO] Cloning git repository...\x1b[0m\n',
                    triggered_by=request.user,
                    artifact_path=src_dir
                )
                def job():
                    try:
                        clone_git_repo(playbook.git_repo, playbook.repo_branch, src_dir, run=run)
                        run.output += '\x1b[34m[INFO] Git clone complete.\n[INFO] Starting Ansible playbook...\x1b[0m\n'
                        run.save()
                        project_dir = os.path.abspath(os.path.join(src_dir, playbook.project_root)) if playbook.project_root else os.path.abspath(src_dir)
                        playbook_path = os.path.abspath(os.path.join(project_dir, playbook.playbook_file))
                        runner_cmd = f'ansible-runner run {artifact_dir} -p {playbook_path} -v'
                        run.ansible_command = runner_cmd
                        run.save()
                        runner = ansible_runner.run(private_data_dir=artifact_dir, playbook=playbook_path, verbosity=4, project_dir=project_dir)
                        output = runner.stdout.read() if hasattr(runner.stdout, 'read') else str(runner.stdout)
                        run.status = runner.status
                        run.output += output
                        run.save()
                        logger.debug(f'Playbook {playbook.name} run by {request.user.username}: {output}')
                    except Exception as e:
                        run.status = 'failed'
                        run.output += f"\n\x1b[31m[ERROR] {str(e)}\x1b[0m\n"
                        run.save()
                # Start the job in a background thread
                Thread(target=job, daemon=True).start()
                # Respond immediately with log info for AJAX/redirect
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/x-www-form-urlencoded':
                    return JsonResponse({'log_id': run.pk, 'log_url': f'/logs/{run.pk}/'})
                messages.success(request, f'Playbook {playbook.name} started.')
                return redirect('log_list')
        else:
            # Save or update playbook
            playbook_id = request.POST.get('playbook_id')
            if playbook_id:
                playbook = get_object_or_404(Playbook, pk=playbook_id)
            else:
                playbook = Playbook()
            playbook.name = request.POST.get('name')
            playbook.git_repo = request.POST.get('git_repo')
            playbook.repo_branch = request.POST.get('repo_branch')
            playbook.project_root = request.POST.get('project_root')
            playbook.modules = request.POST.get('modules')
            playbook.playbook_file = request.POST.get('playbook_file')
            playbook.description = request.POST.get('description')
            playbook.save()
            messages.success(request, f'Playbook "{playbook.name}" saved.')
            return redirect('playbook_list')
    return render(request, 'dashboard/playbook_list.html', {'playbooks': playbooks})

@login_required
@user_passes_test(lambda u: is_admin(u) or is_operator(u))
def run_playbook(request, pk):
    import uuid
    import traceback
    from django.utils import timezone
    playbook = get_object_or_404(Playbook, pk=pk)
    if request.method == 'POST':
        artifact_id = str(uuid.uuid4())
        artifact_dir = os.path.abspath(os.path.join('artifacts', artifact_id))
        src_dir = os.path.join(artifact_dir, 'src')
        os.makedirs(src_dir, exist_ok=True)
        # Create PlaybookRun entry with status 'running' before starting the job
        run = PlaybookRun.objects.create(
            playbook=playbook,
            status='running',
            output='',
            triggered_by=request.user,
            artifact_path='',  # Set after creation
            git_command='',
            git_stdout='',
            git_stderr='',
            ansible_command='',
        )
        # Set artifact_path and save before running git
        run.artifact_path = artifact_dir
        run.save()
        # Open job log file for writing step-by-step logs
        job_log_path = os.path.join(artifact_dir, 'job.log')
        def log_to_file(msg):
            try:
                with open(job_log_path, 'a') as f:
                    f.write(f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
            except Exception:
                pass  # Don't let logging errors break the job
        try:
            log_to_file(f"Job started for playbook '{playbook.name}' (ID: {playbook.id})")
            log_to_file(f"Artifact directory: {artifact_dir}")
            log_to_file(f"Source directory: {src_dir}")
            # --- GIT CLONE ---
            git_cmd = [
                'git', 'clone', '--branch', playbook.repo_branch or 'main', '--single-branch', playbook.git_repo, src_dir
            ]
            run.git_command = ' '.join(git_cmd)
            run.save()
            log_to_file(f"Cloning git repo: {playbook.git_repo} (branch: {playbook.repo_branch or 'main'}) to {src_dir}")
            log_to_file(f"Git command: {' '.join(git_cmd)}")
            git_proc = subprocess.run(git_cmd, capture_output=True, text=True)
            run.git_stdout = git_proc.stdout or ''
            run.git_stderr = git_proc.stderr or ''
            run.save()
            log_to_file(f"Git stdout: {git_proc.stdout.strip()}")
            log_to_file(f"Git stderr: {git_proc.stderr.strip()}")
            if git_proc.returncode != 0:
                log_to_file(f"Git clone failed with return code {git_proc.returncode}")
                run.status = 'failed'
                run.output += f"\n\x1b[31m[ERROR] Git clone failed:\n{git_proc.stderr}\x1b[0m\n"
                run.finished_at = timezone.now()
                run.save()
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/x-www-form-urlencoded':
                    return JsonResponse({'log_id': run.pk, 'log_url': f'/logs/{run.pk}/'})
                messages.error(request, f'Git clone failed: {git_proc.stderr}')
                return redirect('log_list')
            # --- ANSIBLE RUNNER ---
            project_dir = os.path.abspath(os.path.join(src_dir, playbook.project_root)) if playbook.project_root else os.path.abspath(src_dir)
            playbook_path = os.path.abspath(os.path.join(project_dir, playbook.playbook_file))
            ansible_cmd = f"ansible-runner run {artifact_dir} -p {playbook_path} -v -v -v -v --project-dir {project_dir}"
            run.ansible_command = ansible_cmd
            run.save()
            log_to_file(f"Running ansible-runner with playbook: {playbook_path}")
            log_to_file(f"Ansible command: {ansible_cmd}")
            runner = ansible_runner.run(
                private_data_dir=artifact_dir,
                playbook=playbook_path,
                verbosity=4,
                project_dir=project_dir
            )
            # Capture output (stdout is a file-like object or string)
            output = ''
            if hasattr(runner, 'stdout') and hasattr(runner.stdout, 'read'):
                output = runner.stdout.read()
            elif hasattr(runner, 'stdout'):
                output = str(runner.stdout)
            run.status = runner.status or 'unknown'
            run.output += output or ''
            run.finished_at = timezone.now()
            run.save()
            log_to_file(f"Ansible runner finished with status: {run.status}")
        except Exception as e:
            tb = traceback.format_exc()
            run.status = 'failed'
            run.output += f"\n\x1b[31m[ERROR] {str(e)}\x1b[0m\n"
            run.finished_at = timezone.now()
            run.save()
            log_to_file(f"[ERROR] Exception occurred: {str(e)}\n{tb}")
            logger.error(f'Error running playbook {playbook.name}: {e}')
        # If AJAX, return JSON with log id and URL
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/x-www-form-urlencoded':
            return JsonResponse({'log_id': run.pk, 'log_url': f'/logs/{run.pk}/'})
        messages.success(request, f'Playbook {playbook.name} executed.')
        return redirect('log_list')
    return render(request, 'dashboard/run_playbook.html', {'playbook': playbook})

@login_required
def log_list(request):
    logs = PlaybookRun.objects.all().order_by('-started_at')
    status_filter = request.GET.get('status')
    playbook_filter = request.GET.get('playbook')
    if status_filter:
        logs = logs.filter(status=status_filter)
    if playbook_filter:
        logs = logs.filter(playbook__id=playbook_filter)
    return render(request, 'dashboard/log_list.html', {'logs': logs})

@login_required
@user_passes_test(is_admin)
def schedule_playbook(request):
    from django import forms
    from django.forms import ModelForm
    # Intuitive schedule choices
    SCHEDULE_CHOICES = [
        ("once", "Once at a specific date/time"),
        ("daily", "Every day at a specific time"),
        ("weekly", "Every week on specific days at a specific time"),
        ("interval", "Every N minutes/hours"),
    ]
    class IntuitiveScheduleForm(forms.Form):
        playbook = forms.ModelChoiceField(queryset=Playbook.objects.all())
        schedule_type = forms.ChoiceField(choices=SCHEDULE_CHOICES)
        once_datetime = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
        daily_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={'type': 'time'}))
        weekly_days = forms.MultipleChoiceField(
            required=False,
            choices=[('mon','Mon'),('tue','Tue'),('wed','Wed'),('thu','Thu'),('fri','Fri'),('sat','Sat'),('sun','Sun')],
            widget=forms.CheckboxSelectMultiple
        )
        weekly_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={'type': 'time'}))
        interval_value = forms.IntegerField(required=False, min_value=1)
        interval_unit = forms.ChoiceField(required=False, choices=[('minutes','Minutes'),('hours','Hours')])
        enabled = forms.BooleanField(required=False)
    playbooks = Playbook.objects.all()
    tasks = ScheduledTask.objects.select_related('playbook').all().order_by('-id')
    form = IntuitiveScheduleForm()
    # Support GET for editing a scheduled task (for AJAX/flyout)
    if request.method == 'GET' and 'edit_id' in request.GET:
        task = get_object_or_404(ScheduledTask, pk=request.GET['edit_id'])
        sched = json.loads(task.schedule) if task.schedule else {}
        initial = {
            'playbook': task.playbook_id,
            'enabled': task.enabled,
            'schedule_type': sched.get('type', 'once'),
            'once_datetime': sched.get('datetime', None),
            'daily_time': sched.get('time', None),
            'weekly_days': sched.get('days', []),
            'weekly_time': sched.get('time', None),
            'interval_value': sched.get('value', None),
            'interval_unit': sched.get('unit', None),
        }
        form = IntuitiveScheduleForm(initial=initial)
        return render(request, 'dashboard/schedule_list.html', {
            'tasks': tasks,
            'form': form,
            'playbooks': playbooks,
            'edit_id': task.id,
        })
    if request.method == 'POST':
        if 'edit_id' in request.POST:
            # Editing: load the ScheduledTask and populate the form
            task = get_object_or_404(ScheduledTask, pk=request.POST['edit_id'])
            # Parse JSON schedule to fill form fields
            sched = json.loads(task.schedule) if task.schedule else {}
            initial = {
                'playbook': task.playbook_id,
                'enabled': task.enabled,
                'schedule_type': sched.get('type', 'once'),
                'once_datetime': sched.get('datetime', None),
                'daily_time': sched.get('time', None),
                'weekly_days': sched.get('days', []),
                'weekly_time': sched.get('time', None),
                'interval_value': sched.get('value', None),
                'interval_unit': sched.get('unit', None),
            }
            form = IntuitiveScheduleForm(initial=initial)
            return render(request, 'dashboard/schedule_list.html', {
                'tasks': tasks,
                'form': form,
                'playbooks': playbooks,
                'edit_id': task.id,
            })
        form = IntuitiveScheduleForm(request.POST)
        if form.is_valid():
            # Convert intuitive form to a cron string or a JSON schedule for storage
            schedule_type = form.cleaned_data['schedule_type']
            if schedule_type == 'once':
                schedule = json.dumps({'type': 'once', 'datetime': str(form.cleaned_data['once_datetime'])})
            elif schedule_type == 'daily':
                schedule = json.dumps({'type': 'daily', 'time': str(form.cleaned_data['daily_time'])})
            elif schedule_type == 'weekly':
                schedule = json.dumps({'type': 'weekly', 'days': form.cleaned_data['weekly_days'], 'time': str(form.cleaned_data['weekly_time'])})
            elif schedule_type == 'interval':
                schedule = json.dumps({'type': 'interval', 'value': form.cleaned_data['interval_value'], 'unit': form.cleaned_data['interval_unit']})
            else:
                schedule = ''
            ScheduledTask.objects.create(
                playbook=form.cleaned_data['playbook'],
                schedule=schedule,
                created_by=request.user,
                enabled=form.cleaned_data.get('enabled', False)
            )
            messages.success(request, 'Scheduled task saved.')
            return redirect('schedule_playbook')
    return render(request, 'dashboard/schedule_list.html', {
        'tasks': tasks,
        'form': form,
        'playbooks': playbooks,
    })

def not_implemented(request):
    return HttpResponse('<div style="padding:2em;font-size:1.2em;">This feature is not yet implemented.</div>')

@login_required
def log_detail(request, pk):
    log = get_object_or_404(PlaybookRun, pk=pk)
    artifact_path = log.artifact_path or ''
    if request.GET.get('partial') == '1':
        from dashboard.templatetags.role_tags import vt100_to_html
        return JsonResponse({
            'output': vt100_to_html(log.output),
            'status': log.status,
            'finished_at': log.finished_at.strftime('%Y-%m-%d %H:%M:%S') if log.finished_at else '',
            'artifact_path': artifact_path,
        })
    return render(request, 'dashboard/log_detail.html', {'log': log, 'artifact_path': artifact_path})

def clone_git_repo(repo_url, branch, dest_dir, run=None):
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    cmd = ['git', 'clone', '--branch', branch, '--single-branch', repo_url, dest_dir]
    if run is not None:
        run.git_command = " ".join(cmd)
        if run.git_stdout is None:
            run.git_stdout = ''
        if run.git_stderr is None:
            run.git_stderr = ''
        run.save()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if run is not None:
            run.git_stdout += result.stdout or ''
            run.git_stderr += result.stderr or ''
            run.save()
        result.check_returncode()
    except Exception as e:
        if run is not None:
            run.git_stderr = (run.git_stderr or '') + f'\n[ERROR] git failed: {str(e)}\n'
            run.save()
        raise

def logout_view(request):
    """Allow logout via GET and POST, then redirect to login page."""
    logout(request)
    return redirect('login')  # or use your home page name if preferred
