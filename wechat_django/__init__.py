# -*- coding: utf-8 -*-
# flake8: noqa
from __future__ import unicode_literals

__title__ = "wechat-django"
__description__ = "Django WeChat Extension"
__url__ = "https://github.com/Xavier-Lam/wechat-django"
__version__ = "0.3.1"
__author__ = "Xavier-Lam"
__author_email__ = "Lam.Xavier@hotmail.com"

default_app_config = "wechat_django.apps.WeChatConfig"


from .handler import message_handler, message_rule
from .oauth import wechat_auth, WeChatOAuthView, WeChatSNSScope
