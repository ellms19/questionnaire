# Generated by Django 3.0.4 on 2020-03-29 16:52

from django.db import migrations, models
import things.directionOfFile


class Migration(migrations.Migration):

    dependencies = [
        ('things', '0003_auto_20200329_1544'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegForStudent',
            fields=[
                ('id', models.IntegerField(primary_key=True, serialize=False)),
                ('password', models.CharField(max_length=500)),
                ('photo', models.ImageField(blank=True, default='', upload_to=things.directionOfFile.student_photo_upload)),
            ],
        ),
    ]
