# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import os
try:
    from unittest import mock
except ImportError:
    import mock

from django.test import RequestFactory, TestCase

from ..models import WeChatApp


class WeChatTestCaseBase(TestCase):
    def assertCallArgsEqual(self, func, args=(), kwargs=None):
        kwargs = kwargs or {}
        call_args = func.call_args[0]
        call_kwargs = func.call_args[1]
        self.assertEqual(call_args, args)
        self.assertEqual(
            {k: v for k, v in call_kwargs.items() if k in kwargs}, kwargs)

    def load_data(self, path):
        res_file = os.path.join(
            os.path.dirname(__file__), "data", '%s.json' % path)
        with open(res_file, "rb") as f:
            return json.loads(f.read().decode("utf-8"))

    def list_fields(self, model):
        return [f.name for f in model._meta.fields]

    @property
    def base_url(self):
        return "http://localhost/"

    def rf(self, **defaults):
        return RequestFactory(**defaults)


class WeChatTestCase(WeChatTestCaseBase):
    @classmethod
    def setUpTestData(cls):
        super(WeChatTestCase, cls).setUpTestData()
        WeChatApp.objects.create(title="test", name="test",
            appid="appid", appsecret="secret", token="token")
        WeChatApp.objects.create(title="test1", name="test1",
            appid="appid1", appsecret="secret", token="token")
        WeChatApp.objects.create(title="miniprogram", name="miniprogram",
            appid="miniprogram", appsecret="secret",
            type=WeChatApp.Type.MINIPROGRAM)

    def setUp(self):
        self.app = WeChatApp.objects.get_by_name("test")
        self.another_app = WeChatApp.objects.get_by_name("test1")
        self.miniprogram = WeChatApp.objects.get_by_name("miniprogram")

    #region utils
    def _create_handler(self, rules=None, name="", replies=None, app=None,
        **kwargs):
        """:rtype: MessageHandler"""
        from ..models import MessageHandler, Reply, Rule

        if not rules:
            rules = [dict(type=Rule.Type.ALL)]
        if isinstance(rules, dict):
            rules = [rules]
        if isinstance(replies, dict):
            replies = [replies]

        replies = replies or []
        rules = [
            Rule(**rule)
            for rule in rules
        ]
        replies = [
            Reply(**reply)
            for reply in replies
        ]

        app = app or self.app
        return MessageHandler.objects.create_handler(
            app=app,
            name=name,
            rules=rules,
            replies=replies,
            **kwargs
        )

    def _msg2info(self, message, app=None, **kwargs):
        """:rtype: WeChatMessageInfo"""
        from ..handler import WeChatMessageInfo
        return WeChatMessageInfo(
            _app=app or self.app,
            _message=message,
            **{
                "_" + k: v
                for k, v in kwargs.items()
            }
        )
    #endregion
