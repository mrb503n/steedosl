# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from contextlib import contextmanager


@contextmanager
def mutable_GET(request):
    request.GET._mutable = True
    try:
        yield request.GET
    finally:
        request.GET._mutable = False


def get_ip(request):
    """获取客户端ip"""
    if not request:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip
