from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def abs_value(value):
    try:
        return abs(value)
    except (TypeError, ValueError):
        return value

@register.filter
def percentage(value, total):
    try:
        if float(total) == 0:
            return 0
        return round(float(value) / float(total) * 100, 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0

@register.filter
def get_field(form, key):
    """Return a BoundField: {{ form|get_field:'date' }} → form['map_date']"""
    return form[f'map_{key}']

@register.filter
def get_field_widget(form, key):
    """Render widget HTML: {{ form|get_field_widget:'date' }}"""
    return mark_safe(str(form[f'map_{key}']))

@register.filter
def split(value, delimiter=','):
    """Split a string: {{ '10,25,50'|split:',' }}"""
    return value.split(delimiter)
