# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import messages
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
import object_tool
from wechatpy.exceptions import WeChatClientException

from ...constants import AppType
from ...models import UserTag
from ..utils import field_property
from ..base import RecursiveDeleteActionMixin, WeChatModelAdmin


class UserTagAdmin(RecursiveDeleteActionMixin, WeChatModelAdmin):
    __category__ = "usertag"
    __model__ = UserTag

    actions = ("sync_users", "sync_openids")
    changelist_object_tools = ("sync",)
    list_display = ("id",  "name", "sys_tag", "count", "created_at")
    search_fields = ("name", )

    fields = list_display
    readonly_fields = ("id", "count", "sys_tag")

    sys_tag = field_property("sys_tag", boolean=True, short_description=_("sys tag"))

    @object_tool.confirm(short_description=_("Sync user tags"))
    def sync(self, request, obj=None):
        self.check_wechat_permission(request, "sync")
        def action():
            tags = UserTag.sync(request.app)
            msg = _("%(count)d tags successfully synchronized")
            return msg % dict(count=len(tags))

        return self._clientaction(
            request, action, _("Sync user tags failed with %(exc)s"))

    def sync_users(self, request, queryset, detail=True):
        self.check_wechat_permission(request, "sync", "user")
        def action():
            tags = queryset.all()
            for tag in tags:
                users = tag.sync_users(detail)
                msg = _("%(count)d users of %(tag)s successfully synchronized")
                return msg % dict(count=len(users), tag=tag.name)
        
        return self._clientaction(
            request, action, _("Sync users failed with %(exc)s"))
    sync_users.short_description = _("sync tag users")

    sync_openids = lambda self, request, queryset: self.sync_users(
        request, queryset, False)
    sync_openids.short_description = _("sync tag openids")

    @mark_safe
    def count(self, obj):
        return '<a href="{link}">{count}</a>'.format(
            link="{0}?{1}".format(
                reverse(
                    "admin:wechat_django_wechatuser_changelist",
                    kwargs=dict(wechat_app_id=obj.app_id)
                ),
                urlencode(dict(
                    tags__in=obj._id
                ))
            ),
            count=obj.users.count()
        )
    count.short_description = _("users count")

    def get_fields(self, request, obj=None):
        fields = list(super(UserTagAdmin, self).get_fields(request, obj))
        if not obj:
            fields.remove("count")
            fields.remove("created_at")
        return fields

    def get_readonly_fields(self, request, obj=None):
        rv = super(UserTagAdmin, self).get_readonly_fields(request, obj)
        if obj:
            rv = rv + ("created_at",)
        return rv

    def has_delete_permission(self, request, obj=None):
        rv = super(UserTagAdmin, self).has_delete_permission(request, obj)
        if rv and obj:
            return not obj.sys_tag
        return rv

    def has_add_permission(self, request):
        return super(UserTagAdmin, self).has_add_permission(request)\
            and self.get_queryset(request).exclude(
                id__in=UserTag.SYS_TAGS).count() < 100

    def get_model_perms(self, request):
        if request.app.type not in (AppType.SERVICEAPP, AppType.SUBSCRIBEAPP):
            return {}
        return super(UserTagAdmin, self).get_model_perms(request)
