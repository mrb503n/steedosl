# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import random

from django.db import models as m, transaction
from django.utils import timezone
from django.utils.translation import ugettext as _

from ..exceptions import MessageHandleError
from . import WeChatApp


class MessageHandlerManager(m.Manager):
    def create_handler(self, rules=None, replies=None, **kwargs):
        """:rtype: wechat_django.models.MessageHandler"""
        handler = self.create(**kwargs)
        if rules:
            for rule in rules:
                rule.handler = handler
            handler.rules.bulk_create(rules)
        if replies:
            for reply in replies:
                reply.handler = handler
            handler.replies.bulk_create(replies)
        return handler


class MessageHandler(m.Model):
    class Source(object):
        SELF = 0  # 自己的后台
        MENU = 1  # 菜单
        MP = 2  # 微信后台

    class ReplyStrategy(object):
        ALL = "reply_all"
        RANDOM = "random_one"
        NONE = "none"

    class EventType(object):
        SUBSCRIBE = "subscribe"
        UNSUBSCRIBE = "unsubscribe"
        SCAN = "SCAN"
        LOCATION = "LOCATION"
        CLICK = "CLICK"
        VIEW = "VIEW"

    app = m.ForeignKey(
        WeChatApp, on_delete=m.CASCADE, related_name="message_handlers",
        null=False, editable=False)
    name = m.CharField(_("name"), max_length=60)
    src = m.PositiveSmallIntegerField(choices=(
        (Source.MP, "wechat"),
        (Source.SELF, "self"),
        (Source.MENU, "menu")
    ), default=Source.SELF, editable=False)
    strategy = m.CharField(_("strategy"), max_length=10, choices=(
        (ReplyStrategy.ALL, "reply_all"),
        (ReplyStrategy.RANDOM, "random_one"),
        (ReplyStrategy.NONE, "none")
    ), default=ReplyStrategy.ALL)
    log = m.BooleanField(_("log"), default=False)

    starts = m.DateTimeField(_("starts"), null=True, blank=True)
    ends = m.DateTimeField(_("ends"), null=True, blank=True)
    enabled = m.BooleanField(_("enabled"), null=False, default=True)

    weight = m.IntegerField(_("weight"), default=0, null=False)
    created_at = m.DateTimeField(_("created_at"), auto_now_add=True)
    updated_at = m.DateTimeField(_("updated_at"), auto_now=True)

    objects = MessageHandlerManager()

    class Meta:
        ordering = ("-weight", "-created_at", "-id")
        index_together = (
            ("app", "weight", "created_at"),
        )

    def available(self):
        if not self.enabled:
            return False
        now = timezone.now()
        if self.starts and self.starts > now:
            return False
        if self.ends and self.ends < now:
            return False
        return True
    available.short_description = _("available")
    available.boolean = True

    @staticmethod
    def matches(message_info):
        """
        :type message_info: wechat_django.models.WeChatMessageInfo
        """
        handlers = message_info.app.message_handlers\
            .prefetch_related("rules").all()
        for handler in handlers:
            if handler.is_match(message_info):
                return (handler, )

    def is_match(self, message_info):
        if self.available():
            for rule in self.rules.all():
                if rule.match(message_info):
                    return self

    def reply(self, message_info):
        """
        :type message: wechatpy.messages.BaseMessage
        :rtype: wechatpy.replies.BaseReply
        """
        reply = ""
        if self.strategy == self.ReplyStrategy.NONE:
            pass
        else:
            replies = list(self.replies.all())
            if not replies:
                pass
            elif self.strategy == self.ReplyStrategy.ALL:
                for reply in replies[1:]:
                    # TODO: 异常处理
                    reply.send(message_info)
                reply = replies[0]
            elif self.strategy == self.ReplyStrategy.RANDOM:
                reply = random.choice(replies)
            else:
                raise MessageHandleError("incorrect reply strategy")
        return reply and reply.reply(message_info)

    @classmethod
    def sync(cls, app):
        from . import Reply, Rule
        resp = app.client.message.get_autoreply_info()

        # 处理自动回复
        handlers = []

        # 成功后移除之前的自动回复并保存新加入的自动回复
        with transaction.atomic():
            app.message_handlers.filter(
                src=MessageHandler.Source.MP
            ).delete()

            if resp.get("message_default_autoreply_info"):
                # 自动回复
                handler = cls.objects.create_handler(
                    app=app,
                    name="微信配置自动回复",
                    src=MessageHandler.Source.MP,
                    enabled=bool(resp.get("is_autoreply_open")),
                    created=timezone.datetime.fromtimestamp(0),
                    rules=[Rule(type=Rule.Type.ALL)],
                    replies=[
                        Reply.from_mp(
                            resp["message_default_autoreply_info"], app)
                    ]
                )
                handlers.append(handler)

            if resp.get("add_friend_autoreply_info"):
                # 关注回复
                handler = cls.objects.create_handler(
                    app=app,
                    name="微信配置关注回复",
                    src=MessageHandler.Source.MP,
                    enabled=bool(resp.get("is_add_friend_reply_open")),
                    created=timezone.datetime.fromtimestamp(0),
                    rules=[Rule(
                        type=Rule.Type.EVENT,
                        event=cls.EventType.SUBSCRIBE
                    )],
                    replies=[
                        Reply.from_mp(resp["add_friend_autoreply_info"], app)
                    ]
                )
                handlers.append(handler)

            if (resp.get("keyword_autoreply_info")
                and resp["keyword_autoreply_info"].get("list")):
                handlers_list = resp["keyword_autoreply_info"]["list"][::-1]
                handlers.extend(
                    MessageHandler.from_mp(handler, app)
                    for handler in handlers_list
                )
            return handlers

    @classmethod
    def from_mp(cls, handler, app):
        return cls.objects.create_handler(
            app=app,
            name=handler["rule_name"],
            src=MessageHandler.Source.MP,
            created=timezone.datetime.fromtimestamp(handler["create_time"]),
            strategy=handler["reply_mode"],
            rules=[
                Rule.from_mp(rule)
                for rule in handler["keyword_list_info"][::-1]
            ],
            replies=[
                Reply.from_mp(reply, app)
                for reply in handler["reply_list_info"][::-1]
            ]
        )

    @classmethod
    def from_menu(cls, menu, data, app):
        """
        :type menu: .Menu
        """
        from . import Reply, Rule
        return cls.objects.create_handler(
            app=app,
            name="菜单[{0}]事件".format(data["name"]),
            src=cls.Source.MENU,
            rules=[Rule(
                type=Rule.Type.EVENTKEY,
                event=cls.EventType.CLICK,
                key=menu.content["key"]
            )],
            replies=[Reply.from_menu(data, app)]
        )

    def __str__(self):
        return self.name
