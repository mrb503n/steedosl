from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.translation import ugettext as _

from ..models import (EventType, MessageHandler, ReceiveMsgType, 
    Reply, ReplyMsgType, Rule, WeChatApp)
from ..utils import check_wechat_permission, enum2choices
from .bases import DynamicChoiceForm, WeChatAdmin

class RuleInline(admin.StackedInline):
    model = Rule
    extra = 0
    min_num = 1

    class RuleForm(DynamicChoiceForm):
        content_field = "rule"
        origin_fields = ("type", "weight")
        type_field = "type"

        msg_type = forms.ChoiceField(label=_("message type"), 
            choices=enum2choices(ReceiveMsgType), required=False)
        event = forms.ChoiceField(label=_("event"), 
            choices=enum2choices(EventType), required=False)
        key = forms.CharField(label=_("event key"), required=False)
        pattern = forms.CharField(label=_("pattern"), required=False)
        # media_id = forms.CharField(label=_("media_id"), required=False)

        class Meta(object):
            model = Rule
            fields = ("type", "weight")

        def allowed_fields(self, type, cleaned_data):
            if type in (Rule.Type.CONTAIN, Rule.Type.REGEX, Rule.Type.EQUAL):
                fields = ("pattern", )
            elif type == Rule.Type.EVENT:
                fields = ("event", )
            elif type == Rule.Type.EVENTKEY:
                fields = ("event", "key")
            elif type == Rule.Type.MSGTYPE:
                fields = ("msg_type", )
            else:
                fields = tuple()
            return fields
    form = RuleForm


class ReplyInline(admin.StackedInline):
    model = Reply
    extra = 0

    class ReplyForm(DynamicChoiceForm):
        content_field = "content"
        origin_fields = ("msg_type",)
        type_field = "msg_type"

        program = forms.CharField(label=_("program"), required=False)
        url = forms.URLField(label=_("url"), required=False)
        content = forms.CharField(label=_("content"), widget=forms.Textarea,
            required=False)
        media_id = forms.CharField(label=_("media_id"), required=False)

        class Meta(object):
            model = Reply
            fields = ("msg_type", )
        
        def allowed_fields(self, type, cleaned_data):
            if type == ReplyMsgType.FORWARD:
                fields = ("url", )
            elif type == ReplyMsgType.CUSTOM:
                fields = ("program", )
            elif type == ReplyMsgType.NEWS:
                fields = ("content", "media_id")
            elif type in (ReplyMsgType.VIDEO, ReplyMsgType.VOICE, 
                ReplyMsgType.IMAGE):
                fields = ("media_id", )
            elif type == ReplyMsgType.MUSIC:
                # TODO: 是错的
                fields = ("media_id", )
            elif type == ReplyMsgType.TEXT:
                fields = ("content", )
            return fields
    form = ReplyForm

class MessageHandlerAdmin(WeChatAdmin):
    class AvailableFilter(admin.SimpleListFilter):
        title = _("available")
        parameter_name = "available"
        
        def lookups(self, request, model_admin):
            return [(True, "available")]
        
        def queryset(self, request, queryset):
            if self.value():
                now = timezone.now()
                queryset = (queryset.filter(enabled=True)
                    .exclude(starts__gt=now).exclude(ends__lte=now))
            return queryset

    actions = ("sync", )
    list_display = ("name", "is_sync", "available", "enabled", "weight", 
        "starts", "ends", "updated", "created")
    list_editable = ("weight",)
    list_filter = (AvailableFilter, )
    search_fields = ("name", "rules__rule", "replies__content")

    inlines = (RuleInline, ReplyInline)
    fields = ("name", "strategy", "starts", "ends", "enabled", "log",
        "weight", "created", "updated")

    def sync(self, request, queryset):
        app_id = self.get_request_app_id(request)
        app = WeChatApp.get_by_id(app_id)
        try:
            handlers = MessageHandler.sync(app)
            self.message_user(request, 
                "%d handlers successfully synchronized"%len(handlers))
        except Exception as e:
            self.message_user(request, 
                "sync failed with %s"%str(e), level=messages.ERROR)
    sync.short_description = _("sync")

    def is_sync(self, obj):
        return obj.src in (MessageHandler.Source.MP, MessageHandler.Source.MENU)
    is_sync.boolean = True
    is_sync.short_description = _("synchronized from wechat")

    def changelist_view(self, request, extra_context=None):
        post = request.POST.copy()
        if admin.helpers.ACTION_CHECKBOX_NAME not in post:
            post.update({admin.helpers.ACTION_CHECKBOX_NAME: None})
            request._set_post(post)
        return super().changelist_view(request, extra_context)

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if not obj:
            fields.remove("created")
            fields.remove("updated")
        return fields

    def get_readonly_fields(self, request, obj=None):
        rv = super().get_readonly_fields(request, obj)
        if obj:
            rv = rv + ("created", "updated")
        return rv

    def save_model(self, request, obj, form, change):
        obj.src = MessageHandler.Source.SELF
        return super().save_model(request, obj, form, change)

admin.site.register(MessageHandler, MessageHandlerAdmin)