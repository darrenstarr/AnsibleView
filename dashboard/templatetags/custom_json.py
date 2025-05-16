import json
from django import template
register = template.Library()

@register.filter
def from_json(value):
    try:
        return json.loads(value)
    except Exception:
        return {}
