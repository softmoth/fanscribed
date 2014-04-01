from decimal import Decimal

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from model_utils.models import AutoCreatedField, TimeStampedModel

from django_fsm.db.fields import FSMField, transition

from .tasks import create_processed_transcript_media


# ---------------------


class SentenceManager(models.Manager):

    use_for_related_fields = True

    def empty(self):
        return self.filter(state='empty')

    def partial(self):
        return self.filter(state='partial')

    def completed(self):
        return self.filter(state='completed')


class Sentence(models.Model):
    """A sentence made from sentence fragments.

    state
    -----

    @startuml
    [*] --> empty
    empty --> partial
    partial --> completed
    completed --> [*]
    @enduml

    clean_state, boundary_state, speaker_state
    ------------------------------------------

    These are all unprotected fields, and have no transition methods.
    We trust ourselves to change them appropriately instead.

    @startuml
    [*] --> untouched
    untouched --> editing
    editing --> untouched
    editing --> edited
    edited --> reviewing
    reviewing --> edited
    reviewing --> reviewed
    @enduml
    """

    transcript = models.ForeignKey('Transcript', related_name='sentences')
    state = FSMField(default='empty', protected=True)
    clean_state = FSMField(default='untouched')     # Not protected.
    boundary_state = FSMField(default='untouched')  # Not protected.
    speaker_state = FSMField(default='untouched')   # Not protected.
    fragments = models.ManyToManyField(
        'SentenceFragment', related_name='sentences')
    fragment_candidates = models.ManyToManyField(
        'SentenceFragment', related_name='candidate_sentences')
    tf_start = models.ForeignKey('TranscriptFragment')
    tf_sequence = models.PositiveIntegerField()
    latest_text = models.TextField(blank=True, null=True)
    latest_start = models.DecimalField(max_digits=8, decimal_places=2,
                                       blank=True, null=True)
    latest_end = models.DecimalField(max_digits=8, decimal_places=2,
                                     blank=True, null=True)
    latest_speaker = models.ForeignKey('Speaker', blank=True, null=True)

    class Meta:
        ordering = ('tf_start__start', 'tf_sequence')

    objects = SentenceManager()

    @property
    def text(self):
        return u' '.join(fragment.text for fragment in self.fragments.all())

    # --

    @transition(state, ['empty', 'partial'], 'partial', save=True)
    def add_candidates(self, *fragments):
        self.fragment_candidates.add(*fragments)

    @transition(state, 'partial', 'partial', save=True)
    def remove_candidates(self, *fragments):
        self.fragment_candidates.remove(*fragments)

    @transition(state, 'partial', 'partial', save=True)
    def commit_candidates(self, *candidates):
        self.fragments.add(*candidates)
        self.fragment_candidates.remove(*candidates)

    @transition(state, 'partial', 'completed', save=True)
    def complete(self):
        # Set initial latest text and (latest_start, latest_end).
        self.revisions.create(
            sequence=1,
            text=self.text,
        )
        starts = set()
        ends = set()
        for fragment in self.fragments.all():
            transcript_fragment = fragment.revision.fragment
            starts.add(transcript_fragment.start)
            ends.add(transcript_fragment.end)
        self.latest_start = min(starts)
        self.latest_end = max(ends)


# ---------------------


class SentenceFragment(models.Model):
    """A sentence fragment from within a transcript fragment."""

    revision = models.ForeignKey('TranscriptFragmentRevision',
                                 related_name='sentence_fragments')
    sequence = models.PositiveIntegerField()
    text = models.TextField()

    class Meta:
        ordering = ('revision__fragment__start', 'sequence')
        unique_together = [
            ('revision', 'sequence'),
        ]


# ---------------------


class SentenceRevision(models.Model):
    """A full-text revision of a sentence."""

    sentence = models.ForeignKey('Sentence', related_name='revisions')
    sequence = models.PositiveIntegerField()
    editor = models.ForeignKey('auth.User', blank=True, null=True)
    text = models.TextField()

    class Meta:
        ordering = ('sequence',)
        get_latest_by = 'sequence'
        unique_together = [
            ('sentence', 'sequence'),
        ]


@receiver(post_save, sender=SentenceRevision)
def update_sentence_latest_text(instance, created, raw, **kwargs):
    if created and not raw:
        sentence = instance.sentence
        sentence.latest_text = instance.text
        sentence.save()


# ---------------------


