# WeChat-Django

**WeChat-Django**旨在为接入微信公众平台的django开发者提供便捷的微信功能封装及最基本的[后台管理支持](docs/admin.md).

项目官方地址: https://github.com/Xavier-Lam/wechat-django

本拓展基于[wechatpy](https://github.com/jxtech/wechatpy) ,支持的最低django版本为1.11.

目前没有使用在生产环境使用本项目的案例,编写了部分单元测试,只在*python3.4 django-1.11, python2.7 django-1.11, python3.4 django-2.0* 下进行了一部分简单的徒手测试.

0.1.0只是一个预览版本,可能存在较多bug,并且有api及数据结构变更可能,欢迎贡献代码

[TOC]

## 功能
* 公众号管理
* 同步用户及用户查看,备注
* 菜单同步,查看及发布
* 同步公众号自动回复,管理自动回复,转发和自定义自动回复业务,接收消息日志
* 永久素材同步及查看
* 图文同步及查看
* 服务号网页授权
* 主动调用微信api封装
* 微信网页授权
* 后台权限管理

## 安装及配置
### 初次安装
1. 安装**pip install wechat-django[cryptography]** 或 **pip install wechat-django[pycrypto]**
2. 在settings.py的**INSTALLED_APPS中添加wechat_django**
3. 运行**manage.py migrate wechat_django** 来更新数据库结构
4. 在urls.py 中引入wechat_django.urls, 将其配置到urlpatterns中

至此,您已可以开始轻松使用wechat_django.项目尚未提供具体的使用文档,如需客制化需求,烦请先阅读代码

### 直接加入项目
如果想将拓展安装到自己的项目下,并且自己改写本拓展,可采用pip install -e 安装
1. 在你的项目的根目录运行**pip install -e git+https://github.com/Xavier-Lam/wechat-django#egg=wechat-django[cryptography] --src ./wechat_django**
2. 执行上述2-4

### 更新
1. 运行**pip install -U wechat-django**
2. 运行**python manage.py migrate wechat_django** 来更新数据库结构

### 配置
一般而言,默认配置足以满足需求

| 参数名 | 默认值 | 说明 |
| --- | --- | --- |
| WECHAT_ADMINSITE | "django.contrib.admin.site" | 需要注册微信后台的AdminSite对象字符串 |
| WECHAT_SESSIONSTORAGE | "django.core.cache.cache" | 存储微信accesstoken等使用的Storage对象字符串,或一个接收 `wechat_django.models.WeChatApp` 对象并返回 [`wechatpy.session.SessionStorage`](https://wechatpy.readthedocs.io/zh_CN/master/quickstart.html#id10) 对象的callable或指向该callable的字符串 | 
| WECHAT_WECHATCLIENTFACTORY | "wechat_django.utils.wechat.get_wechat_client" | 接受一个 `wechat_django.models.WeChatApp` 对象并返回指向一个 [`wechat_django.wechat.WeChatClient`](https://wechatpy.readthedocs.io/zh_CN/master/_modules/wechatpy/client.html) 子类的字符串,当默认的WeChatClient不能满足需求时,可通过修改WeChatClient生成工厂来定制自己的WeChatClient类,比如说某个公众号获取accesstoken的方式比较特殊,可以通过继承WeChatClient并复写fetch_access_token方法来实现 | 
| WECHAT_MESSAGETIMEOFFSET | 180 | 微信请求消息时,timestamp与服务器时间差超过该值的请求将被抛弃 |
| WECHAT_MESSAGENOREPEATNONCE | True | 是否对微信消息防重放检查 默认检查 |

### 日志
| logger | 说明 |
| --- | --- |
| wechat.admin.{appname} | admin异常日志 最低级别warning |
| wechat.api.{appname} | api日志 最低级别debug |
| wechat.handler.{appname} | 消息处理日志 最低级别debug |
| wechat.oauth.{appname} | 网页授权异常日志 最低级别warning |
| wechat.views.{appname} | view异常日志(如素材代理) 最低级别warning |

### 注意事项
* 框架默认采用django的cache管理accesstoken,如果有多个进程,或是多台机器部署,请确保所有worker使用公用cache以免造成token争用,如果希望不使用django的cache管理accesstoken,可以在配置项中定义SessionStorage
* 请确保在https环境下部署,否则有secretkey泄露的风险

## 部分功能使用说明
### 网页授权
可通过`wechat_django.oauth.wechat_auth`装饰器进行网页授权,授权后,request将被附上一个名为wechat的`wechat_django.oauth.WeChatOAuthInfo` 对象,可通过 request.wechat.user 拿到`wechat_django.models.WeChatUser`实例,通过 request.wechat.app 拿到`wechat_django.models.WeChatApp`实例,以下是一个基本示例

    from wechat_django.oauth import wechat_auth

    @wechat_auth("your_app_name")
    def your_view(request, *args, **kwargs):
        """:type request: wechat_django.models.request.WeChatOAuthRequest"""
        user = request.wechat.user

对于默认重定向行为不满意的,可以自定义response,具体的参数说明参见`wechat_django.oauth.wechat_auth`装饰器的docstring


### 主动调用微信api
    from wechat_django.models import WeChatApp
    app = WeChatApp.get_by_name("your app name")
    data = app.client.user.get_followers()

具体client的使用方式,请移步[wechatpy文档](https://wechatpy.readthedocs.io/zh_CN/master/client/index.html)

### 自定义微信回复
在后台配置自定义回复,填写自定义回复处理代码的路径,代码须由 `wechat_django.decorators.message_handler` 装饰对应的方法接收一个 `wechat_django.models.WeChatMessageInfo` 对象,返回字符串或一个 [`wechatpy.replies.BaseReply`](https://wechatpy.readthedocs.io/zh_CN/master/replies.html) 对象

    from wechat_django.decorators import message_handler

    @message_handler
    def custom_business(message):
        """
        :type message: wechat_django.models.WeChatMessageInfo
        """
        user = message.user
        msg = message.message
        text = "hello, {0}! we received a {1} message.".format(
            user, msg.type)
        return TextReply(content=text.encode())

## 后台使用简介
参见[管理后台使用简介](docs/admin.md) 文档

## 示例项目
可参考[本项目sample文件夹](sample)

## TODOS:
* 完善单元测试
* app层面的message log和reply log
* 后台表单验证
* 后台确认页

### 计划的功能
* accesstoken开放给第三方并对接第三方accesstoken
* 用户分组管理
* 消息响应日志/对话
* 客服消息
* 清理及保护永久素材
* 将部分actions改为object-tool
* 回复及一些查询缓存
* 菜单导入导出

## ChangeLog
### 0.1.0


Xavier-Lam@NetDragon