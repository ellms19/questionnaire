# Generated by Django 3.0.4 on 2020-04-06 03:35

from django.db import migrations, models
import things.directionOfFile


class Migration(migrations.Migration):

    dependencies = [
        ('things', '0004_regforstudent'),
    ]

    operations = [
        migrations.DeleteModel(
            name='RegForStudent',
        ),
        migrations.AddField(
            model_name='student',
            name='photo',
            field=models.ImageField(blank=True, default='', upload_to=things.directionOfFile.student_photo_upload),
        ),
    ]