class SentenceBoundary(models.Model):
    """A precise start/end boundary of a sentence."""

    sentence = models.ForeignKey('Sentence', related_name='boundaries')
    sequence = models.PositiveIntegerField()
    editor = models.ForeignKey('auth.User')
    start = models.DecimalField(max_digits=8, decimal_places=2)
    end = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        ordering = ('sequence',)
        get_latest_by = 'sequence'
        unique_together = [
            ('sentence', 'sequence'),
        ]


@receiver(post_save, sender=SentenceBoundary)
def update_sentence_latest_boundary(instance, created, raw, **kwargs):
    if created and not raw:
        sentence = instance.sentence
        sentence.latest_start = instance.start
        sentence.latest_end = instance.end
        sentence.save()


# ---------------------


class SentenceSpeaker(models.Model):
    """An assignment of a speaker to a sentence."""

    sentence = models.ForeignKey('Sentence', related_name='speakers')
    sequence = models.PositiveIntegerField()
    editor = models.ForeignKey('auth.User')
    speaker = models.ForeignKey('Speaker')

    class Meta:
        ordering = ('sequence',)
        get_latest_by = 'sequence'
        unique_together = [
            ('sentence', 'sequence'),
        ]


@receiver(post_save, sender=SentenceSpeaker)
def update_sentence_latest_speaker(instance, created, raw, **kwargs):
    if created and not raw:
        sentence = instance.sentence
        sentence.latest_speaker = instance.speaker
        sentence.save()


# ---------------------


class Speaker(models.Model):
    """A unique speaker in the transcript."""

    transcript = models.ForeignKey('Transcript', related_name='speakers')
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = [
            ('transcript', 'name'),
        ]

    def __unicode__(self):
        return self.name


# ---------------------


class TaskManager(models.Manager):

    use_for_related_fields = True

    def presented(self):
        return self.filter(state='presented')

    def valid(self):
        return self.filter(state='valid')

    def invalid(self):
        return self.filter(state='invalid')

    def can_create(self, transcript, is_review):
        """Can we create a new task?

        :ptype transcript: Transcript
        :ptype review: bool
        """
        return False

    def create_next(self, user, transcript, is_review):
        """Create and return the next new task.

        :ptype transcript: Transcript
        :ptype review: bool
        """
        raise Task.DoesNotExist()


class Task(TimeStampedModel):
    """A transcription task to be completed.

    state
    -----

    @startuml

    [*] --> unassigned
    unassigned --> assigned
    assigned --> presented
    presented --> submitted
    submitted --> valid
    valid --> [*]

    submitted --> invalid
    invalid --> presented

    assigned --> expired
    expired --> aborted
    presented --> aborted
    aborted --> [*]

    @enduml
    """

    transcript = models.ForeignKey('Transcript')
    is_review = models.BooleanField()
    state = FSMField(default='unassigned', protected=True)
    assignee = models.ForeignKey('auth.User', blank=True, null=True)

    class Meta:
        abstract = True

    objects = TaskManager()

    def get_absolute_url(self):
        return reverse('transcripts:task_perform', kwargs=dict(
            transcript_pk=self.transcript.pk,
            type=self.TASK_TYPE,
            pk=self.pk,
        ))

    @transition(state, 'unassigned', 'assigned', save=True)
    def assign_to(self, user):
        self.assignee = user
        self._assign_to()

    def _assign_to(self):
        raise NotImplementedError()

    @transition(state, 'assigned', 'presented', save=True)
    def present(self):
        pass

    @transition(state, 'presented', 'submitted', save=True)
    def submit(self):
        if not settings.TESTING:
            self._finish_submit()

    def _finish_submit(self):
        raise NotImplementedError()

    @transition(state, 'submitted', 'valid', save=True)
    def validate(self):
        self._validate()

    def _validate(self):
        raise NotImplementedError()

    @transition(state, 'submitted', 'invalid', save=True)
    def invalidate(self):
        self._invalidate()

    def _invalidate(self):
        raise NotImplementedError()


# ---------------------


