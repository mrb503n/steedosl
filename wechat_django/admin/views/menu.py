# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import forms
from django.contrib import messages
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
import object_tool
from wechatpy.exceptions import WeChatClientException

from ...models import Menu
from ..utils import get_request_params
from ..base import DynamicChoiceForm, WeChatModelAdmin


class MenuAdmin(WeChatModelAdmin):
    __category__ = "menu"
    __model__ = Menu

    changelist_object_tools = ("sync", "publish")
    change_form_template = "admin/wechat_django/menu/change_form.html"
    change_list_template = "admin/wechat_django/menu/change_list.html"

    list_display = (
        "operates", "id", "parent_id", "title", "type", "detail", "weight",
        "updated_at")
    list_display_links = ("title",)
    list_editable = ("weight", )
    fields = (
        "name", "type", "key", "url", "appid", "pagepath", "created_at",
        "updated_at")

    def title(self, obj):
        if obj.parent:
            return "|--- " + obj.name
        return obj.name
    title.short_description = _("title")

    @mark_safe
    def detail(self, obj):
        rv = ""
        if obj.type == Menu.Event.CLICK:
            rv = obj.content.get("key")
        elif obj.type == Menu.Event.VIEW:
            rv = '<a href="{0}">{1}</a>'.format(
                obj.content.get("url"), _("link"))
        elif obj.type == Menu.Event.MINIPROGRAM:
            rv = obj.content.get("appid")
        return rv or ""
    detail.short_description = _("detail")

    @mark_safe
    def operates(self, obj):
        del_url = reverse("admin:wechat_django_menu_delete", kwargs=dict(
            object_id=obj.id,
            wechat_app_id=obj.app_id
        ))
        rv = '<a class="deletelink" href="{0}"></a>'.format(del_url)
        if not obj.parent and not obj.type and obj.sub_button.count() < 5:
            query = dict(parent_id=obj.id)
            add_link = reverse("admin:wechat_django_menu_add", kwargs=dict(
                wechat_app_id=obj.app_id
            ))
            add_url = "{0}?{1}".format(add_link, urlencode(query))
            rv += '<a class="addlink" href="{0}"></a>'.format(add_url)
        return rv
    operates.short_description = _("actions")

    @object_tool.confirm(short_description=_("Sync menus"))
    def sync(self, request, obj=None):
        self.check_wechat_permission(request, "sync")
        def action():
            Menu.sync(request.app)
            return _("Menus successful synchronized")
            
        return self._clientaction(
            request, action, _("Sync menus failed with %(exc)s"))

    @object_tool.confirm(short_description=_("Publish menus"))
    def publish(self, request, obj=None):
        self.check_wechat_permission(request, "sync")
        def action():
            Menu.publish(request.app)
            return _("Menus successful published")
            
        return self._clientaction(
            request, action, _("Publish menus failed with %(exc)s"))

    def get_actions(self, request):
        actions = super(MenuAdmin, self).get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def get_fields(self, request, obj=None):
        fields = list(super(MenuAdmin, self).get_fields(request, obj))
        if not obj:
            fields.remove("created_at")
            fields.remove("updated_at")
        return fields

    def get_readonly_fields(self, request, obj=None):
        rv = super(MenuAdmin, self).get_readonly_fields(request, obj)
        if obj:
            rv = rv + ("created_at", "updated_at")
        return rv

    def get_queryset(self, request):
        rv = super(MenuAdmin, self).get_queryset(request)
        if not get_request_params(request, "menuid"):
            rv = rv.filter(menuid__isnull=True)
        if request.GET.get("parent_id"):
            rv = rv.filter(parent_id=request.GET["parent_id"])
        return rv

    class MenuForm(DynamicChoiceForm):
        content_field = "content"
        origin_fields = ("name", "menuid", "type", "weight")
        type_field = "type"

        key = forms.CharField(label=_("menu key"), required=False)
        url = forms.URLField(label=_("url"), required=False)
        appid = forms.CharField(label=_("miniprogram app_id"), required=False)
        pagepath = forms.CharField(label=_("pagepath"), required=False)

        class Meta(object):
            model = Menu
            fields = ("name", "menuid", "type", "weight")

        def allowed_fields(self, type, cleaned_data):
            if type == Menu.Event.VIEW:
                fields = ("url", )
            elif type == Menu.Event.CLICK:
                fields = ("key", )
            elif type == Menu.Event.MINIPROGRAM:
                fields = ("url", "appid", "apppath")
            else:
                fields = tuple()
            return fields
    form = MenuForm

    def save_model(self, request, obj, form, change):
        if not change and request.GET.get("parent_id"):
            obj.parent_id = request.GET["parent_id"]
        return super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        if not super(MenuAdmin, self).has_add_permission(request):
            return False
        # 判断菜单是否已满
        q = self.get_queryset(request)
        if request.GET.get("parent_id"):
            return q.count() < 5
        else:
            return q.filter(parent_id__isnull=True).count() < 3

    def get_model_perms(self, request):
        return (super(MenuAdmin, self).get_model_perms(request) 
            if request.app.abilities.menus else {})
