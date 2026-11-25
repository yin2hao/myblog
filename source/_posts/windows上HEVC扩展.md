---
title: windows上HEVC扩展
date: 2026-11-8 19:10:35
tags:
  - windows
  - HEVC
---

## Windows上HEVC扩展

而众所周知，Windows上面HEVC格式编码支持是要爆米的，7块钱。

![image\.png](https://picgocloud.com/m/22feadc2-73c3-49ed-85f6-dcba68bbf784.png)

又众所周知，虽然要爆米，但有一个绕过的方法，就是`来自设备制造商的 HEVC 视频扩展`

![image\.png](https://picgocloud.com/m/4bcc0dcd-8787-4649-925a-23651621eeea.png)

我在测试自己的项目的时候，我发现部分视频出现了画面无法显示的 bug。~~DEBUG~~问 AI 后发现是该视频编码为HEVC，而我的电脑上没有HEVC编码扩展，导致无法正常的解码播放。

![image\.png](https://picgocloud.com/m/776a9aa6-8b7c-4164-82a8-191746e6b5da.png)

于是我去微软商城下载`来自设备制造商的 HEVC 视频扩展`，发现微软商城提示不能下载，与设备不兼容

但是问题是，我当前的电脑系统是 Windows 11 LTSC 版本，在重装到 LTSC 之前，我是 Windows 11 24H2。在Windows 11 24H2 的时候，我是能够正常安装`来自设备制造商的 HEVC 视频扩展`的，因此我的电脑设备硬件肯定是满足的，问题只可能是出现在软件

于是我想在绕过微软商城，直接找到相关的安装包。因为`Apple Store`、`Google Store`都有绕过商城直接获取安装包的方法，于是我上网一搜

https://store.rg-adguard.net/

![image\.png](https://picgocloud.com/m/9a5cfb1e-4509-43e5-8243-0dda1b2f75c5.png)

于是我们获取到了两个版本的`基于设备制造商提供的HEVC视频扩展`，我先尝试下载了最新版本

![image\.png](https://picgocloud.com/m/0b2d84f0-ba8d-493b-a89f-6c1c3ebabc05.png)

最新版本安装的时候提示安装失败，查看安装错误语句发现是系统版本不匹配。我的是`Windows 11 LTSC`版本，它要求的操作系统版本为`10.0.26200.0`及以上，我的是`10.0.26100.9168`不符合要求

![image\.png](https://picgocloud.com/m/128ee248-997e-4450-9c75-2f38071bb9ac.png)

这简单，直接换成老版本的安装包尝试安装

![image\.png](https://picgocloud.com/m/71095f61-a749-40f4-96e8-f586be07d9b3.png)

再打开浏览器，已经可以成功了，全剧终

![image\.png](https://picgocloud.com/m/1583a66d-18f8-4d8b-a60e-f157d0789543.png)

https://jackparker.co.uk/blog/generate-direct-microsoft-store-download-links-via-an-undocumented-api/