class TranscribeTaskManager(TaskManager):

    def _available_fragments(self, transcript, is_review):
        if not is_review:
            return transcript.fragments.filter(
                state='empty',
                lock_state='unlocked',
            )
        else:
            return transcript.fragments.filter(
                state='transcribed',
                lock_state='unlocked',
            )

    def can_create(self, transcript, is_review):
        return bool(self._available_fragments(transcript, is_review).count())

    def create_next(self, user, transcript, is_review):
        fragment = self._available_fragments(transcript, is_review).first()
        if not is_review:
            next = fragment.revisions.create(sequence=1, editor=user)
            text = ''
        else:
            latest = fragment.revisions.latest()
            text = latest.text
            next = fragment.revisions.create(sequence=latest.sequence + 1,
                                             editor=user)
        task = transcript.transcribetask_set.create(
            is_review=is_review,
            revision=next,
            start=fragment.start,
            end=fragment.end,
            text=text,
        )
        task.assign_to(user)
        return task


class TranscribeTask(Task):

    TASK_TYPE = 'transcribe'

    revision = models.ForeignKey('TranscriptFragmentRevision',
                                 blank=True, null=True)
    text = models.TextField(blank=True, null=True)
    # Keep start and end even if `revision` goes away.
    start = models.DecimalField(max_digits=8, decimal_places=2)
    end = models.DecimalField(max_digits=8, decimal_places=2)

    objects = TranscribeTaskManager()

    def _assign_to(self):
        self.revision.fragment.lock()

    def _finish_submit(self):
        from .tasks import process_transcribe_task
        result = process_transcribe_task.delay(self.pk)

    def _validate(self):
        self.revision.fragment.unlock()

    def _invalidate(self):
        fragment = self.revision.fragment
        self.revision.delete()
        self.revision = None
        fragment.unlock()


# ---------------------


class StitchTaskManager(TaskManager):

    def _available_neighbors(self, transcript, is_review):
        if not is_review:
            candidates = transcript.fragments.filter(
                state='transcript_reviewed',
                lock_state='unlocked',
                stitched_right=False,
            )
        else:
            candidates = transcript.fragments.filter(
                state__in=['transcript_reviewed', 'stitched'],
                lock_state='unlocked',
                stitched_right=True,
            )
        if candidates.count() == 0:
            raise TranscriptFragment.DoesNotExist()
        for left in candidates:
            try:
                if not is_review:
                    right = transcript.fragments.get(
                        start=left.end,
                        state='transcript_reviewed',
                        stitched_left=False,
                        lock_state='unlocked',
                    )
                else:
                    right = transcript.fragments.get(
                        start=left.end,
                        state__in=['transcript_reviewed', 'stitched'],
                        stitched_left=True,
                        lock_state='unlocked',
                    )
            except TranscriptFragment.DoesNotExist:
                # No neighbor; keep trying.
                pass
            else:
                # Found our match.
                break
        else:
            raise TranscriptFragment.DoesNotExist()
        return left, right

    def can_create(self, transcript, is_review):
        try:
            self._available_neighbors(transcript, is_review)
        except TranscriptFragment.DoesNotExist:
            return False
        else:
            return True

    def create_next(self, user, transcript, is_review):
        left, right = self._available_neighbors(transcript, is_review)
        task = StitchTask.objects.create(
            transcript=transcript,
            is_review=is_review,
            left=left.revisions.latest(),
            right=right.revisions.latest(),
        )
        if is_review:
            task.create_pairings_from_existing_candidates()
        task.assign_to(user)
        return task


class StitchTask(Task):

    TASK_TYPE = 'stitch'

    left = models.ForeignKey('TranscriptFragmentRevision', related_name='+')
    right = models.ForeignKey('TranscriptFragmentRevision', related_name='+')

    objects = StitchTaskManager()

    def _assign_to(self):
        self.left.fragment.lock()
        self.right.fragment.lock()

    def _finish_submit(self):
        from .tasks import process_stitch_task
        process_stitch_task.delay(self.pk)

    def _validate(self):
        self.left.fragment.unlock()
        self.right.fragment.unlock()

    def _invalidate(self):
        self.left.fragment.unlock()
        self.right.fragment.unlock()

    def create_pairings_from_existing_candidates(self):
        # Create StitchTaskPairings based on existing candidate pairings.
        for left_fragment in self.left.sentence_fragments.all():
            for left_sentence in left_fragment.candidate_sentences.all():
                left_sentence_fragment = None
                right_sentence_fragment = None
                for candidate in left_sentence.fragment_candidates.all():
                    if candidate.revision == self.left:
                        left_sentence_fragment = candidate
                    if candidate.revision == self.right:
                        right_sentence_fragment = candidate
                if (left_sentence_fragment is not None
                    and right_sentence_fragment is not None
                ):
                    self.task_pairings.create(
                        left=left_sentence_fragment,
                        right=right_sentence_fragment,
                    )


