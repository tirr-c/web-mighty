# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-12-18 21:29
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_auto_20171218_0321'),
    ]

    operations = [
        migrations.AlterField(
            model_name='room',
            name='room_id',
            field=models.CharField(db_index=True, max_length=40, unique=True),
        ),
    ]
