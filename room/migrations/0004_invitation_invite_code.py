from django.db import migrations, models
import uuid

def gen_uuid(apps, schema_editor):
    Invitation = apps.get_model('room', 'Invitation')
    for row in Invitation.objects.all():
        row.invite_code = uuid.uuid4()
        row.save(update_fields=['invite_code'])

class Migration(migrations.Migration):

    dependencies = [
        ('room', '0003_room_created_at_room_created_by_room_participants_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='invite_code',
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(gen_uuid, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='invitation',
            name='invite_code',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
