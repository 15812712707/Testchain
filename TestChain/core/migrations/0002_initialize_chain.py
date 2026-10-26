from django.db import migrations


def initialize_chain(apps, schema_editor):
    apps.get_model("core", "ChainState").objects.using(schema_editor.connection.alias).get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(initialize_chain, migrations.RunPython.noop)]