class StitchTaskPairing(models.Model):

    task = models.ForeignKey('StitchTask', related_name='task_pairings')
    left = models.ForeignKey('SentenceFragment', related_name='+')
    right = models.ForeignKey('SentenceFragment', related_name='+')

    class Meta:
        ordering = ('left__revision__fragment__start', 'left__sequence')
        unique_together = [
            ('task', 'left',),
        ]


# ---------------------


class CleanTaskManager(TaskManager):

    def _available_sentences(self, transcript, is_review):
        if not is_review:
            return transcript.sentences.filter(
                state='completed',
                clean_state='untouched',
            )
        else:
            return transcript.sentences.filter(
                state='completed',
                clean_state='edited',
            )

    def can_create(self, transcript, is_review):
        return bool(self._available_sentences(transcript, is_review).count())

    def create_next(self, user, transcript, is_review):
        sentence = self._available_sentences(transcript, is_review).first()
        task = transcript.cleantask_set.create(
            is_review=is_review,
            sentence=sentence,
            text=sentence.latest_text,
        )
        task.assign_to(user)
        return task


class CleanTask(Task):

    TASK_TYPE = 'clean'

    sentence = models.ForeignKey('Sentence')
    text = models.TextField()

    objects = CleanTaskManager()

    def _assign_to(self):
        if not self.is_review:
            self.sentence.clean_state = 'editing'
        else:
            self.sentence.clean_state = 'reviewing'
        self.sentence.save()

    def _finish_submit(self):
        from .tasks import process_clean_task
        process_clean_task.delay(self.pk)

    def _validate(self):
        if not self.is_review:
            self.sentence.clean_state = 'edited'
        else:
            latest, previous = self.sentence.revisions.order_by('-sequence')[:2]
            if latest.text.strip() == previous.text.strip():
                self.sentence.clean_state = 'reviewed'
            else:
                self.sentence.clean_state = 'edited'
        self.sentence.save()

    def _invalidate(self):
        if not self.is_review:
            self.sentence.clean_state = 'untouched'
        else:
            self.sentence.clean_state = 'edited'
        self.sentence.save()


# ---------------------


class BoundaryTaskManager(TaskManager):

    def _available_sentences(self, transcript, is_review):
        if not is_review:
            return transcript.sentences.filter(
                state='completed',
                boundary_state='untouched',
            )
        else:
            return transcript.sentences.filter(
                state='completed',
                boundary_state='edited',
            )

    def can_create(self, transcript, is_review):
        return bool(self._available_sentences(transcript, is_review).count())

    def create_next(self, user, transcript, is_review):
        sentence = self._available_sentences(transcript, is_review).first()
        task = transcript.boundarytask_set.create(
            is_review=is_review,
            sentence=sentence,
            start=sentence.latest_start,
            end=sentence.latest_end,
        )
        task.assign_to(user)
        return task


class BoundaryTask(Task):

    TASK_TYPE = 'boundary'

    sentence = models.ForeignKey('Sentence')
    start = models.DecimalField(max_digits=8, decimal_places=2)
    end = models.DecimalField(max_digits=8, decimal_places=2)

    objects = BoundaryTaskManager()

    def _assign_to(self):
        if not self.is_review:
            self.sentence.boundary_state = 'editing'
        else:
            self.sentence.boundary_state = 'reviewing'
        self.sentence.save()

    def _finish_submit(self):
        from .tasks import process_boundary_task
        process_boundary_task.delay(self.pk)

    def _validate(self):
        if not self.is_review:
            self.sentence.boundary_state = 'edited'
        else:
            latest, previous = self.sentence.boundaries.order_by('-sequence')[:2]
            if (latest.start, latest.end) == (previous.start, previous.end):
                self.sentence.boundary_state = 'reviewed'
            else:
                self.sentence.boundary_state = 'edited'
        self.sentence.save()

    def _invalidate(self):
        if not self.is_review:
            self.sentence.boundary_state = 'untouched'
        else:
            self.sentence.boundary_state = 'edited'
        self.sentence.save()


# ---------------------


