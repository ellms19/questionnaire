# Generated by Django 2.2.5 on 2020-05-03 19:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('things', '0022_cheatingreport_reason'),
    ]

    operations = [
        migrations.AlterField(
            model_name='testresult',
            name='grade',
            field=models.FloatField(null=True),
        ),
        migrations.AlterField(
            model_name='testresult',
            name='submitted_date',
            field=models.DateTimeField(null=True),
        ),
    ]
