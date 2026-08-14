# Generated migration for FileLock and GroupFilePermission models

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('files', '0005_filesystemnode_content'),
        ('accounts', '0003_alter_company_created_by'),
    ]

    operations = [
        migrations.CreateModel(
            name='FileLock',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('locked_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('client_info', models.JSONField(blank=True, default=dict, help_text='Client identifier (hostname, IP, etc.)')),
                ('lock_type', models.CharField(choices=[('exclusive', 'Exclusive Lock'), ('shared', 'Shared Lock')], default='exclusive', max_length=20)),
                ('locked_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='file_locks', to='accounts.user')),
                ('node', models.ForeignKey(limit_choices_to={'node_type': 'file'}, on_delete=django.db.models.deletion.CASCADE, related_name='locks', to='files.filesystemnode')),
            ],
            options={
                'ordering': ['-locked_at'],
                'indexes': [
                    models.Index(fields=['node', 'is_active'], name='files_file_2b8f5a_idx'),
                    models.Index(fields=['locked_by', 'is_active'], name='files_file_5e8f5a_idx'),
                    models.Index(fields=['expires_at'], name='files_file_6e8f5a_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='GroupFilePermission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('permission_mask', models.IntegerField(default=1)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('assigned_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='group_permissions_assigned', to='accounts.user')),
                ('group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='group_file_permissions', to='accounts.department')),
                ('node', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='group_permissions', to='files.filesystemnode')),
            ],
            options={
                'ordering': ['-assigned_at'],
                'indexes': [
                    models.Index(fields=['group', 'node', 'is_active'], name='files_grou_7e8f5a_idx'),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name='filelock',
            constraint=models.UniqueConstraint(condition=models.Q(is_active=True), fields=['node'], name='active_lock_per_file'),
        ),
        migrations.AddConstraint(
            model_name='groupfilepermission',
            constraint=models.UniqueConstraint(fields=['group', 'node'], name='unique_group_node_permission'),
        ),
    ]