class SpeakerTaskManager(TaskManager):

    def _available_sentences(self, transcript, is_review):
        if not is_review:
            return transcript.sentences.filter(
                state='completed',
                speaker_state='untouched',
            )
        else:
            return transcript.sentences.filter(
                state='completed',
                speaker_state='edited',
            )

    def can_create(self, transcript, is_review):
        return bool(self._available_sentences(transcript, is_review).count())

    def create_next(self, user, transcript, is_review):
        sentence = self._available_sentences(transcript, is_review).first()
        task = transcript.speakertask_set.create(
            is_review=is_review,
            sentence=sentence,
            speaker=sentence.latest_speaker,
        )
        task.assign_to(user)
        return task


class SpeakerTask(Task):

    TASK_TYPE = 'speaker'

    sentence = models.ForeignKey('Sentence')
    speaker = models.ForeignKey('Speaker', blank=True, null=True)
    new_name = models.CharField(max_length=100, blank=True, null=True)

    objects = SpeakerTaskManager()

    def _assign_to(self):
        if not self.is_review:
            self.sentence.speaker_state = 'editing'
        else:
            self.sentence.speaker_state = 'reviewing'
        self.sentence.save()

    def _finish_submit(self):
        from .tasks import process_speaker_task
        process_speaker_task.delay(self.pk)

    def _validate(self):
        if not self.is_review:
            self.sentence.speaker_state = 'edited'
        else:
            latest, previous = self.sentence.speakers.order_by('-sequence')[:2]
            if latest.speaker == previous.speaker:
                self.sentence.speaker_state = 'reviewed'
            else:
                self.sentence.speaker_state = 'edited'
        self.sentence.save()

    def _invalidate(self):
        if not self.is_review:
            self.sentence.speaker_state = 'untouched'
        else:
            self.sentence.speaker_state = 'edited'
        self.sentence.save()


# ---------------------


# Mapping of task types to model classes
TASK_MODEL = {
    # task_type: model_class,
    'transcribe': TranscribeTask,
    'stitch': StitchTask,
    'clean': CleanTask,
    'boundary': BoundaryTask,
    'speaker': SpeakerTask,
}


# ---------------------


class Transcript(TimeStampedModel):
    """A transcript of audio or video to text.

    length_state
    ------------

    @startuml
    [*] --> unset
    unset --> set
    set --> [*]
    @enduml
    """

    name = models.CharField(max_length=512)  # TODO: change to `title`
    length = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    length_state = FSMField(default='unset', protected=True)

    def __unicode__(self):
        return self.name

    def has_full_length_processed_media(self):
        return TranscriptMedia.objects.filter(
            transcript=self,
            is_processed=True,
            is_full_length=True,
        ).exists()

    @transition(length_state, 'unset', 'set', save=True)
    def set_length(self, length):
        self.length = Decimal(length)
        self._create_fragments()

    def _create_fragments(self):  # TODO: unit test
        start = Decimal('0')
        while start < self.length:

            # Find the end of the current fragment.
            # If remaining time is less than fragment length, stretch to end.
            end = start + settings.TRANSCRIPT_FRAGMENT_LENGTH
            remaining = self.length - end
            if remaining < settings.TRANSCRIPT_FRAGMENT_LENGTH:
                end = self.length

            self.fragments.create(
                start=start,
                end=end,
                # First and last fragments are 'stitched' to each end. :)
                stitched_left=True if start == Decimal('0') else False,
                stitched_right=True if end == self.length else False,
            )

            start = end


# ---------------------


class TranscriptFragmentManager(models.Manager):

    use_for_related_fields = True

    def empty(self):
        return self.filter(state='empty')

    def transcribed(self):
        return self.filter(state='transcribed')

    def transcript_reviewed(self):
        return self.filter(state='transcript_reviewed')

    def stitched(self):
        return self.filter(state='stitched')

    def stitch_reviewed(self):
        return self.filter(state='stitch_reviewed')

    def locked(self):
        return self.filter(lock_state='locked')

    def unlocked(self):
        return self.filter(lock_state='unlocked')


