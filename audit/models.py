from django.conf import settings
from django.db import models


class AuditLogImmutableError(Exception):
    """Raised by AuditLog.save()/delete() and AuditLogQuerySet.update()/delete()
    when something tries to modify or remove an existing entry. FR-LOG-05 requires
    logs be immutable to every role, including whoever writes code against this
    model later - enforced here, not just by omitting an edit/delete UI.
    """


class AuditLogQuerySet(models.QuerySet):
    # QuerySet.update()/.delete() go straight to SQL and never call an instance's
    # save()/delete() - the two model-level overrides below don't see these at all,
    # so they need their own guard.
    def update(self, **kwargs):
        raise AuditLogImmutableError("Audit log entries cannot be bulk-updated.")

    def delete(self):
        raise AuditLogImmutableError("Audit log entries cannot be bulk-deleted.")


class AuditLog(models.Model):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    ACCESS_DENIED = "ACCESS_DENIED"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    ACTION_CHOICES = [
        (LOGIN_SUCCESS, "Login success"),
        (LOGIN_FAILED, "Login failed"),
        (ACCESS_DENIED, "Access denied"),
        (CREATE, "Create"),
        (UPDATE, "Update"),
        # No call site logs this yet - no .delete() exists anywhere in students/
        # courses/results (soft-disable via Course.is_active is the house style
        # instead). Kept for forward compatibility - costs nothing now, and covers
        # a future hard-delete path or the unbuilt Bursar/Fees app without a
        # migration when one shows up.
        (DELETE, "Delete"),
    ]

    # SET_NULL, not CASCADE/PROTECT: an audit row must outlive the User it names.
    # CASCADE would silently destroy history exactly when it matters most (e.g. a
    # superuser deleting an account that was involved in something worth auditing);
    # PROTECT would block deleting an account for the wrong reason (merely having
    # once logged in). actor_username below is what keeps the row readable once
    # this goes null.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    # Plain-text snapshot, independent of actor - covers cases actor can't: an
    # unknown/mistyped login username (no User row exists to point to at all), an
    # ambiguous username match, and actor's row going null later. Never re-derived
    # from actor after the fact, so a later username change doesn't retroactively
    # rewrite old entries.
    actor_username = models.CharField(max_length=150, blank=True, default="")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    # What was acted on - free text, not a generic FK (ContentType/object_id). The
    # target set here is small and known (StudentProfile, Faculty, Department,
    # Course, CourseRegistration, Result), and a log entry must stay meaningful even
    # after the record it describes changes again or is itself gone.
    target_description = models.CharField(max_length=255, blank=True, default="")
    # PermissionDenied's message text for ACCESS_DENIED, or the specific reason for
    # LOGIN_FAILED (unknown username / wrong password / locked out / inactive /
    # ambiguous match). Blank for CREATE/UPDATE/LOGIN_SUCCESS - nothing to explain.
    reason = models.CharField(max_length=255, blank=True, default="")
    request_path = models.CharField(max_length=255, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} - {self.actor_username or 'unknown'} - {self.created_at:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise AuditLogImmutableError("Audit log entries cannot be modified after creation.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditLogImmutableError("Audit log entries cannot be deleted.")
