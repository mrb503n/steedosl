# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.apps import AppConfig


class WeChatConfig(AppConfig):
    name = "wechat_django"
    verbose_name = "wechat"

    def ready(self):
        from . import handler, views
