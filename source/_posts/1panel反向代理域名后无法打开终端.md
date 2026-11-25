---
title: 1panel反向代理域名后无法打开终端
date: 2026-11-18 17:14:53
tags: 
  - 1panel
  - 反向代理
---

因为服务器面板的增多，很多时候会出现一个问题在于，有时候需要多服务器协同修改，会同时多开几个面板，容易引发问题。如果全部面板都用 IP 命名，很难界定哪一个面板对应的是哪一台服务器。

于是我开始给所有的面板套上了域名，仍然是通过我最爱的反向代理的方式访问

```Bash
location ^~ / {
    proxy_pass http://*.*.*.*:2999; 
    proxy_set_header Host $proxy_host;
    proxy_set_header X-Forwarded-Host "";
    proxy_set_header Forwarded "";
    proxy_set_header X-Real-IP $remote_addr; 
    proxy_set_header REMOTE-HOST $remote_addr; 
    proxy_set_header Upgrade $http_upgrade; 
    proxy_set_header Connection $http_connection; 
    proxy_set_header X-Forwarded-Proto $scheme; 
    proxy_set_header X-Forwarded-Port $server_port; 
    proxy_http_version 1.1; 
    add_header X-Cache $upstream_cache_status; 
    proxy_ssl_server_name off; 
    proxy_ssl_name $proxy_host; 
}
```

但是我遇到了一个小问题：以这种方式访问的面板，面板上网页自带的终端功能无法正常使用，会直接显示 `disconnected`

![image\.png](https://picgocloud.com/m/8prdf4vz/813720f2-5153-4da0-9b4d-d0de1969c7cb.png)

不用想，肯定是反向代理的某些地方出现了问题，于是查找相关资料

在 1Panel 的官方网站上找到了关于反向代理的一些资料，但是根据官网这个案例进行修改并不能解决问题。

https://1panel\-dev\.github\.io/docs/v2/faq/system\_function/

因为这个配置其实已经包含在 1Panel 设置的反向代理默认配置中了。也就是说，1Panel 的反向代理默认就是这样，不需要手动重新修改。



接下来就尝试使用 F12，看一下有没有可用的详细信息

![image\.png](https://picgocloud.com/m/8prdf4vz/cac578ef-1284-4285-bd10-94f00628cec0.png)

可以看到，在打开终端的时候，确实是发送了一个 WebSocket 的请求，但是很遗憾，直接被中断了，并且没有任何可用的反馈信息。



接下来有两种可用的排查思路：一个是 1Panel 的问题，另外一个是 SSH 的问题。

但考虑到 1Panel 不太可能在前端塞一整个完整的 SSH，此处感觉更像是 1Panel 后端在服务器本地尝试连接，然后通过 WebSocket 将实时数据发出来。所以优先查看 1Panel 的问题，可以看到最里面 1Panel 的 WebSocket 请求路径，让 AI 根据这个路径进行排查。



果然排查到了一些问题。在 [PR13953](https://github.com/1Panel-dev/1Panel/pull/13953/changes) 中为面板的终端添加了 Origin 和 Host 的校验，如果校验失败就直接返回 403。

但我们的 反向代理 只重写了 Host，没有重写 Origin，刚好匹配这一个问题，所以进行简单修改之后重新启动试试。

```YAML
proxy_set_header Origin $proxy_host;
```

发现重载失败，Origin 头要加 Scheme 前缀

```YAML
proxy_set_header Origin http://$proxy_host;
```

解决