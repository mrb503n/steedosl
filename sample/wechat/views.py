from django.conf.urls import url
from django.http.response import HttpResponse

from wechat_django.models import WeChatSNSScope, WeChatUser
from wechat_django.oauth import wechat_auth
from wechatpy.replies import TextReply

#!wechat_django oauth示例
@wechat_auth("debug")
def oauth(request):
    return HttpResponse(str(request.wechat.user).encode())

#!wechat_django 自定义业务示例
def custom_business(message):
    """
    :type message: wechat_django.models.WeChatMessage
    """
    user = message.user
    msg = message.message
    text = "hello, {0}! we received a {1} message.".format(
        user, msg.type
    )
    return TextReply(content=text.encode())