# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re

from django.db import models as m
from django.utils.module_loading import import_string
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField

from ..utils.model import enum2choices, model_fields
from . import MessageHandler, MsgType, WeChatModel


class Rule(WeChatModel):
    class Type(object):
        MSGTYPE = "msg_type"  # 类型匹配
        EVENT = "event"  # 事件
        EVENTKEY = "eventkey"  # 指定事件
        CONTAIN = "contain"  # 包含
        EQUAL = "equal"  # 匹配
        REGEX = "regex"  # 正则
        CUSTOM = "custom"
        ALL = "all"  # 全部

    class ReceiveMsgType(MsgType):
        LOCATION = "location"
        LINK = "link"
        SHORTVIDEO = "shortvideo"
        EVENT = "event"

    handler = m.ForeignKey(
        MessageHandler, related_name="rules", null=False, on_delete=m.CASCADE)

    type = m.CharField(
        _("type"), max_length=16, choices=enum2choices(Type))  # 规则类型
    _content = JSONField(db_column="content", blank=True)  # 规则内容

    weight = m.IntegerField(_("weight"), default=0, null=False)
    created_at = m.DateTimeField(_("created_at"), auto_now_add=True)
    updated_at = m.DateTimeField(_("updated_at"), auto_now=True)

    @property
    def content(self):
        return self._content

    class Meta:
        verbose_name = _("rule")
        verbose_name_plural = _("rules")

        ordering = ("-weight", "id")

    def __init__(self, *args, **kwargs):
        content_keys = set(kwargs.keys()) - model_fields(self)
        content = dict()
        for key in content_keys:
            content[key] = kwargs.pop(key)
        kwargs["_content"] = content
        super(Rule, self).__init__(*args, **kwargs)

    def match(self, message_info):
        """
        :type message_info: wechat_django.models.WeChatMessageInfo
        """
        if self.type == self.Type.CUSTOM:
            return self._custom_match(message_info)

        return self._match(message_info.message)

    def _custom_match(self, message_info):
        """
        :type message_info: wechat_django.models.WeChatMessageInfo
        """
        try:
            func = import_string(self.content["program"])
        except ImportError:
            pass
        else:
            appname = message_info.app.name
            if not hasattr(func, "message_rule"):
                return False
            elif (hasattr(func.message_rule, "__contains__")
                  and appname not in func.message_rule):
                return False
            try:
                return func(message_info)
            except:
                pass
        return False

    def _match(self, message):
        """
        :type message: wechatpy.messages.BaseMessage
        """
        if self.type == self.Type.ALL:
            return True
        elif self.type == self.Type.MSGTYPE:
            return message.type == self.content["msg_type"]
        elif self.type == self.Type.EVENT:
            return (message.type == self.ReceiveMsgType.EVENT
                and self._event_match(message))
        elif self.type == self.Type.EVENTKEY:
            return (message.type == self.ReceiveMsgType.EVENT
                and self._event_match(message)
                and hasattr(message, "key")
                and message.key == self.content["key"])
        elif self.type == self.Type.CONTAIN:
            return (message.type == self.ReceiveMsgType.TEXT
                and self.content["pattern"] in message.content)
        elif self.type == self.Type.EQUAL:
            return (message.type == self.ReceiveMsgType.TEXT
                and message.content == self.content["pattern"])
        elif self.type == self.Type.REGEX:
            return (message.type == self.ReceiveMsgType.TEXT
                and re.search(self.content["pattern"], message.content))
        return False

    def _event_match(self, message):
        event = message.event.lower()
        target = self.content["event"].lower()
        if target == MessageHandler.EventType.SUBSCRIBE:
            # wechatpy对eventtype进行了二次封装
            return event in (
                MessageHandler.EventType.SUBSCRIBE, "subscribe_scan")
        else:
            return event == target

    @classmethod
    def from_mp(cls, data, handler=None):
        return cls(
            handler=handler,
            type=data["match_mode"],
            pattern=data["content"]
        )

    def __str__(self):
        if self.handler_id:
            return "{0} - {1}".format(self.handler.name, self.type)
        return "{0}".format(self.type)
