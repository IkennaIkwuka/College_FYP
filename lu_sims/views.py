from accounts import views as accounts_views
from django.contrib.auth.decorators import login_required
from students import views as students_views


# Thin role dispatchers for the shared, role-neutral /profile/ and /profile/edit/
# URLs (mirrors ec4631b's /login/ and /dashboard/ move - the URL itself shouldn't
# reveal what kind of account you're looking at). Live here rather than in
# accounts.views because students depends on accounts, never the reverse -
# accounts can't import students.views itself, but the project's own URL
# composition layer is free to depend on both.


@login_required
def profile(request):
    if request.user.is_student:
        return students_views.my_profile(request)
    return accounts_views.profile(request)


@login_required
def profile_edit(request):
    if request.user.is_student:
        return students_views.my_profile_edit(request)
    return accounts_views.profile_edit(request)
