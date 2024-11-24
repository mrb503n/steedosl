import math
import re
            
from django.db import models as m, transaction
from django.utils.translation import ugettext as _

from .. import utils
from . import WeChatApp

class WeChatUser(m.Model):
    class Gender(object):
        UNKNOWN = "0"
        MALE = "1"
        FEMALE = "2"
    
    class SubscribeScene(object):
        ADD_SCENE_SEARCH = "ADD_SCENE_SEARCH" # 公众号搜索
        ADD_SCENE_ACCOUNT_MIGRATION = "ADD_SCENE_ACCOUNT_MIGRATION" # 公众号迁移
        ADD_SCENE_PROFILE_CARD = "ADD_SCENE_PROFILE_CARD" # 名片分享
        ADD_SCENE_QR_CODE = "ADD_SCENE_QR_CODE" # 扫描二维码
        ADD_SCENE_PROFILE_LINK = "ADD_SCENEPROFILE LINK" # 图文页内名称点击
        ADD_SCENE_PROFILE_ITEM = "ADD_SCENE_PROFILE_ITEM" # 图文页右上角菜单
        ADD_SCENE_PAID = "ADD_SCENE_PAID" # 支付后关注
        ADD_SCENE_OTHERS = "ADD_SCENE_OTHERS" # 其他

    app = m.ForeignKey(WeChatApp, on_delete=m.CASCADE,
        related_name="users", null=False, editable=False)
    openid = m.CharField(_("openid"), max_length=36, null=False)
    unionid = m.CharField(_("unionid"), max_length=36, null=True)

    nickname = m.CharField(_("nickname"), max_length=24, null=True)
    sex = m.SmallIntegerField(_("gender"), choices=utils.enum2choices(Gender), 
        null=True)
    headimgurl = m.CharField(_("avatar"), max_length=256, null=True)
    city = m.CharField(_("city"), max_length=24, null=True)
    province = m.CharField(_("province"), max_length=24, null=True)
    country = m.CharField(_("country"), max_length=24, null=True)
    language = m.CharField(_("language"), max_length=24, null=True)

    subscribe = m.NullBooleanField(_("is subscribed"), null=True)
    subscribe_time = m.IntegerField(_("subscribe time"), null=True)
    subscribe_scene = m.CharField(_("subscribe scene"), max_length=32,
        null=True, choices=utils.enum2choices(SubscribeScene))
    qr_scene = m.IntegerField(_("qr scene"), null=True)
    qr_scene_str = m.CharField(_("qr_scene_str"), max_length=64, null=True)

    remark = m.TextField(_("remark"), blank=True, null=True)
    groupid = m.IntegerField(_("group id"), null=True)

    created = m.DateTimeField(_("created"), auto_now_add=True)
    updated = m.DateTimeField(_("updated"), auto_now=True)
    
    class Meta(object):
        ordering = ("app", "-created")
        unique_together = (("app", "openid"), ("app", "unionid"))

    def avatar(self, size=132):
        assert size in (0, 46, 64, 96, 132)
        return self.headimgurl and re.sub(r"\d+$", str(size), self.headimgurl)

    @classmethod
    def sync(cls, app, all=False, detail=True):
        rv = []
        first_openid = None
        if not all:
            try:
                user = cls.objects.filter(app=app).latest("created")
            except cls.DoesNotExist:
                user = None
            first_openid = user and user.openid
        for openids in cls._iter_followers_list(app, first_openid):
            if detail:
                allowed_fields = list(map(lambda o: o.name, cls._meta.fields))
                user_dicts = map(
                    lambda o: {k: v for k, v in o.items() if k in allowed_fields},
                    app.client.user.get_batch(openids))
            else:
                user_dicts = map(lambda openid: dict(openid=openid), openids)
            params = map(lambda o: dict(app=app, openid=o["openid"], defaults=o), 
                user_dicts)
            with transaction.atomic():
                users = map(lambda kwargs: cls.objects.update_or_create(**kwargs)[0], 
                    params)
            rv.extend(users)
        return rv

    @classmethod
    def _iter_followers_list(cls, app, first_user_id=None):
        count = 100
        while True:
            follower_data = app.client.user.get_followers(first_user_id)
            first_user_id = follower_data["next_openid"]
            if "data" not in follower_data:
                raise StopIteration
            openids = follower_data["data"]["openid"]
            pages = math.ceil(len(openids)/count)
            for page in range(pages):
                yield openids[page*count: page*count+count]
            if not first_user_id:
                raise StopIteration
        
    def __str__(self):
        return "{nickname}({openid})".format(nickname=self.nickname or "",
            openid=self.openid)

# class WeChatUserTag(object):
#     user = m.ForeignKey(WeChatApp, on_delete=m.CASCADE,
#         related_name="users", null=False, editable=False)