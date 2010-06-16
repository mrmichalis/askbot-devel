import datetime
from django.db import models
from askbot import const
from askbot.models import base
from askbot.models.user import EmailFeedSetting

class VoteManager(models.Manager):
    def get_up_vote_count_from_user(self, user):
        if user is not None:
            return self.filter(user=user, vote=1).count()
        else:
            return 0

    def get_down_vote_count_from_user(self, user):
        if user is not None:
            return self.filter(user=user, vote=-1).count()
        else:
            return 0

    def get_votes_count_today_from_user(self, user):
        if user is not None:
            today = datetime.date.today()
            return self.filter(user=user, voted_at__range=(today, today + datetime.timedelta(1))).count()
        else:
            return 0


class Vote(base.MetaContent, base.UserContent):
    VOTE_UP = +1
    VOTE_DOWN = -1
    VOTE_CHOICES = (
        (VOTE_UP,   u'Up'),
        (VOTE_DOWN, u'Down'),
    )

    vote           = models.SmallIntegerField(choices=VOTE_CHOICES)
    voted_at       = models.DateTimeField(default=datetime.datetime.now)

    objects = VoteManager()

    class Meta(base.MetaContent.Meta):
        unique_together = ('content_type', 'object_id', 'user')
        db_table = u'vote'

    def __unicode__(self):
        return '[%s] voted at %s: %s' %(self.user, self.voted_at, self.vote)

    def is_upvote(self):
        return self.vote == self.VOTE_UP

    def is_downvote(self):
        return self.vote == self.VOTE_DOWN

    def is_opposite(self, vote_type):
        assert(vote_type in (self.VOTE_UP, self.VOTE_DOWN))
        return self.vote != vote_type


class FlaggedItemManager(models.Manager):
    def get_flagged_items_count_today(self, user):
        if user is not None:
            today = datetime.date.today()
            return self.filter(user=user, flagged_at__range=(today, today + datetime.timedelta(1))).count()
        else:
            return 0

class FlaggedItem(base.MetaContent, base.UserContent):
    """A flag on a Question or Answer indicating offensive content."""
    flagged_at     = models.DateTimeField(default=datetime.datetime.now)

    objects = FlaggedItemManager()

    class Meta(base.MetaContent.Meta):
        unique_together = ('content_type', 'object_id', 'user')
        db_table = u'flagged_item'

    def __unicode__(self):
        return '[%s] flagged at %s' %(self.user, self.flagged_at)

class Comment(base.MetaContent, base.UserContent):
    comment = models.CharField(max_length = const.COMMENT_HARD_MAX_LENGTH)
    added_at = models.DateTimeField(default = datetime.datetime.now)
    html = models.CharField(max_length = const.COMMENT_HARD_MAX_LENGTH, default='')

    _urlize = True
    _use_markdown = False

    class Meta(base.MetaContent.Meta):
        ordering = ('-added_at',)
        db_table = u'comment'

    #these two are methods
    parse = base.parse_post_text
    parse_and_save = base.parse_and_save_post

    def get_origin_post(self):
        return self.content_object.get_origin_post()

    #todo: maybe remove this wnen post models are unified
    def get_text(self):
        return self.comment

    def set_text(self, text):
        self.comment = text

    def get_updated_activity_data(self, created = False):
        if self.content_object.__class__.__name__ == 'Question':
            return const.TYPE_ACTIVITY_COMMENT_QUESTION, self
        elif self.content_object.__class__.__name__ == 'Answer':
            return const.TYPE_ACTIVITY_COMMENT_ANSWER, self

    def get_response_receivers(self, exclude_list = None):
        """get list of users who authored comments on a post
        and the post itself
        """
        assert(exclude_list is not None)
        users = set()
        users.update(
                    #get authors of parent object and all associated comments
                    self.content_object.get_author_list(
                            include_comments = True,
                        )
                )
        users -= set(exclude_list)
        return list(users)

    def get_instant_notification_subscribers(
                                    self, 
                                    potential_subscribers = None,
                                    mentioned_users = None,
                                    exclude_list = None
                                ):
        """get list of users who want instant notifications
        about this post

        argument potential_subscribers is required as it saves on db hits
        """

        subscriber_set = set()

        if potential_subscribers:
            potential_subscribers = set(potential_subscribers)
        else:
            potential_subscribers = set()

        if mentioned_users:
            potential_subscribers.update(mentioned_users)

        if potential_subscribers:
            comment_subscribers = EmailFeedSetting.objects.filter(
                                            subscriber__in = potential_subscribers,
                                            feed_type = 'm_and_c',
                                            frequency = 'i'
                                        ).values_list(
                                                'subscriber', 
                                                flat=True
                                        )
            subscriber_set.update(comment_subscribers)

        origin_post = self.get_origin_post()
        selective_subscribers = origin_post.followed_by.all()
        if selective_subscribers:
            selective_subscribers = EmailFeedSetting.objects.filter(
                                                subscriber__in = selective_subscribers,
                                                feed_type = 'q_sel',
                                                frequency = 'i'
                                            ).values_list(
                                                    'subscriber', 
                                                    flat=True
                                            )
            for subscriber in selective_subscribers:
                if origin_post.passes_tag_filter_for_user(subscriber):
                    subscriber_set.add(subscriber)

            subscriber_set.update(selective_subscribers)

        global_subscribers = EmailFeedSetting.objects.filter(
                                            feed_type = 'q_all',
                                            frequency = 'i'
                                        ).values_list(
                                                'subscriber', 
                                                flat=True
                                        )

        subscriber_set.update(global_subscribers)
        if exclude_list:
            subscriber_set -= set(exclude_list)

        return list(subscriber_set)

    def get_time_of_last_edit(self):
        return self.added_at

    def delete(self, **kwargs):
        #todo: not very good import in models of other models
        #todo: potentially a circular import
        from askbot.models.user import Activity
        Activity.objects.get_mentions(
                            mentioned_in = self
                        ).delete()
        super(Comment,self).delete(**kwargs)

    def get_absolute_url(self):
        origin_post = self.get_origin_post()
        return '%s#comment-%d' % (origin_post.get_absolute_url(), self.id)

    def get_latest_revision_number(self):
        return 1

    def __unicode__(self):
        return self.comment
