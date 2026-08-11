from django.db import migrations

RENAMES = [
    ("Admin", "IT Admin"),
    ("Hod", "HOD"),
]


def rename_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for old_name, new_name in RENAMES:
        group = Group.objects.filter(name=old_name).first()
        if group:
            group.name = new_name
            group.save(update_fields=["name"])
        else:
            Group.objects.get_or_create(name=new_name)


def rename_groups_back(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for old_name, new_name in RENAMES:
        group = Group.objects.filter(name=new_name).first()
        if group:
            group.name = old_name
            group.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_must_change_password"),
    ]

    operations = [
        migrations.RunPython(rename_groups, rename_groups_back),
    ]
