# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from wechatpy.exceptions import WeChatClientException

from ..models import Material
from .base import RecursiveDeleteActionMixin, DynamicChoiceForm, WeChatModelAdmin


class MaterialAdmin(RecursiveDeleteActionMixin, WeChatModelAdmin):
    __category__ = "material"
    __model__ = Material

    actions = ("sync", )
    list_display = ("media_id", "type", "comment", "updatetime")
    list_filter = ("type", )
    search_fields = ("name", "media_id", "comment")

    fields = ("type", "media_id", "name", "open", "comment")
    readonly_fields = ("type", "media_id", "name", "open", "media_id")

    @mark_safe
    def preview(self, obj):
        if obj.type == Material.Type.IMAGE:
            return '<img src="%s" />'%obj.url
    preview.short_description = _("preview")
    preview.allow_tags = True

    def updatetime(self, obj):
        return timezone.datetime.fromtimestamp(obj.update_time)
    updatetime.short_description = _("update time")

    @mark_safe
    def open(self, obj):
        blank = True
        if obj.type == Material.Type.NEWS:
            url = "{0}?{1}".format(
                reverse("admin:wechat_django_article_changelist"),
                urlencode(dict(
                    app_id=obj.app_id,
                    material_id=obj.id
                ))
            )
            blank = False
        elif obj.type == Material.Type.VOICE:
            # 代理下载
            app = obj.app
            url = reverse("wechat_django:material_proxy", kwargs=dict(
                appname=app.name,
                media_id=obj.media_id
            ))
        else:
            url = obj.url
        return '<a href="{0}" {1}>{2}</a>'.format(
            url, 'target="_blank"' if blank else "", _("open")
        )
    open.short_description = _("open")
    open.allow_tags = True

    def sync(self, request, queryset):
        self.check_wechat_permission(request, "sync")
        app = request.app
        try:
            materials = Material.sync(app)
            msg = _("%(count)d materials successfully synchronized")
            self.message_user(request, msg % dict(count=len(materials)))
        except Exception as e:
            msg = _("sync failed with %(exc)s") % dict(exc=e)
            if isinstance(e, WeChatClientException):
                self.logger(request).warning(msg, exc_info=True)
            else:
                self.logger(request).error(msg, exc_info=True)
            self.message_user(request, msg, level=messages.ERROR)
    sync.short_description = _("sync")

    def has_add_permission(self, request):
        return False
