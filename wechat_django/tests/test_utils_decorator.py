# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.http import response
from django.urls import reverse
from django.urls.resolvers import get_ns_resolver

# from .. import urls
from ..decorators import wechat_route
from .base import WeChatTestCase


class UtilDecoratorTestCase(WeChatTestCase):
    def test_wechat_route(self):
        """测试wechat_route 装饰器"""
        pass
        # def test(request, *args, **kwargs):
        #     return response.HttpResponse(status=204)
        # api1 = "api1/"
        # wechat_route(api1)(test)
        # api2 = "api2/"
        # name = "test1"
        # wechat_route(api2, methods=["POST"], name=name)(test)

        # # python2.7在linux下会走到cache 非常的神奇..
        # get_ns_resolver.cache_clear()

        # fullurl = "/wechat/" + self.app.name + "/" + api1
        # url = reverse(
        #     "wechat_django:" + test.__name__, kwargs=dict(appname=self.app.name))
        # self.assertEqual(url, fullurl)
        # resp = self.client.get(fullurl)
        # self.assertEqual(resp.status_code, 204)
        # resp = self.client.post(fullurl)
        # self.assertIsInstance(resp, response.HttpResponseNotAllowed)

        # fullurl = "/wechat/" + self.app.name + "/" + api2
        # url = reverse(
        #     "wechat_django:" + name, kwargs=dict(appname=self.app.name))
        # self.assertEqual(url, fullurl)
        # resp = self.client.get(fullurl)
        # self.assertIsInstance(resp, response.HttpResponseNotAllowed)
        # resp = self.client.post(fullurl)
        # self.assertEqual(resp.status_code, 204)
