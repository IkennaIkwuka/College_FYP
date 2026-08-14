from django.db import migrations

NEW_ROLE_GROUPS = ["Registrar", "Bursar", "Dean"]


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in NEW_ROLE_GROUPS:
        Group.objects.get_or_create(name=name)


def delete_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=NEW_ROLE_GROUPS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_staffidcounter_user_staff_id"),
    ]

    operations = [
        migrations.RunPython(create_groups, delete_groups),
    ]
