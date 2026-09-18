---
layout: layout
title: docker pull命令通过镜像源下载偶发过慢问题
date: 2026-08-23 17:03:54
tags: docker
---

### 背景

现在有两台服务器，一台是位于中国成都内地的 ESC 实例 A\(20M带宽\)

另外一台是位于吉隆坡的轻量应用服务器 B （峰值200M带宽）

在这之前，我比较喜欢使用 1Panel 面板可视化管理服务器。1Panel 面板是基于 Docker 的管理面板，它的应用体系基本依靠 Docker Compose。

1Panel 面板官方提供了一个应用商城。该应用商城分为两个部分，一个是官方提供的应用，另外一个部分是可以从本地的目录中同步应用。鉴于官方提供的应用较少且覆盖不完整，我配置了[第三方应用商城](https://github.com/QYG2297248353/appstore-1panel)以及个人的 Docker Compose 编排，每天定时更新。

![OMMKr.png](https://a1.ax1x.com/2026/08/23/OMMKr.png)

由于新买的服务器在中国成都，受到网络条件制约，目前国内主流的 Docker 镜像源要么收费，要么相对不稳定，因此，我在位于吉隆坡的服务器 B 使用 Docker 官方的 [Registry](https://hub.docker.com/_/registry) 搭建了简单的 Docker 镜像源，当接到拉取请求时，吉隆坡的服务器先从 DockerHub 拉取镜像到本地，再发送给请求者，镜像本机缓存 24 小时。

![OMJQ4.png](https://a1.ax1x.com/2026/08/23/OMJQ4.png)

准备安装的 `astrbot` \+ `napcat` 的容器编排如下。

```Bash
networks:
  1panel-network:
    external: true

services:
  napcat:
    image: mlikiowa/napcat-docker:v4.18.18
    container_name: napcat-${CONTAINER_NAME}
    restart: always
    networks:
      - 1panel-network
    ports:
      - ${PANEL_APP_PORT_NAPCAT}:6099
    mac_address: ${NAPCAT_MAC_ADDRESS:-02:42:ac:11:00:02}
    env_file:
      - ${GLOBAL_ENV_FILE:-/etc/1panel/envs/global.env}
      - ${ENV_FILE:-/etc/1panel/envs/default.env}
    volumes:
      - ${ASTRBOT_ROOT_PATH}/data:/AstrBot/data
      - ${ASTRBOT_ROOT_PATH}/ntqq:/app/.config/QQ
    environment:
      - TZ=Asia/Shanghai
      - MODE=astrbot
      - NAPCAT_UID=${NAPCAT_UID:-1000}
      - NAPCAT_GID=${NAPCAT_GID:-1000}
  astrbot:
    image: soulter/astrbot:v4.27.2
    container_name: ${CONTAINER_NAME}
    labels:
      createdBy: "Apps"
    restart: always
    networks:
      - 1panel-network
    ports:
      - ${PANEL_APP_PORT_HTTP}:6185
      - ${PANEL_APP_PORT_QQ_WH}:6199
      - ${PANEL_APP_PORT_QQ_API}:6196
      - ${PANEL_APP_PORT_WECOM}:6195
      - ${PANEL_APP_PORT_WECHAT}:11451
    env_file:
      - ${GLOBAL_ENV_FILE:-/etc/1panel/envs/global.env}
      - ${ENV_FILE:-/etc/1panel/envs/default.env}
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - ${ASTRBOT_ROOT_PATH}/data:/AstrBot/data
      - ${ASTRBOT_ROOT_PATH}/ntqq:/app/.config/QQ
      - ${ASTRBOT_ROOT_PATH}/napcat/config:/app/napcat/config
    environment:
      - TZ=Asia/Shanghai

```

可以看到，这一个编排中有两个容器

一个容器是`mlikiowa/napcat-docker:v4.18.18` 

另外一个容器是`soulter/astrbot:v4.27.2`

### 问题出现

我在中国成都的内地服务器中从 1Panel 的应用商城安装，底层仍然是容器编排，暴露出的信息如下

![OMzAQ.png](https://a1.ax1x.com/2026/08/23/OMzAQ.png)

![OMdEJ.png](https://a1.ax1x.com/2026/08/23/OMdEJ.png)

拉取的实时网络:

![OMxzK.png](https://a1.ax1x.com/2026/08/23/OMxzK.png)

可以看到实时的网速只有 75KB 每秒左右，很慢

但是拉取其他的镜像，比如 nacos

![OMT1Z.png](https://a1.ax1x.com/2026/08/23/OMT1Z.png)

速度就是正常的 10MB/s。因此应该不是成都服务器的问题（但是我服务器不是只有 20M 吗？服务器购买的时候的带宽，应该是指的出口带宽，入口带宽应该是动态的。但根据[阿里云官方文档](https://help.aliyun.com/zh/ecs/user-guide/network-bandwidth)，出口带宽理论应该与入口带宽保持一致，下限为 20 Mbps）



手动运行 `docker compose pull` 命令拉取镜像

![OMc8c.png](https://a1.ax1x.com/2026/08/23/OMc8c.png)

![OM03O.png](https://a1.ax1x.com/2026/08/23/OM03O.png)

12\.05 MB/s，拉取速度一切正常

会不会是两台服务器之间通信的问题？在此使用 iperf3 进行服务器间测速：

![OM2om.png](https://a1.ax1x.com/2026/08/23/OM2om.png)

可见两台服务器之间的连接速度是一切正常的，达到了（甚至超过了）理论峰值速度。因此理论上应该不是两台服务器之间的通信速率问题。



那可能是 1panel 面板的问题。在此之前， 1panel 面板在我的理解中一直是依赖 docker，通过 `Docker compose `编排安装的应用。有没有可能它在里面添加了自己的小巧思，修改了部分逻辑呢？
感谢万能的 [chatgpt](https://chatgpt.com/share/6a82c7e6-d32c-83ea-91e6-66227023ddc7) ，直接阅读 1panel 面板的源码和 pr 分析相关的信息，让我这个完全不会 go 语言的也能完成分析

简单来说，在服务器中，docker 可以简单理解成 `docker engine` 和 `docker cli`两部分。其中直接在命令行输入的 `docker pull` 命令，会唤起 `docker cli`，`docker cli`再通过 API 向 `docker engine` 发送拉取指令，由 `docker engine` 实际拉取。在拉取过程之中，`docker engine` 会实时向 `docker cli` 反馈下载进度，并打印在控制台中。

使用 `docker compose pull` 指令手动拉取目标编排，`docker cli` 会默认同时拉取两个镜像，两个镜像的拉取之间是并行的。

如果使用 1panel 安装应用，对于一个包含多个镜像的 docker compose 编排，面板会先解析其中包含的镜像，再通过串行的方式逐个拉取。

比如当前编排中两个镜像，`mlikiowa/napcat-docker:v4.18.18` 和`soulter/astrbot:v4.27.2`，面板会先拉取`mlikiowa/napcat-docker:v4.18.18` ，在该镜像拉取完成之后再开始拉取`soulter/astrbot:v4.27.2`。

与 AI 求证，并且简单翻阅源码之后，发现面板并非直接简单使用 `docker pull` 命令拉取，而是直接与 `docker engine` 通信。更准确的讲，在 [PR\#7955](https://github.com/1Panel-dev/1Panel/pull/7955/) 之前，Docker 在拉取镜像的时候，是通过 docker cli 运行 `docker pull` 命令拉取的。但在该修改之后，面板会直接与 docker engine 通信，通过 API 拉取。

~~这样怀疑范围又小了一部分。在对整体拉取速度进行统计之后，就确定问题出现于~~~~`mlikiowa/napcat-docker:v4.18.18`~~~~ 上。~~

在进行更加细致的观察后，发现并不是单一容器的问题，而是对于某些镜像的某些特定 layer 存在下载速度过慢的问题而不是局限于整体的容器拉取速度。

于是手动修改配置文件，将 Docker 的同时下载的 Layer 数量改为 1 \(在默认情况下，Docker 会同时下载的 Layer 数量为 3）

```YAML
{
     "registry-mirrors": [
          "https://docker.***.***"
     ],
    "max-concurrent-downloads": 1
}
```

此后再在服务器和本机上不同的环境下进行拉取修改测试

全量拉取比较各个 layer 拉取速度后发现是两个镜像的这两个 Layer 拉起速度较慢。

Napcat: 99adaac412a4

Astrbot: 1284b755ec6a

拿 napcat 的该 layer 测试，直接使用 `curl` 命令，手动拉取源数据并指定下载。

```YAML
curl -s \
  -H 'Accept: application/vnd.docker.distribution.manifest.v2+json' \
  https://docker.***.***/v2/mlikiowa/napcat-docker/manifests/v4.18.18 \
  | jq
```

得到

```JSON
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.index.v1+json",
  "manifests": [
    {
      "mediaType": "application/vnd.oci.image.manifest.v1+json",
      "digest": "sha256:cbcfebdc2656f7f7ff388ddfe0762b192335572a6e2bdfb576aa4246edb19943",
      "size": 1628,
      "platform": {
        "architecture": "amd64",
        "os": "linux"
      }
    },
    {
      "mediaType": "application/vnd.oci.image.manifest.v1+json",
      "digest": "sha256:9478065f1ca882a1a73dffdec958f947f24f8086d18548f27b37b432c21c5ace",
      "size": 1628,
      "platform": {
        "architecture": "arm64",
        "os": "linux"
      }
    },
    {
      "mediaType": "application/vnd.oci.image.manifest.v1+json",
      "digest": "sha256:9202418e2e6946c5bea024374a62a7d79ae63ab947284692c94bf47ec5b0ae08",
      "size": 564,
      "annotations": {
        "vnd.docker.reference.digest": "sha256:cbcfebdc2656f7f7ff388ddfe0762b192335572a6e2bdfb576aa4246edb19943",
        "vnd.docker.reference.type": "attestation-manifest"
      },
      "platform": {
        "architecture": "unknown",
        "os": "unknown"
      }
    },
    {
      "mediaType": "application/vnd.oci.image.manifest.v1+json",
      "digest": "sha256:a762cef58e8e48b6064f42f224e447f3110dd164d8fbb0613b49e5324848b7d4",
      "size": 564,
      "annotations": {
        "vnd.docker.reference.digest": "sha256:9478065f1ca882a1a73dffdec958f947f24f8086d18548f27b37b432c21c5ace",
        "vnd.docker.reference.type": "attestation-manifest"
      },
      "platform": {
        "architecture": "unknown",
        "os": "unknown"
      }
    }
  ]
}
```

这是napcat的多架构镜像顶层索引，因为服务器是 X86 架构，因此选用 architecture amd64，也就是

> "digest": "sha256:cbcfebdc2656f7f7ff388ddfe0762b192335572a6e2bdfb576aa4246edb19943"

再获取对应镜像的layer信息

```YAML
curl -s \
  -H 'Accept: application/vnd.oci.image.manifest.v1+json' \
  https://docker.***.***/v2/mlikiowa/napcat-docker/manifests/sha256:cbcfebdc2656f7f7ff388ddfe0762b192335572a6e2bdfb576aa4246edb19943 \
  | jq
```

得到

```JSON
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.manifest.v1+json",
  "config": {
    "mediaType": "application/vnd.oci.image.config.v1+json",
    "digest": "sha256:0f76fde5ecb3d738f970e8b6fafff8a151540907fde308221e781b87b0992b94",
    "size": 5110
  },
  "layers": [
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:6414378b647780fee8fd903ddb9541d134a1947ce092d08bdeb23a54cb3684ac",
      "size": 29535688
    },
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:490f82e472ca8db02fef02d020d6cadeb58dea37642c5d42814fa9819fe58eb6",
      "size": 271963756
    },
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:7c7b5cd01343fbc3495bf320ebcc9a413a180551d49146885cfbe6e1426d6b21",
      "size": 1412
    },
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:47e443e2d71a3cd56adf54144a2b7d13e7791fdb17b965cea974b3f9bbf5791a",
      "size": 93
    },
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:81c066f39089ddcace93effcec25665495e3d4d7ca7896d98eea4d9cf4dbf29b",
      "size": 28791179
    },
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:99adaac412a4a27d8281d9004e797149f3d6f7cb5e8fb51bc073c31b2361eb49",
      "size": 267101944
    },
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:dc00ce595fccf890cd8505403725479661a93194c6ff8350d1841d22629b7870",
      "size": 3167
    }
  ]
}
```

找到对应的 layer

![OMXKl.png](https://a1.ax1x.com/2026/08/23/OMXKl.png)

使用指令进行手动下载

```YAML
curl -L \
  -o /dev/null \
  -w $'\nHTTP=%{http_code}\nSIZE=%{size_download} bytes\nSPEED=%{speed_download} bytes/s\nTIME=%{time_total}s\n' \
  "https://docker.***.***/v2/mlikiowa/napcat-docker/blobs/sha256:99adaac412a4a27d8281d9004e797149f3d6f7cb5e8fb51bc073c31b2361eb49"
```

在不同的情况下多次尝试下载

省流：

在成都云服务器上，多次下载速度分别为（单位MBps）：11\.1、11\.5、5、`0.1`、13、6\.2、7、`4.5`、11\.9、11\.6、10\.3、12\.1、1\.9

在本机上，多次下载速度分别为（单位MBps）：4\.85、0\.018、0\.042、14\.88、8\.84、0\.002、0\.006，3\.7、11\.7、7、6\.7



由数据可知，下载速率是随机波动的

那么有没有可能不只是这一个 Layer 下载波动，其他的 Layer 也存在相同的问题呢？现在随机挑选了一个 24MB 的 Layer，多次下载测试。

在成都云服务器上，多次下载速度分别为：11\.7、12\.3、11\.9、`4`、12\.5、12\.3、11\.9、13\.1、`3.1`、4\.8、12\.7

在本机上，多次下载速度分别为：5、6\.5、5\.4、6\.5、5\.7、5\.8、4\.9、6\.8、4\.4、4\.1、4\.9


整体的下载速度都相对不怎么稳定，时快时慢的。那么如果是直接从 Docker Hub 拉取呢？

在本地环境直接挂梯从 dockerhub 拉取，测试10次速率恒定，都是稳定跑慢速



感觉可能不是拉取问题，而是涉及到 tcp 网络连接，但是当前的精力不足可能得过段时间再继续了，目前服务器中仍然在跑定时脚本收集数据



## Docker 缓存

在对比测试的时候，某一次在成都的机器上拉取两个镜像时，出现了没有流量流入，而是秒拉取成功。疑问是可能是 Docker 有潜在的缓存机制

一个 Docker 的镜像有很多个 Layer 组成，运行 docker pull 命令拉取镜像时，会逐个 Layer 下载（官方默认线程为 3，也就是同时下载 3 个 Layer）。已经下载好的 layer 会放在 content store 中，下次如果需要下载相同的layer就可以直接使用本地已有的不需要联网重下

Docker 默认的 `content store`存放位置在 `/var/lib/containerd/io.containerd.content.v1.content`

[![OMvgp.png](https://a1.ax1x.com/2026/08/23/OMvgp.png)](https://imgse.com/i/OMvgp)

作为测试用途，我必须清理掉 content store 的缓存。但是官方似乎并没有给出一个单独的清理方案

github中也有相似的[issues](https://github.com/moby/moby/issues/48909)。根据实测使用`docker image prune -a`命令可以在清理掉未被引用的镜像的同时一起清理掉content store缓存\(这似乎是一个bug\)