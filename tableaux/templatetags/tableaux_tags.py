from django import template

register = template.Library()


@register.filter
def milliers(n):
    """3000 -> « 3 000 » (espace fine insécable, typographie française)."""
    try:
        return f"{int(n):,}".replace(",", " ")
    except (TypeError, ValueError):
        return n
