from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0002_department_alter_studentprofile_department"),
    ]

    operations = [
        migrations.RenameField(
            model_name="studentprofile",
            old_name="level",
            new_name="entry_level",
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="entry_session",
            field=models.CharField(default="2025/2026", help_text="e.g. 2025/2026", max_length=9),
            preserve_default=False,
        ),
    ]
