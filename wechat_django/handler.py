# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
import time

from django.core.cache import cache
from django.http import response
from wechatpy import parse_message, replies
from wechatpy.crypto import WeChatCrypto
from wechatpy.exceptions import InvalidSignatureException
from wechatpy.utils import check_signature

from . import settings
from .decorators import wechat_route
from .models import MessageHandler, WeChatApp
from .utils.web import get_ip

__all__ = ("handler", )


@wechat_route("$", methods=("GET", "POST"))
def handler(request, app):
    """接收及处理微信发来的消息
    :type request: django.http.request.HttpRequest
    """
    logger = logging.getLogger("wechat.handler.{0}".format(app.name))
    log_args = dict(params=request.GET, body=request.body,
        ip=get_ip(request))
    logger.debug("received: {0}".format(log_args))
    if not app.interactable():
        return response.HttpResponseNotFound()

    try:
        # 防重放检查
        nonce_key = "wx:m:n:{0}".format(request.GET["signature"])
        nonce = request.GET["nonce"]
        if settings.MESSAGENOREPEATNONCE and cache.get(nonce_key) == nonce:
            logger.debug("repeat request: {0}".format(log_args))
            return response.HttpResponseBadRequest()

        timestamp = request.GET["timestamp"]
        time_diff = int(timestamp) - time.time()

        # 检查timestamp
        if abs(time_diff) > settings.MESSAGETIMEOFFSET:
            logger.debug("time error: {0}".format(log_args))
            return response.HttpResponseBadRequest()

        check_signature(
            app.token,
            request.GET["signature"],
            timestamp,
            nonce
        )

        # 防重放
        settings.MESSAGENOREPEATNONCE and cache.set(
            nonce_key, nonce, settings.MESSAGETIMEOFFSET + time_diff)

        if request.method == "GET":
            return request.GET["echostr"]
    except (KeyError, InvalidSignatureException):
        logger.debug("received an unexcepted request: {0}".format(log_args),
            exc_info=True)
        return response.HttpResponseBadRequest()

    raw = request.body
    try:
        if app.encoding_mode == WeChatApp.EncodingMode.SAFE:
            crypto = WeChatCrypto(
                app.token,
                app.encoding_aes_key,
                app.appid
            )
            raw = crypto.decrypt_message(
                raw,
                request.GET["signature"],
                request.GET["timestamp"],
                request.GET["nonce"]
            )
        msg = parse_message(raw)
    except:
        logger.error(
            "decrypt message failed: {0}".format(log_args),
            exc_info=True
        )
        return ""

    msg.raw = raw
    msg.request = request
    handlers = MessageHandler.matches(app, msg)
    if not handlers:
        logger.debug("handler not found: {0}".format(log_args))
        return ""
    handler = handlers[0]
    try:
        reply = handler.reply(msg)
        if not reply or isinstance(reply, replies.EmptyReply):
            logger.debug("empty response: {0}".format(log_args))
            return ""
        xml = reply.render()
        log_args["response"] = xml
        logger.debug("response: {0}".format(log_args))
    except:
        logger.warning("an error occurred when response: {0}".format(
            log_args), exc_info=True)
        return ""
    return response.HttpResponse(xml, content_type="text/xml")
