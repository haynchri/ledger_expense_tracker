from django import template

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
