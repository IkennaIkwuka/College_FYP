from accounts.decorators import admin_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from .models import AuditLog


@admin_required
def log_list(request):
    logs = AuditLog.objects.select_related("actor").order_by("-created_at")

    action = request.GET.get("action", "").strip()
    query = request.GET.get("q", "").strip()
    if action:
        logs = logs.filter(action=action)
    if query:
        logs = logs.filter(
            Q(actor_username__icontains=query)
            | Q(target_description__icontains=query)
            | Q(reason__icontains=query)
        )

    paginator = Paginator(logs, 25)
    logs = paginator.get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    return render(
        request,
        "audit/log_list.html",
        {
            "logs": logs,
            "query": query,
            "querystring": querystring,
            "actions": AuditLog.ACTION_CHOICES,
            "selected_action": action,
        },
    )
