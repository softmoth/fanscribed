from django.contrib import admin
from django_object_actions import DjangoObjectActions

from . import models as m


class EpisodeAdmin(DjangoObjectActions, admin.ModelAdmin):

    list_display = ('podcast', 'title', 'published',
                    'transcript', 'external_transcript')
    objectactions = ('use_link_as_external_transcript',)
    ordering = ('podcast', '-published')
    readonly_fields = ('podcast', 'guid', 'published')

    def use_link_as_external_transcript(self, request, obj):
        obj.external_transcript = obj.link_url
        obj.save()
    use_link_as_external_transcript.label = 'Use Link as External Transcript'


# ---


class TranscriptionApprovalInline(admin.StackedInline):

    model = m.TranscriptionApproval
    fields = ('approval_type', 'notes')
    extra = 1


class PodcastAdmin(DjangoObjectActions, admin.ModelAdmin):

    actions = ['fetch']
    fields = ('title', 'link_url', 'rss_url', 'image_url', 'provides_own_transcripts')
    list_display = ('title', 'link_url', 'rss_url')
    objectactions = ('fetch_individual',)

    inlines = [
        TranscriptionApprovalInline,
    ]

    def fetch(self, request, queryset):
        fetched = 0
        for podcast in queryset:
            podcast.fetches.create().start()
            fetched += 1
        message = 'fetched: {fetched}'
        self.message_user(request, message.format(**locals()))
    fetch.short_description = 'Fetch RSS for selected podcasts'

    def fetch_individual(self, request, obj):
        obj.fetches.create().start()
        self.message_user(request, 'RSS fetch started.')
    fetch_individual.label = 'Fetch RSS'


# ---


class RssFetchAdmin(admin.ModelAdmin):

    actions = ['start_fetch']
    list_display = ('podcast', 'fetched', 'state')

    def start_fetch(self, request, queryset):
        started = 0
        could_not_start = 0
        for rss_fetch in queryset:
            if rss_fetch.state == 'not_fetched':
                started += 1
                rss_fetch.start()
            else:
                could_not_start += 1
        message = 'started: {started}, could not start: {could_not_start}'
        self.message_user(request, message.format(**locals()))
    start_fetch.short_description = 'Start selected RSS fetches'


admin.site.register(m.Episode, EpisodeAdmin)
admin.site.register(m.Podcast, PodcastAdmin)
admin.site.register(m.RssFetch, RssFetchAdmin)
