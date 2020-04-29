# Generated by Django 2.2.5 on 2020-04-17 18:27

from django.db import migrations


def link_artists(apps, schema_editor):
    Student = apps.get_model('things', 'Student')
    Speciality = apps.get_model('things', 'Speciality')
    for student in Student.objects.all():
        speciality, created = Speciality.objects.get_or_create(title=student.speciality)
        student.speciality_fk = speciality
        student.save()


class Migration(migrations.Migration):

    dependencies = [
        ('things', '0012_auto_20200418_0026'),
    ]

    operations = [
    ]