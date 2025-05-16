# Ansible Administration Dashboard

This Django application provides an admin dashboard for scheduling and running Ansible playbooks using ansible-runner. It supports user authentication, role-based access (admin, operator, viewer), log filtering, and extremely verbose output logging.

## Features
- Schedule Ansible playbooks to run at specific times (via django-crontab)
- Run playbooks with extremely verbose output (verbosity=4)
- Log all playbook runs and filter logs by status/playbook
- User authentication and roles:
  - **Admin**: Full access
  - **Operator**: Can run specific playbooks
  - **Viewer**: Can only view results

## Setup
1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Run migrations:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
3. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```
4. Start the development server:
   ```bash
   python manage.py runserver
   ```

## Usage
- Access the dashboard at http://localhost:8000/
- Use the Django admin at http://localhost:8000/admin/ to manage users, roles, and playbooks.

## Notes
- Playbook scheduling UI is a placeholder; cron jobs can be managed via django-crontab.
- All playbook runs are logged with full output for auditing and filtering.
# AnsibleView