class TranscriptFragment(models.Model):
    """A fragment of a transcript defined by its time span.

    state
    -----

    @startuml
    [*] --> empty
    empty --> transcribed
    transcribed --> transcript_reviewed
    transcript_reviewed --> stitched
    stitched --> stitch_reviewed
    stitch_reviewed --> [*]
    @enduml

    lock_state
    ------------

    @startuml
    [*] --> unlocked
    unlocked --> locked
    locked --> unlocked
    @enduml
    """

    transcript = models.ForeignKey('Transcript', related_name='fragments')
    start = models.DecimalField(max_digits=8, decimal_places=2)
    end = models.DecimalField(max_digits=8, decimal_places=2)
    stitched_left = models.BooleanField(default=False)
    stitched_right = models.BooleanField(default=False)
    state = FSMField(default='empty', protected=True)
    lock_state = FSMField(default='unlocked', protected=True)

    objects = TranscriptFragmentManager()

    class Meta:
        ordering = ('start',)
        unique_together = [
            ('transcript', 'start', 'end'),
        ]

    def stitched_both_sides(self):
        return self.stitched_left and self.stitched_right

    @transition(lock_state, 'unlocked', 'locked', save=True)
    def lock(self):
        pass

    @transition(lock_state, 'locked', 'unlocked', save=True)
    def unlock(self):
        pass

    @transition(state, 'empty', 'transcribed', save=True)
    def transcribe(self):
        pass

    @transition(state, 'transcribed', 'transcript_reviewed', save=True)
    def review_transcript(self):
        pass

    @transition(state, 'transcript_reviewed', 'stitched', save=True,
                conditions=[stitched_both_sides])
    def stitch(self):
        pass

    @transition(state, 'stitched', 'stitch_reviewed', save=True,
                conditions=[stitched_both_sides])
    def review_stitch(self):
        self._merge_sentences()
        self._complete_sentences()

    def _merge_sentences(self):
        """Merge overlapping Sentence instances."""
        latest_revision = self.revisions.latest()
        deletion_candidates = []
        for sf in latest_revision.sentence_fragments.all():
            sentences = sf.sentences
            candidate_sentences = sf.candidate_sentences
            if sentences.count() > 1 or candidate_sentences.count() > 1:
                # This fragment is in more than one sentence.
                # Pick the first sentence selected as the survivor.
                if sentences:
                    survivor = sentences.first()
                else:
                    survivor = candidate_sentences.first()

                def merge(s, o):
                    # TODO: investigate why 'other' is sometimes none.
                    if o is not None:
                        s.fragments.add(*o.fragments.all())
                        s.fragment_candidates.add(
                            *o.fragment_candidates.all())
                        o.delete()

                for other in sentences.all():
                    if other != survivor:
                        merge(survivor, other)

                for other in candidate_sentences.all():
                    if other != survivor:
                        merge(survivor, other)

    def _complete_sentences(self):
        """Complete sentences in this fragment as applicable."""
        latest = self.revisions.latest()
        for candidate_sf in latest.sentence_fragments.all():
            for sentence in candidate_sf.sentences.filter(state='partial'):
                if sentence.fragment_candidates.count() > 0:
                    # The sentence is still being worked on.
                    continue
                if all(
                    other_sf.revision.fragment.state == 'stitch_reviewed'
                    for other_sf in sentence.fragments.all()
                    if other_sf != candidate_sf
                ):
                    sentence.complete()


# ---------------------


class TranscriptFragmentRevision(TimeStampedModel):
    """A revision of a TranscriptFragment."""

    fragment = models.ForeignKey('TranscriptFragment', related_name='revisions')
    sequence = models.PositiveIntegerField()
    editor = models.ForeignKey('auth.User')

    class Meta:
        get_latest_by = 'sequence'
        ordering = ('sequence',)
        unique_together = [
            ('fragment', 'sequence'),
        ]

    @property
    def text(self):
        return '\n\n'.join(
            sf.text for sf in self.sentence_fragments.all())


# ---------------------


class TranscriptMedia(models.Model):

    # TODO: state machine around conversion process

    transcript = models.ForeignKey('Transcript')
    media_file = models.ForeignKey('media.MediaFile')
    is_processed = models.BooleanField(help_text='Is it processed media?')
    is_full_length = models.BooleanField(
        help_text='Is it the full length of media to be transcribed?')
    created = AutoCreatedField()
    start = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    end = models.DecimalField(max_digits=8, decimal_places=2, null=True)

    class Meta:
        unique_together = (
            'transcript',
            'is_processed',
            'is_full_length',
            'start',
            'end',
        )

    def __unicode__(self):
        if self.is_processed:
            return u'Processed media for {self.transcript}'.format(**locals())
        else:
            return u'Raw media for {self.transcript}'.format(**locals())

    def create_processed(self):
        create_processed_transcript_media.delay(self.pk)
