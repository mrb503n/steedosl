# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from functools import update_wrapper, wraps

from django.db import models as m
from django.utils.encoding import force_bytes
import six

from . import WeChatApp


def appmethod(func_or_name):
    """可以把方法注册到WeChatApp上的语法糖

        class SomeModel(WeChatModel):
            @classmethod
            @appmethod
            def awesome_method(cls, app, *args, **kwargs):
                # ...

            @classmethod
            @appmethod("another_method")
            def method(cls, app, *args, **kwargs):
                # ...

        res = SomeModel.awesome_method(app, *args, **kwargs)
        res = app.awesome_method(*args, **kwargs)
        res = app.another_method(*args, **kwargs)
    """
    def decorator(func):
        @wraps(func)
        def decorated_func(*args, **kwargs):
            return func(*args, **kwargs)
        decorated_func._appmethod = name

        return decorated_func

    if callable(func_or_name):
        name = func_or_name.__name__
        return decorator(func_or_name)
    else:
        name = func_or_name
        return decorator


class WeChatModelMetaClass(m.base.ModelBase):
    def __new__(meta, name, bases, attrs):
        # python2.7 __str__必须返回bytestring
        if six.PY2 and "__str__" in attrs:
            __str__ = attrs.pop("__str__")
            attrs["__str__"] = update_wrapper(
                lambda self: force_bytes(__str__(self)), __str__)

        cls = super(WeChatModelMetaClass, meta).__new__(
            meta, name, bases, attrs)
        return cls

    def __init__(cls, name, bases, attrs):
        super(WeChatModelMetaClass, cls).__init__(name, bases, attrs)
        for attr in attrs:
            # 将modelmethod转换为appmethod
            value = getattr(cls, attr)
            if getattr(value, "_appmethod", False):
                method = value

                def wrapped_func(self, *args, **kwargs):
                    return method(self, *args, **kwargs)

                method_name = method._appmethod
                appmethod = wraps(method)(wrapped_func)
                appmethod.__name__ = str(method_name)
                appmethod.__qualname__ = "{0}.{1}".format(
                    "WeChatApp", method_name)
                setattr(WeChatApp, method_name, appmethod)


class WeChatModel(six.with_metaclass(WeChatModelMetaClass, m.Model)):
    class Meta(object):
        abstract = True
