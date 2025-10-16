# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import time

from django.test import RequestFactory
from django.utils.http import urlencode
from httmock import response
from requests.exceptions import HTTPError
from six.moves.urllib.parse import parse_qsl
from wechatpy import events, messages, parse_message, replies
from wechatpy.utils import check_signature, WeChatSigner

from ..decorators import message_handler
from ..exceptions import HandleMessageError
from ..models import MessageHandler, Reply, Rule, WeChatMessage
from .bases import WeChatTestCase
from .interceptors import (common_interceptor, wechatapi,
    wechatapi_accesstoken, wechatapi_error)


@message_handler
def debug_handler(message):
    return "success"


@message_handler("test")
def app_only_handler(message):
    return "success"


def forbidden_handler(message):
    return ""


class HandlerTestCase(WeChatTestCase):
    def test_available(self):
        """测试handler有效性"""
        from datetime import timedelta
        from django.utils import timezone

        rule = dict(type=Rule.Type.ALL)
        now = timezone.now()
        day = timedelta(days=1)
        handler_not_begin = self._create_handler(rule,
            name="not_begin", starts=now + day)
        handler_ended = self._create_handler(rule, name="ended",
            ends=now - day)
        handler_disabled = self._create_handler(rule,
            name="disabled", enabled=False)
        handler_available = self._create_handler(rule, name="available",
            starts=now - day, ends=now + day)

        msg = self._wrap_message(messages.TextMessage("abc"))
        self.assertFalse(handler_not_begin.is_match(msg))
        self.assertFalse(handler_ended.is_match(msg))
        self.assertFalse(handler_disabled.is_match(msg))
        self.assertTrue(handler_available.is_match(msg))

        matches = MessageHandler.matches(self.app, msg)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0], handler_available)

    def test_match(self):
        """测试匹配"""
        def _create_rule(type, **kwargs):
            return Rule(type=type, rule=kwargs)

        def _create_msg(type, **kwargs):
            rv = type(dict())
            for k, v in kwargs.items():
                setattr(rv, k, v)
            return rv

        content = "某中文"
        text_message = _create_msg(messages.TextMessage, content=content)
        another_content = "abc"
        another_text_message = _create_msg(messages.TextMessage,
            content=another_content)

        media_id = "media_id"
        url = "http://example.com/foo?bar=1"
        image_message = _create_msg(messages.ImageMessage, media_id=media_id, image=url)

        event_key = "key"
        sub_event = _create_msg(events.SubscribeEvent, key=event_key)
        click_event = _create_msg(events.ClickEvent, key=event_key)
        another_key = "another"
        another_click_event = _create_msg(events.ClickEvent, key=another_key)

        # 所有消息
        rule = _create_rule(Rule.Type.ALL)
        self.assertMatch(rule, text_message)
        self.assertMatch(rule, image_message)

        # 测试类型匹配
        rule = _create_rule(Rule.Type.MSGTYPE, 
            msg_type=Rule.ReceiveMsgType.IMAGE)
        self.assertNotMatch(rule, text_message)
        self.assertMatch(rule, image_message)

        # 测试事件匹配
        rule = _create_rule(Rule.Type.EVENT,
            event=MessageHandler.EventType.SUBSCRIBE)
        self.assertNotMatch(rule, text_message)
        self.assertMatch(rule, sub_event)
        self.assertNotMatch(rule, click_event)

        # 测试指定事件匹配
        rule = _create_rule(Rule.Type.EVENTKEY, 
            event=MessageHandler.EventType.CLICK, key=event_key)
        self.assertNotMatch(rule, text_message)
        self.assertNotMatch(rule, sub_event)
        self.assertMatch(rule, click_event)
        self.assertNotMatch(rule, another_click_event)

        # 测试包含匹配
        rule = _create_rule(Rule.Type.CONTAIN, pattern="中")
        self.assertMatch(rule, text_message)
        self.assertNotMatch(rule, another_text_message)
        self.assertNotMatch(rule, image_message)
        self.assertNotMatch(rule, click_event)

        # 测试相等匹配
        rule = _create_rule(Rule.Type.EQUAL, pattern=content)
        self.assertMatch(rule, text_message)
        self.assertNotMatch(rule, another_text_message)
        self.assertNotMatch(rule, image_message)
        self.assertNotMatch(rule, click_event)

        # 测试正则匹配
        rule = _create_rule(Rule.Type.REGEX, pattern=r"[a-c]+")
        self.assertNotMatch(rule, text_message)
        self.assertMatch(rule, another_text_message)
        self.assertNotMatch(rule, image_message)
        self.assertNotMatch(rule, click_event)

        # 测试handler匹配
        handler3 = self._create_handler(rules=[dict(
            type=Rule.Type.EQUAL,
            rule=dict(
                pattern=content
            )
        ), dict(
            type=Rule.Type.EQUAL,
            rule=dict(
                pattern=another_content
            )
        )], name="3")
        self.assertTrue(handler3.is_match(
            self._wrap_message(text_message)))
        self.assertTrue(handler3.is_match(
            self._wrap_message(another_text_message)))
        self.assertFalse(handler3.is_match(
            self._wrap_message(click_event)))

        # 测试匹配顺序
        handler1 = self._create_handler(rules=[dict(
            type=Rule.Type.EVENTKEY,
            rule=dict(
                event=MessageHandler.EventType.CLICK,
                key=event_key
            )
        )], name="1", weight=5)
        handler2 = self._create_handler(rules=[dict(
            type=Rule.Type.EQUAL,
            rule=dict(
                pattern=content
            )
        )], name="2")
        handler4 = self._create_handler(rules=[dict(
            type=Rule.Type.EVENT,
            rule=dict(
                event=MessageHandler.EventType.CLICK
            )
        )], name="4", weight=-5)
        matches = MessageHandler.matches(
            self.app, self._wrap_message(text_message))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].id, handler2.id)
        matches = MessageHandler.matches(
            self.app, self._wrap_message(click_event))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].id, handler1.id)
        matches = MessageHandler.matches(
            self.app, self._wrap_message(another_click_event))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].id, handler4.id)

    def test_reply(self):
        """测试一般回复"""
        def _create_reply(msg_type, **kwargs):
            return Reply(msg_type=msg_type, content=kwargs)
        sender = "openid"
        message = messages.TextMessage(dict(
            FromUserName=sender,
            content="xyz"
        ))

        # 测试文本回复
        content = "test"
        msg_type = Reply.MsgType.TEXT
        reply = _create_reply(msg_type, content=content)
        obj = reply.normal_reply(message)
        self.assertEqual(obj.target, sender)
        self.assertEqual(obj.type, msg_type)
        self.assertEqual(obj.content, content)

        # 测试图片回复
        media_id = "media_id"
        msg_type = Reply.MsgType.IMAGE
        reply = _create_reply(msg_type, media_id=media_id)
        obj = reply.normal_reply(message)
        self.assertEqual(obj.target, sender)
        self.assertEqual(obj.type, msg_type)
        self.assertEqual(obj.image, media_id)

        # 测试音频回复
        msg_type = Reply.MsgType.VOICE
        reply = _create_reply(msg_type, media_id=media_id)
        obj = reply.normal_reply(message)
        self.assertEqual(obj.target, sender)
        self.assertEqual(obj.type, msg_type)
        self.assertEqual(obj.voice, media_id)

        # 测试视频回复
        title = "title"
        description = "desc"
        msg_type = Reply.MsgType.VIDEO
        reply = _create_reply(msg_type, media_id=media_id, title=title,
            description=description)
        obj = reply.normal_reply(message)
        self.assertEqual(obj.target, sender)
        self.assertEqual(obj.type, msg_type)
        self.assertEqual(obj.media_id, media_id)
        self.assertEqual(obj.title, title)
        self.assertEqual(obj.description, description)
        # 选填字段
        reply = _create_reply(msg_type, media_id=media_id)
        obj = reply.normal_reply(message)
        self.assertEqual(obj.target, sender)
        self.assertEqual(obj.type, msg_type)
        self.assertEqual(obj.media_id, media_id)
        self.assertIsNone(obj.title)
        self.assertIsNone(obj.description)

        # 测试音乐回复
        music_url = "music_url"
        hq_music_url = "hq_music_url"
        msg_type = Reply.MsgType.MUSIC
        reply = _create_reply(msg_type, thumb_media_id=media_id, title=title,
            description=description, music_url=music_url,
            hq_music_url=hq_music_url)
        obj = reply.normal_reply(message)
        self.assertEqual(obj.target, sender)
        self.assertEqual(obj.type, msg_type)
        self.assertEqual(obj.thumb_media_id, media_id)
        self.assertEqual(obj.title, title)
        self.assertEqual(obj.description, description)
        self.assertEqual(obj.music_url, music_url)
        self.assertEqual(obj.hq_music_url, hq_music_url)
        # 选填字段
        reply = _create_reply(msg_type, thumb_media_id=media_id)
        obj = reply.normal_reply(message)
        self.assertEqual(obj.target, sender)
        self.assertEqual(obj.type, msg_type)
        self.assertEqual(obj.thumb_media_id, media_id)
        self.assertIsNone(obj.title)
        self.assertIsNone(obj.description)
        self.assertIsNone(obj.music_url)
        self.assertIsNone(obj.hq_music_url)

        # 测试图文回复
        pass

    def test_multireply(self):
        """测试多回复"""
        reply1 = "abc"
        reply2 = "def"
        replies = [dict(
            msg_type=Reply.MsgType.TEXT,
            content=dict(content=reply1)
        ), dict(
            msg_type=Reply.MsgType.TEXT,
            content=dict(content=reply2)
        )]
        handler_all = self._create_handler(replies=replies,
            strategy=MessageHandler.ReplyStrategy.ALL)
        handler_rand = self._create_handler(replies=replies,
            strategy=MessageHandler.ReplyStrategy.RANDOM)

        # 随机回复
        api = "/cgi-bin/message/custom/send"
        sender = "openid"
        message = messages.TextMessage(dict(
            FromUserName=sender,
            content="xyz"
        ))
        message = self._wrap_message(message)
        with wechatapi_accesstoken(), wechatapi_error(api):
            reply = handler_rand.reply(message)
            self.assertEqual(reply.type, Reply.MsgType.TEXT)
            self.assertEqual(reply.target, sender)
            self.assertIn(reply.content, (reply1, reply2))

        # 回复一条正常消息以及一条客服消息
        counter = dict(calls=0)
        def callback(url, request, response):
            counter["calls"] += 1
            data = json.loads(request.body.decode())
            self.assertEqual(data["text"]["content"], reply2)
            self.assertEqual(data["touser"], sender)
        with wechatapi_accesstoken(), wechatapi(api, dict(errcode=0, errmsg=""), callback):
            reply = handler_all.reply(message)
            self.assertEqual(reply.type, Reply.MsgType.TEXT)
            self.assertEqual(reply.target, sender)
            self.assertEqual(reply.content, reply1)
            self.assertEqual(counter["calls"], 1)

    def test_custom(self):
        """测试自定义回复"""
        from ..models import WeChatApp

        def _get_handler(handler, app=None):
            return self._create_handler(replies=dict(
                msg_type=Reply.MsgType.CUSTOM,
                content=dict(
                    program="wechat_django.tests.test_model_handler." + handler
                )
            ), app=app)

        sender = "openid"
        message = messages.TextMessage(dict(
            FromUserName=sender,
            content="xyz"
        ))
        message = self._wrap_message(message)
        success_reply = "success"
        # 测试自定义回复
        handler = _get_handler("debug_handler")
        reply = handler.reply(message)
        self.assertIsInstance(reply, replies.TextReply)
        self.assertEqual(reply.content, success_reply)

        # 测试未加装饰器的自定义回复
        handler = _get_handler("forbidden_handler")
        self.assertRaises(HandleMessageError, lambda: handler.reply(message))

        # 测试不属于本app的自定义回复
        handler_success = _get_handler("app_only_handler")
        handler_fail = _get_handler("app_only_handler",
            WeChatApp.get_by_name("test1"))
        reply = handler_success.reply(message)
        self.assertIsInstance(reply, replies.TextReply)
        self.assertEqual(reply.content, success_reply)
        message._app = WeChatApp.get_by_name("test1")
        self.assertRaises(HandleMessageError, lambda: handler_fail.reply(message))

    def test_forward(self):
        """测试转发回复"""
        scheme = "http"
        netloc = "example.com"
        path = "/debug"
        url = "{scheme}://{netloc}{path}".format(
            scheme=scheme,
            netloc=netloc,
            path=path
        )

        token = self.app.token
        timestamp = str(int(time.time()))
        nonce = "123456"
        query_data = dict(
            timestamp=timestamp,
            nonce=nonce
        )
        signer = WeChatSigner()
        signer.add_data(token, timestamp, nonce)
        signature = signer.signature
        query_data["signature"] = signature

        sender = "openid"
        content = "xyz"
        xml = """<xml>
        <ToUserName><![CDATA[toUser]]></ToUserName>
        <FromUserName><![CDATA[{sender}]]></FromUserName>
        <CreateTime>1348831860</CreateTime>
        <MsgType><![CDATA[text]]></MsgType>
        <Content><![CDATA[{content}]]></Content>
        <MsgId>1234567890123456</MsgId>
        </xml>""".format(sender=sender, content=content)
        req_url = url + "?" + urlencode(query_data)
        request = RequestFactory().post(req_url, xml, content_type="text/xml")

        message = WeChatMessage.from_request(request, self.app)

        reply_text = "abc"
        def reply_test(url, request):
            self.assertEqual(url.scheme, scheme)
            self.assertEqual(url.netloc, netloc)
            self.assertEqual(url.path, path)

            query = dict(parse_qsl(url.query))
            self.assertEqual(query["timestamp"], timestamp)
            self.assertEqual(query["nonce"], nonce)
            self.assertEqual(query["signature"], signature)
            check_signature(self.app.token, query["signature"], timestamp, nonce)

            msg = parse_message(request.body)
            self.assertIsInstance(msg, messages.TextMessage)
            self.assertEqual(msg.source, sender)
            self.assertEqual(msg.content, content)
            reply = replies.create_reply(reply_text, msg)
            return response(content=reply.render())

        handler = self._create_handler(replies=dict(
            msg_type=Reply.MsgType.FORWARD,
            content=dict(url=url)
        ))

        with common_interceptor(reply_test):
            reply = handler.reply(message)
            self.assertIsInstance(reply, replies.TextReply)
            self.assertEqual(reply.content, reply_text)
            self.assertEqual(reply.target, sender)

        def bad_reply(url, request):
            return response(404)

        with common_interceptor(bad_reply):
            self.assertRaises(HTTPError, lambda: handler.reply(message))

    def test_send(self):
        """测试客服回复"""
        def _create_reply(msg_type, **kwargs):
            return Reply(msg_type=msg_type, content=kwargs)
        sender = "openid"
        message = messages.TextMessage(dict(
            FromUserName=sender,
            content="xyz"
        ))
        message = self._wrap_message(message)

        # 空消息转换
        empty_msg = replies.EmptyReply()
        empty_str = ""
        self.assertIsNone(Reply.reply2send(empty_msg)[0])
        self.assertIsNone(Reply.reply2send(empty_str)[0])

        client = self.app.client.message

        # 文本消息转换
        content = "test"
        msg_type = Reply.MsgType.TEXT
        reply = _create_reply(msg_type, content=content).reply(message)
        funcname, kwargs = Reply.reply2send(reply)
        self.assertTrue(hasattr(client, funcname))
        self.assertEqual(funcname, "send_text")
        self.assertEqual(reply.content, kwargs["content"])

        # 图片消息转换
        media_id = "media_id"
        msg_type = Reply.MsgType.IMAGE
        reply = _create_reply(msg_type, media_id=media_id).reply(message)
        funcname, kwargs = Reply.reply2send(reply)
        self.assertTrue(hasattr(client, funcname))
        self.assertEqual(funcname, "send_image")
        self.assertEqual(reply.media_id, kwargs["media_id"])

        # 声音消息转换
        msg_type = Reply.MsgType.VOICE
        reply = _create_reply(msg_type, media_id=media_id).reply(message)
        funcname, kwargs = Reply.reply2send(reply)
        self.assertTrue(hasattr(client, funcname))
        self.assertEqual(funcname, "send_voice")
        self.assertEqual(reply.media_id, kwargs["media_id"])

        # 视频消息转换
        title = "title"
        description = "desc"
        msg_type = Reply.MsgType.VIDEO
        reply = _create_reply(msg_type, media_id=media_id, title=title,
            description=description).reply(message)
        funcname, kwargs = Reply.reply2send(reply)
        self.assertTrue(hasattr(client, funcname))
        self.assertEqual(funcname, "send_video")
        self.assertEqual(reply.media_id, kwargs["media_id"])
        self.assertEqual(reply.title, kwargs["title"])
        self.assertEqual(reply.description, kwargs["description"])
        # 选填字段
        reply = _create_reply(msg_type, media_id=media_id).reply(message)
        funcname, kwargs = Reply.reply2send(reply)
        self.assertTrue(hasattr(client, funcname))
        self.assertEqual(funcname, "send_video")
        self.assertEqual(reply.media_id, kwargs["media_id"])
        self.assertIsNone(kwargs["title"])
        self.assertIsNone(kwargs["description"])

        # 音乐消息转换
        music_url = "music_url"
        hq_music_url = "hq_music_url"
        msg_type = Reply.MsgType.MUSIC
        reply = _create_reply(msg_type, thumb_media_id=media_id, title=title,
            description=description, music_url=music_url,
            hq_music_url=hq_music_url).reply(message)
        funcname, kwargs = Reply.reply2send(reply)
        self.assertTrue(hasattr(client, funcname))
        self.assertEqual(funcname, "send_music")
        self.assertEqual(reply.thumb_media_id, kwargs["thumb_media_id"])
        self.assertEqual(reply.music_url, kwargs["url"])
        self.assertEqual(reply.hq_music_url, kwargs["hq_url"])
        self.assertEqual(reply.title, kwargs["title"])
        self.assertEqual(reply.description, kwargs["description"])
        # 选填字段
        reply = _create_reply(msg_type, thumb_media_id=media_id).reply(message)
        funcname, kwargs = Reply.reply2send(reply)
        self.assertTrue(hasattr(client, funcname))
        self.assertEqual(funcname, "send_music")
        self.assertEqual(reply.thumb_media_id, kwargs["thumb_media_id"])
        self.assertIsNone(kwargs["url"])
        self.assertIsNone(kwargs["hq_url"])
        self.assertIsNone(kwargs["title"])
        self.assertIsNone(kwargs["description"])

        # 图文消息转换
        pass

        # 确认消息发送
        handler = self._create_handler(replies=dict(
            msg_type=Reply.MsgType.TEXT,
            content=dict(content=content)
        ))

        def callback(url, request, response):
            data = json.loads(request.body.decode())
            self.assertEqual(data["touser"], sender)
            self.assertEqual(data["msgtype"], Reply.MsgType.TEXT)
            self.assertEqual(data["text"]["content"], content)

        with wechatapi_accesstoken(), wechatapi("/cgi-bin/message/custom/send", dict(
            errcode=0
        ), callback):
            handler.replies.all()[0].send(message)

    def test_sync(self):
        """测试同步"""
        pass

    def assertMatch(self, rule, message):
        self.assertTrue(rule._match(message))

    def assertNotMatch(self, rule, message):
        self.assertFalse(rule._match(message))
    
    def _wrap_message(self, message):
        return WeChatMessage(
            _app=self.app,
            _message=message
        )

    def _create_handler(self, rules=None, name="", replies=None, app=None, **kwargs):
        """:rtype: MessageHandler"""
        handler = MessageHandler.objects.create(
            app=app or self.app,
            name=name,
            **kwargs
        )

        if not rules:
            rules = [dict(type=Rule.Type.ALL)]
        if isinstance(rules, dict):
            rules = [rules]
        if isinstance(replies, dict):
            replies = [replies]
        replies = replies or []
        Rule.objects.bulk_create([
            Rule(handler=handler, **rule)
            for rule in rules
        ])
        Reply.objects.bulk_create([
            Reply(handler=handler, **reply)
            for reply in replies
        ])

        return handler
