# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

import django
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.actions import delete_selected
from django.contrib.admin.templatetags import admin_list, admin_urls
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import response
from django.shortcuts import redirect
from django.utils.encoding import force_text
from django.utils.http import urlencode
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import NoReverseMatch, resolve, reverse
import six
from wechatpy.exceptions import WeChatClientException

from ..models.permission import get_user_permissions
from ..utils.web import mutable_GET


registered_admins = []


class RecursiveDeleteActionMixin(object):
    """逐一删除混合类"""
    def get_actions(self, request):
        actions = super(RecursiveDeleteActionMixin, self).get_actions(request)
        if "delete_selected" in actions:
            actions["delete_selected"] = (
                RecursiveDeleteActionMixin.delete_selected_recusively,
                actions["delete_selected"][1],
                actions["delete_selected"][2]
            )
        return actions

    def delete_selected_recusively(self, request, queryset):
        """逐一删除"""
        if not request.POST.get("post"):
            resp = delete_selected(self, request, queryset)
            resp.context_data.update(
                wechat_app=request.app,
                wechat_app_id=request.app_id
            )
            return resp

        with transaction.atomic():
            for o in queryset.all():
                try:
                    if not self.has_delete_permission(request, o):
                        raise PermissionDenied
                    o.delete()
                except WeChatClientException:
                    msg = _("delete %(category)s failed: %(obj)s") % dict(
                        category=self.model.verbose_name_plural,
                        obj=o
                    )
                    self.logger(request).warning(msg, exc_info=True)
                    raise
    delete_selected.short_description = _("delete selected")


def has_wechat_permission(request, app, category="", operate="", obj=None):
    """
    检查用户是否具有某一微信权限
    :type request: django.http.request.HttpRequest
    """
    if request.user.is_superuser:
        return True
    perms = get_user_permissions(request.user, app)
    needs = {category, "{0}_{1}".format(category, operate)}
    return bool(needs.intersection(perms))


class WeChatChangeList(ChangeList):
    def __init__(self, request, *args, **kwargs):
        super(WeChatChangeList, self).__init__(request, *args, **kwargs)
        self.request = request

    def url_for_result(self, result):
        view = "admin:%s_%s_change" % (
            self.opts.app_label, self.opts.model_name)
        kwargs = dict(
            object_id=getattr(result, self.pk_attname),
            wechat_app_id=self.request.app_id
        )
        return reverse(
            view, kwargs=kwargs, current_app=self.model_admin.admin_site.name)


class WeChatModelAdminMetaClass(forms.MediaDefiningClass):
    def __new__(cls, name, bases, attrs):
        model = attrs.pop("__model__", None)
        self = super(WeChatModelAdminMetaClass, cls).__new__(
            cls, name, bases, attrs)
        if name != "WeChatModelAdmin" and model:
            registered_admins.append((model, self))
        return self


class WeChatModelAdmin(six.with_metaclass(WeChatModelAdminMetaClass, admin.ModelAdmin)):
    """所有微信相关业务admin的基类

    并且通过request.app_id及request.app拿到app信息
    """
    #region view
    def get_changelist(self, request):
        return WeChatChangeList

    def get_urls(self):
        urlpatterns = super(WeChatModelAdmin, self).get_urls()
        # django 1.11 替换urlpattern为命名式的
        if django.VERSION[0] < 2:
            for pattern in urlpatterns:
                pattern._regex = pattern._regex.replace(
                    "(.+)", "(?P<object_id>.+)")
        return urlpatterns

    def changelist_view(self, request, extra_context=None):
        # 允许没有选中的actions
        post = request.POST.copy()
        if admin.helpers.ACTION_CHECKBOX_NAME not in post:
            post.update({admin.helpers.ACTION_CHECKBOX_NAME: None})
            request._set_post(post)
        return super(WeChatModelAdmin, self).changelist_view(
            request, extra_context)

    def response_post_save_add(self, request, obj):
        return self.response_post_save_change(request, obj)

    def response_post_save_change(self, request, obj):
        # 修正重定向url
        opts = self.model._meta

        if self.has_change_permission(request, None):
            post_url = reverse(
                "admin:%s_%s_changelist" % (opts.app_label, opts.model_name),
                kwargs=dict(wechat_app_id=request.app_id),
                current_app=self.admin_site.name
            )
            preserved_filters = self.get_preserved_filters(request)
            post_url = admin_urls.add_preserved_filters(dict(
                preserved_filters=preserved_filters,
                opts=opts
            ), post_url)
        else:
            post_url = reverse(
                "admin:index",
                kwargs=dict(wechat_app_id=request.app_id),
                current_app=self.admin_site.name
            )
        return response.HttpResponseRedirect(post_url)

    def response_delete(self, request, obj_display, obj_id):
        resp = super(WeChatModelAdmin, self).response_delete(
            request, obj_display, obj_id)
        if not resolve(resp.url).kwargs.get("wechat_app_id"):
            return self.response_post_save_change(request, None)
        return resp
    #endregion

    #region model
    def get_queryset(self, request):
        return (super(WeChatModelAdmin, self)
            .get_queryset(request).filter(app_id=request.app_id))

    def save_model(self, request, obj, form, change):
        if not change:
            obj.app_id = request.app_id
        return super(WeChatModelAdmin, self).save_model(request, obj, form, change)
    #endregion

    #region permissions
    def check_wechat_permission(self, request, operate="", category="", obj=None):
        if not self.has_wechat_permission(request, operate, category, obj):
            raise PermissionDenied

    def has_wechat_permission(self, request, operate="", category="", obj=None):
        app = request.app
        category = category or self.__category__
        return has_wechat_permission(request, app, category, operate, obj)

    def get_model_perms(self, request):
        # 隐藏首页上的菜单
        if getattr(request, "app_id", None):
            return super(WeChatModelAdmin, self).get_model_perms(request)
        return {}

    def has_add_permission(self, request):
        return self.has_wechat_permission(request, "add")

    def has_change_permission(self, request, obj=None):
        return self.has_wechat_permission(request, "change", obj=obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_wechat_permission(request, "delete", obj=obj)

    def has_module_permission(self, request):
        """是否拥有任意本公众号管理权限"""
        return bool(get_user_permissions(request.user, request.app))
    #endregion

    #region utils
    def logger(self, request):
        name = "wechat.admin.{0}".format(request.app.name)
        return logging.getLogger(name)
    #endregion


class DynamicChoiceForm(forms.ModelForm):
    content_field = "_content"
    type_field = "type"
    origin_fields = tuple()

    def __init__(self, *args, **kwargs):
        inst = kwargs.get("instance")
        if inst:
            initial = kwargs.get("initial", {})
            initial.update(getattr(inst, self.content_field))
            kwargs["initial"] = initial
        super(DynamicChoiceForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(DynamicChoiceForm, self).clean()
        if self.type_field not in cleaned_data:
            self.add_error(self.type_field, "")
            return
        type = cleaned_data[self.type_field]
        fields = self.allowed_fields(type, cleaned_data)

        content = dict()
        for k in set(cleaned_data.keys()).difference(self.origin_fields):
            if k in fields:
                content[k] = cleaned_data[k]
                del cleaned_data[k]
        cleaned_data[self.content_field] = content
        return cleaned_data

    def allowed_fields(self, type, cleaned_data):
        raise NotImplementedError()

    def save(self, commit=True, *args, **kwargs):
        model = super(DynamicChoiceForm, self).save(False, *args, **kwargs)
        setattr(model, self.content_field,
            self.cleaned_data[self.content_field])
        if commit:
            model.save()
        return model
