from django.contrib.auth.models import User, Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from allauth.account.models import EmailAddress, EmailConfirmation
from allauth.socialaccount.models import SocialAccount, SocialToken

from ...apps.media.models import MediaFile
from ...apps.media.tests.base import RAW_NOAGENDA_MEDIA_PATH
from ...apps.podcasts.models import Podcast, RssFetch, TranscriptionApproval
from ...apps.transcripts.models import Transcript, TranscriptMedia


class Command(BaseCommand):
    args = '<fixture_name> ...'
    help = "Builds a test data set"

    def handle(self, *args, **options):

        self.verbosity = options.get('verbosity', 0)

        if len(args) == 0:
            self.stdout.write('Available fixtures:')
            for name in sorted(dir(self)):
                if name.startswith('fix_'):
                    method = getattr(self, name)
                    short_name = name[4:]
                    if method.__doc__:
                        self.stdout.write(
                            '- {short_name} ({docstring})'.format(**locals()))
                    else:
                        self.stdout.write('- {short_name}'.format(**locals()))
        else:
            for name in args:
                method_name = 'fix_{name}'.format(**locals())
                method = getattr(self, method_name)
                method()

    def verbose_write(self, str):
        if self.verbosity > 0:
            self.stdout.write(str)

    def fix_demo(self):
        """Demo data: zero su u podcasts"""
        self.fix_zero()
        self.fix_su()
        self.fix_u()
        self.fix_samplepodcasts()
        self.fix_sampletranscript()

    def fix_samplepodcasts(self):
        self.verbose_write('Creating sample podcasts.')
        for rss_url in [
            'http://feed.nashownotes.com/rss.xml',
            'http://lavenderhour.libsyn.com/rss',
            'http://feeds.feedburner.com/matrixmasters/iGAG',
            'http://feeds.twit.tv/twiet.xml',
        ]:
            Podcast.objects.create(rss_url=rss_url)

    def fix_sampletranscript(self):
        self.verbose_write('Creating sample transcript with media.')
        transcript = Transcript.objects.create(
            name='Sample No Agenda Transcript')
        data_url = 'file://{}'.format(RAW_NOAGENDA_MEDIA_PATH)
        media_file = MediaFile.objects.create(data_url=data_url)
        transcript_media = TranscriptMedia.objects.create(
            transcript=transcript,
            media_file=media_file,
            is_processed=False,
            is_full_length=True,
        )
        transcript_media.create_processed()

    def fix_su(self):
        """Create superuser account (creds are su:su)"""
        self.verbose_write('Creating superuser "su".')
        superuser = User.objects.create_superuser(
            'su', 'superuser@example.com', 'su',
            first_name='Super', last_name='User')

    def fix_u(self):
        """Create regular user account (creds are user:password)"""
        self.verbose_write('Creating user "user".')
        user = User.objects.create_user(
            'user', 'user@example.com', 'password',
            first_name='Regular', last_name='User')

    def fix_zero(self):
        """Truncate all database tables; reload initial data."""
        self.verbose_write('Truncating all tables.')
        self._truncate_tables([
            # admin
            'django_admin_log',

            # auth
            User,
            Group,
            'auth_group_permissions',
            'auth_user_groups',
            'auth_user_user_permissions',

            # allauth
            EmailAddress,
            EmailConfirmation,
            SocialAccount,
            SocialToken,
            'account_emailaddress',
            'account_emailconfirmation',

            # waffle
            'waffle_flag_groups',
            'waffle_flag_users',

            # media,
            MediaFile,

            # podcasts,
            Podcast,
            RssFetch,
            TranscriptionApproval,

            # transcripts,
            Transcript,
            TranscriptMedia,
        ])
        call_command('load_initial_data', verbosity=self.verbosity,
                     interactive=False)

    def _table_name(self, model):
        return model if isinstance(model, basestring) else model._meta.db_table

    def _truncate_tables(self, models_to_truncate):
        # http://stackoverflow.com/questions/2988997/
        cursor = connection.cursor()
        tables = [self._table_name(model) for model in models_to_truncate]
        tables_in_quotes = ['"{0}"'.format(table) for table in tables]
        sql = 'TRUNCATE TABLE {0} CASCADE'.format(','.join(tables_in_quotes))
        cursor.execute(sql)
