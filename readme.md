# wechat_django

本拓展基于[wechatpy](https://github.com/jxtech/wechatpy) ,旨在为有在django框架下接入微信公众平台的开发者提供便利.支持的最低django版本为1.11.

[TOC]

## 功能
* 最基本的公众号管理
* 同步用户及用户查看,备注
* 最基本的菜单管理
* 同步公众号自动回复,管理自动回复,转发自动回复和自定义自动回复业务
* 素材同步及查看
* 图文同步及查看
* 服务号网页授权
* 主动调用微信api封装

目前没有使用在生产环境的案例,只在python3.4 django-1.11 下进行了徒手测试

## 安装

1. 安装
    
    pip install wechat_django

2. 在settings.py的**INSTALLED_APPS中添加wechat_django**
3. 运行manage.py migrate wechat_django 来更新数据库结构
4. 在urls.py 中引入wechat_django.views.urls, 将其配置到urlpatterns中

至此,您已可以开始轻松使用wechat_django.项目尚未提供具体的使用文档,如需客制化需求,烦请先阅读代码

## 配置
| 参数名 | 默认值 | 说明 |
| --- | --- | --- |
| WECHAT_ADMINSITE | "django.contrib.admin.site" | 需要注册微信后台的AdminSite对象字符串 |
| WECHAT_SESSIONSTORAGE | "django.core.cache.cache" | 存储微信accesstoken等使用的Storage对象字符串,或一个接收 `wechat_django.models.WeChatApp` 对象并返回 [`wechatpy.session.SessionStorage`](https://wechatpy.readthedocs.io/zh_CN/master/quickstart.html#id10) 对象的callable或指向该callable的字符串 | 
| WECHAT_WECHATCLIENTFACTORY | "wechat_django.wechat.get_wechat_client" | 接受一个 `wechat_django.models.WeChatApp` 对象并返回指向一个 [`wechat_django.wechat.WeChatClient`](https://wechatpy.readthedocs.io/zh_CN/master/_modules/wechatpy/client.html) 子类的字符串,当默认的WeChatClient不能满足需求时,可通过修改WeChatClient生成工厂来定制自己的WeChatClient类,比如说某个公众号获取accesstoken的方式比较特殊,可以通过继承WeChatClient并复写fetch_access_token方法来实现 | 

## 部分功能使用说明
### 网页授权

### 主动调用微信api
    from wechat_django.models import WeChatApp
    app = WeChatApp.get_by_name("your app name")
    data = app.client.user.get_followers()

具体client的使用方式,请移步[wechatpy文档](https://wechatpy.readthedocs.io/zh_CN/master/client/index.html)

## 预览

## 日志
| logger | 说明 |
| --- | --- |
| wechat.admin.{appid} | admin异常日志 最低级别warning |
| wechat.api.req.{appid} | api请求日志 级别debug |
| wechat.api.resp.{appid} | api响应日志 级别debug |
| wechat.api.excs.{appid} | api异常日志 最低级别warning |
| wechat.handler.{appid} | 消息处理日志 最低级别debug |
| wechat.views.{appid} | view异常日志(如素材代理) 最低级别warning |

## TODOS:
* 本地化
* 用户分组管理
* 移除未使用的永久素材
* 将部分actions改为object-tool
* 转发多回复
* 回复缓存
* 权限管理
* 单元测试
* 文档