import re
from django.utils.safestring import mark_safe
from django import template

register = template.Library()

@register.filter
def has_role(user, role_name):
    return user.is_authenticated and user.role_set.filter(name=role_name).exists()

def vt100_to_html(value):
    # Map VT100 color codes to CSS styles
    color_map = {
        '30': 'color:#808080;',  # Black (render as middle gray for dark bg)
        '31': 'color:#d16969;',  # Red
        '32': 'color:#6a9955;',  # Green
        '33': 'color:#d7ba7d;',  # Yellow
        '34': 'color:#569cd6;',  # Blue
        '35': 'color:#c586c0;',  # Magenta
        '36': 'color:#4ec9b0;',  # Cyan
        '37': 'color:#d4d4d4;',  # White
        '90': 'color:#808080;',  # Bright Black (Gray)
        '91': 'color:#f44747;',  # Bright Red
        '92': 'color:#b5cea8;',  # Bright Green
        '93': 'color:#fffb8f;',  # Bright Yellow
        '94': 'color:#9cdcfe;',  # Bright Blue
        '95': 'color:#d7ba7d;',  # Bright Magenta
        '96': 'color:#4ec9b0;',  # Bright Cyan
        '97': 'color:#ffffff;',  # Bright White
        '0': '',  # Reset
    }
    # Regex to match VT100 color codes
    pattern = re.compile(r'\x1b\[([0-9;]+)m')
    parts = pattern.split(value)
    result = []
    current_style = ''
    for i, part in enumerate(parts):
        if i % 2 == 0:
            # Text part
            if current_style:
                result.append(f'<span style="{current_style}">{part}</span>')
            else:
                result.append(part)
        else:
            # Attribute part
            attrs = part.split(';')
            styles = []
            for attr in attrs:
                if attr in color_map:
                    styles.append(color_map[attr])
                elif attr == '1':
                    styles.append('font-weight:bold;')
            current_style = ''.join(styles)
    return mark_safe(''.join(result))

register.filter('vt100_to_html', vt100_to_html)
