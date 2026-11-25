from django import template

from litigant_portal.app.topic_flow.formatting import format_answer

register = template.Library()
register.filter("display_answer", format_answer)
