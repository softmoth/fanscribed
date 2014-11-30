# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'Episode.guid'
        db.alter_column(u'podcasts_episode', 'guid', self.gf('django.db.models.fields.TextField')())

        # Changing field 'Episode.title'
        db.alter_column(u'podcasts_episode', 'title', self.gf('django.db.models.fields.TextField')())

        # Changing field 'Podcast.title'
        db.alter_column(u'podcasts_podcast', 'title', self.gf('django.db.models.fields.TextField')(null=True))

    def backwards(self, orm):

        # Changing field 'Episode.guid'
        db.alter_column(u'podcasts_episode', 'guid', self.gf('django.db.models.fields.CharField')(max_length=200))

        # Changing field 'Episode.title'
        db.alter_column(u'podcasts_episode', 'title', self.gf('django.db.models.fields.CharField')(max_length=200))

        # Changing field 'Podcast.title'
        db.alter_column(u'podcasts_podcast', 'title', self.gf('django.db.models.fields.CharField')(max_length=200, null=True))

    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'podcasts.episode': {
            'Meta': {'ordering': "('-published',)", 'unique_together': "[('podcast', 'guid')]", 'object_name': 'Episode'},
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'external_transcript': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'guid': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'link_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'media_url': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'podcast': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'episodes'", 'to': u"orm['podcasts.Podcast']"}),
            'published': ('django.db.models.fields.DateTimeField', [], {}),
            'title': ('django.db.models.fields.TextField', [], {}),
            'transcript': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'episode'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': u"orm['transcripts.Transcript']", 'blank': 'True', 'unique': 'True'})
        },
        u'podcasts.podcast': {
            'Meta': {'ordering': "('title', 'rss_url')", 'object_name': 'Podcast'},
            'approval_state': ('django_fsm.db.fields.fsmfield.FSMField', [], {'default': "'not_approved'", 'max_length': '50'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'link_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'provides_own_transcripts': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'rss_url': ('django.db.models.fields.URLField', [], {'unique': 'True', 'max_length': '200'}),
            'title': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        u'podcasts.rssfetch': {
            'Meta': {'object_name': 'RssFetch'},
            'body': ('django.db.models.fields.BinaryField', [], {'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'blank': 'True'}),
            'fetched': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'podcast': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'fetches'", 'to': u"orm['podcasts.Podcast']"}),
            'state': ('django_fsm.db.fields.fsmfield.FSMField', [], {'default': "'not_fetched'", 'max_length': '50'})
        },
        u'podcasts.transcriptionapproval': {
            'Meta': {'object_name': 'TranscriptionApproval'},
            'approval_type': ('django.db.models.fields.CharField', [], {'max_length': '5'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'notes': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'podcast': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'approvals'", 'to': u"orm['podcasts.Podcast']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        u'transcripts.transcript': {
            'Meta': {'object_name': 'Transcript'},
            'contributors': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'contributed_to_transcripts'", 'symmetrical': 'False', 'to': u"orm['auth.User']"}),
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'length': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '8', 'decimal_places': '2'}),
            'length_state': ('django_fsm.db.fields.fsmfield.FSMField', [], {'default': "'unset'", 'max_length': '50'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'state': ('django_fsm.db.fields.fsmfield.FSMField', [], {'default': "'unfinished'", 'max_length': '50'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '512'})
        }
    }

    complete_apps = ['podcasts']