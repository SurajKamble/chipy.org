from __future__ import unicode_literals
import datetime
import string
import random

from django.db import models
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from interval.fields import IntervalField


from chipy_org.libs.models import CommonModel

MAX_LENGTH = 255

MEETING = (
    ('Loop', 'Loop Meeting - 2nd Thursday'),
    ('North', 'North Meeting - 3rd Thursday'),
)


class Venue(CommonModel):

    def __unicode__(self):
        return self.name

    name = models.CharField(max_length=MAX_LENGTH)
    email = models.EmailField(max_length=MAX_LENGTH, blank=True, null=True)
    phone = models.CharField(max_length=MAX_LENGTH, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def get_latitude(self):
        raise NotImplementedError

    def get_longitude(self):
        raise NotImplementedError

    longitude = property(get_longitude)
    latitude = property(get_latitude)

    @property
    def jsonLatLng(self):
        '''
        Use the string returned as args for google.maps.LatLng constructor.
        '''
        if self.latitude is not None and self.longitude is not None:
            return "%.6f,%.6f" % (self.latitude, self.longitude)
        else:
            return None

    directions = models.TextField(blank=True, null=True)
    embed_map = models.TextField(blank=True, null=True)
    link = models.URLField(blank=True, null=True)


class MeetingType(CommonModel):
    """
    This model contains entries for different meeting types.
    Example:
      - SIG Meetings
      - Mentorship Meetings
      - Holiday Party
    """

    subgroup = models.ForeignKey(
        'subgroups.SubGroup', blank=True, null=True,
        help_text='Optional Sub-group (i.e. SIG)')
    name = models.CharField(max_length=64)
    slug = models.SlugField(max_length=64, unique=True)
    description = models.TextField(blank=True, null=True)

    def __unicode__(self):
        return "%s | (%s)" % (self.id, self.name)

    class Meta(object):
        verbose_name = "Meeting Type"
        verbose_name_plural = "Meeting Types"


class Meeting(CommonModel):

    def __unicode__(self):
        if self.where:
            return "%s at %s" % (
                self.when.strftime("%a, %b %d %Y at %I:%M %p"), self.where.name)
        return "%s location TBD" % self.when

    when = models.DateTimeField()
    where = models.ForeignKey(Venue, blank=True, null=True)
    # Used for anonymous access to meeting information like RSVPs
    key = models.CharField(max_length=40, unique=True, blank=True)
    live_stream = models.CharField(max_length=500, null=True, blank=True)
    meetup_id = models.TextField(blank=True, null=True)
    meeting_type = models.ForeignKey(
        MeetingType, blank=True, null=True,
        help_text=("Type of meeting (i.e. SIG Meeting, "
                   "Mentorship Meeting, Startup Row, etc.). "
                   "Leave this empty for the main meeting."))
    description = models.TextField(blank=True, null=True)

    def is_future(self):
        return bool(self.when >= (datetime.datetime.now() - datetime.timedelta(hours=3)))

    def rsvp_user_yes(self):
        raise NotImplementedError

    def rsvp_user_maybe(self):
        raise NotImplementedError

    def number_rsvps(self):
        return self.rsvp_set.exclude(response='N').count()

    def get_absolute_url(self):
        return reverse("meeting", args=[self.id])

    def meetup_url(self):
        return "https://www.meetup.com/_ChiPy_/events/{}/".format(self.meetup_id)


class Presentor(CommonModel):

    def __unicode__(self):
        return "%s | (%s)" % (self.name, self.email)

    user = models.ForeignKey(User, blank=True, null=True)
    name = models.CharField(max_length=MAX_LENGTH)
    email = models.EmailField(max_length=MAX_LENGTH, blank=True, null=True)
    phone = models.CharField(max_length=MAX_LENGTH, blank=True, null=True)
    release = models.BooleanField(default=False)


LICENSE_CHOISES = (
    ('CC BY', 'Creative Commons: Attribution'),
    ('CC BY-SA', 'Creative Commons: Attribution-ShareAlike'),
    ('CC BY-ND', 'Creative Commons: Attribution-NoDerivs'),
    ('CC BY-NC', 'Creative Commons: Attribution-NonCommercial'),
    ('CC BY-NC-SA', 'Creative Commons: Attribution-NonCommercial-ShareAlike'),
    ('CC BY-NC-ND', 'Creative Commons: Attribution-NonCommercial-NoDerivs'),
    ('All Rights Reserved', 'All Rights Reserved')
)

EXPERIENCE_LEVELS = (
    ('novice', 'Novice'),
    ('intermediate', 'Intermediate'),
    ('advanced', 'Advanced'),
)


class TopicsQuerySet(models.QuerySet):

    def active(self):
        return self.filter(approved=True).order_by('start_time')


class Topic(CommonModel):

    def __unicode__(self):
        out = self.title
        if self.presentors.count():
            out += " By: %s" % self.presentors.all()[0].name
        return out

    title = models.CharField(
        max_length=MAX_LENGTH)
    presentors = models.ManyToManyField(
        Presentor, blank=True)
    meeting = models.ForeignKey(
        Meeting, blank=True, null=True, related_name='topics')
    experience_level = models.CharField(
        "Audience Experience Level",
        max_length=15, blank=True, null=True, choices=EXPERIENCE_LEVELS)
    license = models.CharField(
        max_length=50, choices=LICENSE_CHOISES, default='CC BY')
    length = IntervalField(
        format="M", blank=True, null=True)
    embed_video = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    slides_link = models.URLField(blank=True, null=True)
    start_time = models.DateTimeField(blank=True, null=True)
    approved = models.BooleanField(default=False)

    objects = TopicsQuerySet.as_manager()


class RSVP(CommonModel):

    RSVP_CHOICES = (
        ('Y', "Yes"),
        ('N', "No"),
        ('M', "Maybe"),
    )

    user = models.ForeignKey(User, blank=True, null=True)
    name = models.CharField(max_length=MAX_LENGTH, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    meeting = models.ForeignKey(Meeting)
    response = models.CharField(max_length=1, choices=RSVP_CHOICES)
    key = models.CharField(max_length=MAX_LENGTH, blank=True, null=True)
    meetup_user_id = models.IntegerField(blank=True, null=True)
    guests = models.IntegerField(default=0)

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.user and not self.name:
            raise ValidationError('User or Name required')

        # Check uniqueness
        if not self.id:
            if self.user:
                if RSVP.objects.filter(meeting=self.meeting, user=self.user).exists():
                    raise ValidationError('User has already RSVPed for meeting')
            else:
                if RSVP.objects.filter(meeting=self.meeting, name=self.name).exists():
                    raise ValidationError('User has already RSVPed for meeting')

    def save(self, *args, **kwargs):
        self.full_clean()

        # Generate a key for this RSVP
        if not self.key:
            self.key = ''.join(
                random.choice(string.digits + string.ascii_lowercase) for x in range(40))

        return super(RSVP, self).save(*args, **kwargs)

    @property
    def users_name(self):
        if not self.name:
            if self.user.profile.display_name:
                self.name = self.user.profile.display_name
            else:
                self.name = self.user.get_full_name()
        return self.name

    @property
    def users_email(self):
        if self.user:
            return self.user.email
        else:
            return self.email

    @property
    def users_guests(self):
        if self.user:
            return self.user.guests
        else:
            return self.guests

    def __unicode__(self):
        self.users_name
        return "{}: {}".format(self.meeting, self.name)
