# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from six.moves.urllib.parse import urlparse
from wechatpy import parse_message

from . import WeChatApp, WeChatUser


class WeChatInfo(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def app(self):
        """
        :rtype: wechat_django.models.WeChatApp
        """
        if not hasattr(self, "_app"):
            self._app = WeChatApp.objects.get_by_name(self.appname)
        return self._app

    @property
    def user(self):
        """
        :rtype: wechat_django.models.WeChatUser
        """
        if not hasattr(self, "_user"):
            raise NotImplementedError()
        return self._user

    @property
    def request(self):
        """
        :rtype: django.http.request.HttpRequest
        """
        return self._request

    @property
    def appname(self):
        return self._appname


class WeChatMessageInfo(WeChatInfo):
    """由微信接收到的消息"""
    @property
    def message(self):
        """
        :raises: xmltodict.expat.ExpatError
        :rtype: wechatpy.messages.BaseMessage
        """
        if not hasattr(self, "_message"):
            app = self.app
            request = self.request
            raw = self.raw
            if app.crypto:
                self._raw = app.crypto.decrypt_message(
                    self.raw,
                    request.GET["msg_signature"],
                    request.GET["timestamp"],
                    request.GET["nonce"]
                )
            self._message = parse_message(self.raw)
        return self._message

    @property
    def local_user(self):
        """
        不从微信服务器重新同步用户
        :rtype: wechat_django.models.WeChatUser
        """
        if not hasattr(self, "_user") and not hasattr(self, "_local_user"):
            self._local_user = self.app.user_by_openid(
                self.message.source, ignore_errors=True, sync_user=False)
        return self._user if hasattr(self, "_user") else self._local_user

    @property
    def user(self):
        """
        :rtype: wechat_django.models.WeChatUser
        """
        if not hasattr(self, "_user"):
            self._user = self.app.user_by_openid(
                self.message.source, ignore_errors=True)
        return self._user

    @property
    def raw(self):
        """原始消息
        :rtype: str
        """
        if hasattr(self, "_raw"):
            return self._raw
        return self.request.body


class WeChatOAuthInfo(WeChatInfo):
    """附带在request上的微信对象
    """
    @property
    def scope(self):
        """授权的scope
        :rtype: tuple
        """
        from ..oauth import WeChatSNSScope

        if not getattr(self, "_scope", None):
            self._scope = (WeChatSNSScope.BASE,)
        return self._scope

    _state = ""
    @property
    def state(self):
        """授权携带的state"""
        return self._state

    @property
    def oauth_uri(self):
        return self.app.oauth.authorize_url(
            self.redirect_uri,
            ",".join(self.scope),
            self.state
        )

    _redirect_uri = None

    @property
    def redirect_uri(self):
        """授权后重定向回的地址"""
        # 绝对路径
        if self._redirect_uri and urlparse(self._redirect_uri).netloc:
            return self._redirect_uri

        request = self.request
        return request.build_absolute_uri(
            self._redirect_uri
            or (request.is_ajax() and request.META.get("HTTP_REFERER"))
            or None
        )

    @redirect_uri.setter
    def redirect_uri(self, value):
        self._redirect_uri = value

    @property
    def openid(self):
        if not hasattr(self, "_openid"):
            self._openid = self.request.session.get(self.session_key)
        return self._openid

    @property
    def user(self):
        if not hasattr(self, "_user"):
            self._user = self.app.user_by_openid(self.openid)
        return super(WeChatOAuthInfo, self).user

    @property
    def session_key(self):
        return "wechat_{0}_user".format(self.appname)

    def __str__(self):
        return "WeChatOuathInfo: " + "\t".join(
            "{k}: {v}".format(k=attr, v=getattr(self, attr, None))
            for attr in
            ("app", "user", "redirect", "oauth_uri", "state", "scope")
        )
