import importlib

from django.db import models as m
from django.utils.translation import ugettext as _
from jsonfield import JSONField
import requests
from wechatpy import replies

from . import MessageHandler, ReplyMsgType
from .. import utils

class Reply(m.Model):
    handler = m.ForeignKey(MessageHandler, on_delete=m.CASCADE,
        related_name="replies")

    msg_type = m.CharField(_("type"), max_length=16,
        choices=utils.enum2choices(ReplyMsgType))
    content = JSONField()

    def reply(self, message):
        """
        :type message: wechatpy.messages.BaseMessage

        :returns: serialized xml response
        """
        if self.msg_type == ReplyMsgType.FORWARD:
            # 转发业务
            resp = requests.post(self.content["url"], message.raw, 
                params=message.request.GET, timeout=4.5)
            resp.raise_for_status()
            return resp.content
        elif self.msg_type == ReplyMsgType.CUSTOM:
            # 自定义业务
            try:
                mod_name, func_name = self.content["program"].rsplit('.', 1)
                mod = importlib.import_module(mod_name)
                func = getattr(mod, func_name)
            except:
                pass # TODO: 404
                return ""
            else:
                reply = func(message)
                if not reply:
                    return ""
                elif isinstance(reply, str):
                    reply = replies.TextReply(content=reply)
                reply.source = message.target
                reply.target = message.source
        else:
            # 正常回复类型
            if self.msg_type == ReplyMsgType.NEWS:
                klass = replies.ArticlesReply
                data = dict(content=self.content["content"])
            elif self.msg_type == ReplyMsgType.MUSIC:
                klass = replies.MusicReply
                data = dict(**self.content)
            elif self.msg_type == ReplyMsgType.VIDEO:
                klass = replies.VideoReply
                data = dict(**self.content)
            elif self.msg_type == ReplyMsgType.IMAGE:
                klass = replies.ImageReply
                data = dict(media_id=self.content["media_id"])
            elif self.msg_type == ReplyMsgType.VOICE:
                klass = replies.VoiceReply
                data = dict(media_id=self.content["media_id"])
            else:
                klass = replies.TextReply
                data = dict(content=self.content["content"])
            reply = klass(message=message, **data)
        return reply.render()

    @classmethod
    def from_mp(cls, data):
        type = data["type"]
        reply = cls(
            msg_type=type
        )
        if type == ReplyMsgType.TEXT:
            content = dict(content=data["content"])
        elif type in (ReplyMsgType.IMAGE, ReplyMsgType.VOICE, 
            ReplyMsgType.VIDEO):
            # TODO: 图片回复说是img
            # TODO: 按照文档 是临时素材 需要转换为永久素材
            content = dict(media_id=content)
        elif type == ReplyMsgType.NEWS:
            # TODO: 应该处理成永久素材保存
            content = dict(content=cls.mpnews2replynews(data["news_info"]["list"]))
        else:
            # TODO: unknown type
            raise Exception("unknown type")
        reply.content = content
        return reply

    @classmethod
    def from_menu(cls, data):
        type = data["type"]
        rv = cls(msg_type=type)
        if type == ReplyMsgType.TEXT:
            content = dict(content=data["content"])
        elif type in (ReplyMsgType.IMAGE, ReplyMsgType.VOICE, 
            ReplyMsgType.VIDEO):
            # TODO: video存的时下载链接
            content = dict(media_id=data["value"])
        elif type == ReplyMsgType.NEWS:
            content = dict(
                content=cls.mpnews2replynews(data["news_info"]),
                media_id=data["value"]
            )
        else:
            # TODO: unknown type
            raise Exception("unknown type")
        rv.content = content
        return rv

    @staticmethod
    def mpnews2replynews(mpnews):
        return list(map(lambda o: dict(
            title=o["title"],
            description=o.get("digest") or "",
            image=o["cover_url"],
            url=o["content_url"]
        ), mpnews))

    def __str__(self):
        if self.handler:
            return self.handler.name
        return super().__str__()