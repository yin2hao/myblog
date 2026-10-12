---
layout: layout
title: github action使用docker/build-push-action@v6推送失败，提示401 Unauthorized,已排除权限问题
date: 2026-09-18 21:54:13
tags: docker
---

## docker hub推送问题

### 问题开始

我自己的项目有一套自动构建\+推送到 dockerHub 的工作流。
现在我将原本的项目前后端拆分为单独的仓库，发现工作流运行出现了问题

这是我原本的工作流

```YAML
name: Publish frontend Docker image

on:
  push:
    tags:
      - '*'

permissions:
  contents: read

concurrency:
  group: docker-publish-${{ github.repository }}-${{ github.ref }}
  cancel-in-progress: false

jobs:
  normalize-version:
    name: Validate and normalize tag
    runs-on: ubuntu-latest
    outputs:
      valid: ${{ steps.version.outputs.valid }}
      version: ${{ steps.version.outputs.version }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Validate vX.Y.Z-compatible tag
        id: version
        shell: bash
        env:
          TAG: ${{ github.ref_name }}
        run: bash scripts/release/normalize-version.sh

  publish-image:
    name: Build and push frontend Docker image
    needs: normalize-version
    if: needs.normalize-version.outputs.valid == 'true'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to container registry
        uses: docker/login-action@v3
        with:
          registry: ${{ secrets.REGISTRY_HOST }}
          username: ${{ secrets.REGISTRY_USERNAME }}
          password: ${{ secrets.REGISTRY_PASSWORD }}

      - name: Build and push frontend image
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile
          push: true
          tags: |
            ${{ secrets.REGISTRY_HOST }}/${{ secrets.REGISTRY_NAMESPACE }}/videobackup-frontend:${{ needs.normalize-version.outputs.version }}
            ${{ secrets.REGISTRY_HOST }}/${{ secrets.REGISTRY_NAMESPACE }}/videobackup-frontend:latest
          labels: |
            org.opencontainers.image.title=VideoBackup frontend
            org.opencontainers.image.version=${{ needs.normalize-version.outputs.version }}
            org.opencontainers.image.source=${{ github.server_url }}/${{ github.repository }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

大概的步骤是：

先检查版本号，比如`v1.0.0`这样的三段式，`v*.*.*`的格式（`Semantic Versioning`，`MAJOR.MINOR.PATCH`语义化版本号），不符合格式的规范成这个格式

然后开始构建前端。先通过 `docker/setup-buildx-action@v3` 安装docker cli，然后使用`docker/login-action@v3`通过 github secret中的信息登录 docker hub。最后通过 `docker/build-push-action@v6` 构建并push镜像。
但是测试运行的时候，发现推送时报错

```YAML
ERROR: failed to build: failed to solve: failed to fetch oauth token: unexpected status from GET request to https://auth.docker.io/token?scope=repository%3A***%2Fvideobackup-frontend%3Apull%2Cpush&service=registry.docker.io: 401 Unauthorized: access token has insufficient scopes
```



### 排查

一般来说这个的意思是 PAT 的权限不足以 push 上 dockerhub 。但是我很明确是授予了 `read&write` 权限的

而且更诡异的是，这一个发布的工作流是从另一个已经正常跑了 5 个月的仓库直接扒下来的，理论上配置什么的都相同，不应该出问题才对。


我的第一反应是 github secret 填错了，因为填入之后就看不到填入的内容，于是我尝试各种替换 github secrets 测试，无论怎样都是 401 错误。

于是我开始尝试根据流程排查。首先可以确认的是`docker/login-action@v3`是没有问题的，因为该步骤提示`Login Succeeded!`，说明`REGISTRY_USERNAME`和`REGISTRY_PASSWORD`是可以正常登录的，但是最后仍然提示没有授权。

已知：

- 提示令牌权限不足

- 确认令牌生成时给足了权限

- 确认填入的是我的令牌

那么可能的原因只剩下了

1. docker官方权限管理出问题了

2. 工作流没有使用我的PAT

docker hub官方我没办法，且社区没有看到有明确的帖子讨论这件事情，因此不太可能是官方的问题。那就只能往工作流中没有使用我的 PAT 上面靠。



于是尝试让工作流直接将最终的`config.json`打印在控制台，发现了问题：`config.json`中存在两个密钥

```Go
{
  "auths": {
    "https://index.docker.io/v1/": {
      "auth": "..."
    },
    "registry-1.docker.io": {
      "auth": "..."
    }
  }
}
```

按道理来说只应该存在`registry-1.docker.io`才对，多出了一个`https://index.docker.io/v1/`。



为此单独开了一个仓库测试:

在仓库传入`registry host`为`registry-1.docker.io`时，登录前和登录后的`config.json`分别为

```YAML
{
  "auths": {
    "https://index.docker.io/v1/": {
      "auth": "..."
    }
  }
}
```

```JSON
{
  "auths": {
    "https://index.docker.io/v1/": {
      "auth": "..."
    },
    "registry-1.docker.io": {
      "auth": "..."
    }
  }
}
```

在 `registry host`为`docker.io`时，登录前和登录后的`config.json`分别为

```Go
{
  "auths": {
    "https://index.docker.io/v1/": {
      "auth": "..."
    }
  }
}
```

```Go
{
  "auths": {
    "https://index.docker.io/v1/": {
      "auth": "..."
    }
  }
}
```

如实验结果所示，在登录工作流运行之前，Action Runner容器中就已经存在了一份`config.json`文件，并且`config.json`文件中存在一个`PAT`。查找资料后，感觉可能是因为这个的原因

![image\.png](https://picgocloud.com/m/acdde270-6854-4a44-be7f-011992236168.png)



这里有一个小插曲，在 `Github Action` 日志中，会自动隐藏掉 `Github Secret` 的值。我之前猜想这个隐藏是通过监控变量传值实现的。

但实际上，在日志中输出已经写入到文件中的 PAT 的值的时候，发现仍然不能输出，会被 github 拦截掉，才知道，最高等的食材往往采用最朴素的烹饪方式——直接从输出内容中匹配到相同的字符串，然后隐藏。



现在已经知道了存在一个多余的`PAT`，但是没有解释一件事情：在测试的时候，为什么当`registry host`为`docker.io`的时候，登录写入的 K 是`https://index.docker.io/v1/`，并且当`registry host`为`registry-1.docker.io`的时候推送存在问题



借助 GPT 对整体流程的相关代码进行扫描：

查阅了三个action脚本的代码没有发现明显问题

这里`docker/login-action@v3`对于 register host 的处理只有一个当不存在时自动设置为`docker.io`，无伤大雅

```TypeScript
export function getAuthList(inputs: Inputs): Array<Auth> {
  if (inputs.registryAuth && (inputs.registry || inputs.username || inputs.password || inputs.scope || inputs.ecr)) {
    throw new Error('Cannot use registry-auth with other inputs');
  }
  let auths: Array<Auth> = [];
  if (!inputs.registryAuth) {
    const registry = inputs.registry || 'docker.io';
    auths.push({
      registry,
      username: inputs.username,
      password: inputs.password,
      scope: inputs.scope,
      ecr: inputs.ecr || 'auto',
      configDir: scopeToConfigDir(registry, inputs.scope)
    });
  } else {
    auths = (yaml.load(inputs.registryAuth) as Array<Auth>).map(auth => {
      if (auth.password) {
        core.setSecret(auth.password); // redacted in workflow logs
      }
      const registry = auth.registry || 'docker.io';
      return {
        registry,
        username: auth.username,
        password: auth.password,
        scope: auth.scope,
        ecr: auth.ecr || 'auto',
        configDir: scopeToConfigDir(registry, auth.scope)
      };
    });
  }
  if (auths.length == 0) {
    throw new Error('No registry to login');
  }
  return auths;
}
```



那么怀疑会不会是 docker 本身的问题。在本机 docker 环境完成复现后，我开始借助 gpt 对 docker 官方的代码库进行扫描，着重处理 docker 官方域名的处理逻辑：

#### docker cli

[`cli/command/registry/login.go`](https://github.com/docker/cli/blob/master/cli/command/registry/login.go#L161) line 161

```Go
if opts.serverAddress != "" && opts.serverAddress != registry.DefaultNamespace {
    serverAddress = opts.serverAddress
} else {
    serverAddress = registry.IndexServer
}
```

此处：

```Go
registry.DefaultNamespace == docker.io
registry.IndexServer == https://index.docker.io/v1/
```

在`docker login`流程中，传入的serverAddress不为空且不为`docker.io`时，设置为传入值，否则设置为默认`https://index.docker.io/v1/`



[`cli/config/configfile/file.go`](https://github.com/docker/cli/blob/master/cli/config/configfile/file.go#L44) line 44

```Go
func getAuthConfigKey(domainName string) string {
    if domainName == "docker.io" || domainName == "index.docker.io" {
        return authConfigKey
    }
    return domainName
}
```

而`authConfigKey = "``https://index.docker.io/v1/``"`， 也就是说，当`DomainName`为`docker.io`的时候，会直接返回`https://index.docker.io/v1/`。



这两串代码一起，会导致`docker login docker.io`时在本地`config.json`文件写入的domian为`https://index.docker.io/v1/`而不是`docker.io`



#### docker buildKit

[util/resolver/resolver\.go](https://github.com/moby/buildkit/blob/master/util/resolver/resolver.go#L146) line 146

```Go
if host == "docker.io" {
    host = "registry-1.docker.io"
}
```



#### docker buildx

[`util/dockerutil/dockerconfig/configprovider.go`](https://github.com/docker/buildx/blob/master/util/dockerutil/dockerconfig/configprovider.go#L122) line 122\~125

```Go
hostKey := host
if host == authprovider.DockerHubRegistryHost {
    hostKey = authprovider.DockerHubConfigfileKey
}
```

其中

```Go
DockerHubConfigfileKey = "https://index.docker.io/v1/"
DockerHubRegistryHost  = "registry-1.docker.io"
```

在 docker 中， `buildx`用于管理`BuildKit`的各种控制器，此处代码用于读取本地 `config.json` 以为 BuildKit 提供仓库认证信息

此处会检查`hostKey`是否为`registry-1.docker.io`，如果是则将其替换为`https://index.docker.io/v1/`

#### container

在 container 中检索到代码

[`core/remotes/docker/config/hosts.go`](https://github.com/containerd/containerd/blob/main/core/remotes/docker/config/hosts.go#L102) line 102

```Go
if host == "docker.io" {
    hosts[len(hosts)-1].scheme = "https"
    hosts[len(hosts)-1].host = "registry-1.docker.io"
}
```

在传入是`docker.io`时，container会将其映射回`registry-1.docker.io`



core/remotes/docker/registry\.go line 200

```Go
else if host == "docker.io" {
    config.Host = "registry-1.docker.io"
}
```



#### 串联

也就是说，在`docker login`阶段，如果：

- 传入的`register host`为`docker.io`，那么会被规范化为`https://index.docker.io/v1/`并保存

- 传入的`register host`为`registry-1.docker.io`，不会做规范处理直接以`registry-1.docker.io`原样保存



在`docker/build-push-action@v6`阶段，如果：

- 传入的`register host`为`docker.io`，会被规范化为`https://index.docker.io/v1/`并尝试从`config.json`获取

- 传入的`register host`为`registry-1.docker.io`，也会被规范化为`https://index.docker.io/v1/`并尝试从`config.json`获取



这样，

- 当传入`register host`为`docker.io`时，写入和读取的都是`https://index.docker.io/v1/`，即使原本`github runner`中存在，也会被覆盖

- 传入的`register host`为`registry-1.docker.io`时，写入`registry-1.docker.io`，读取`https://index.docker.io/v1/`，本应该读取失败。但是因为`github runner`自带一个用于加速拉取的`PAT`，会读取成功，但是该`PAT`不具备访问个人仓库权限





### 后记

想要把上面的改改提个 pr 上去，看 cli 调用流程的时候又发现个小问题¯\\\(°\_o\)/¯



在`docker login`的时候，docker cli会将`docker.io`解析为`index.docker.io`并且写入`config.json`。但是`docker logout`的时候没有解析流程

也就是说，

- 登陆时：`docker login docker.io`成功，写入`https://index.docker.io/v1/`

- 登出时：`docker logout docker.io`成功\(实际失败\)，尝试删除`docker.io`，但不存在

![PixPin\_2026\-09\-23\_13\-03\-25\.gif](https://picgocloud.com/m/6e319499-fefe-4ce3-b083-51cee0848d74.gif)

该问题已提交[pr](https://github.com/docker/cli/pull/7327)，会被合并吗？

### 后记的后记

又双发现个问题，域名前方可以带有`scheme`，也就是`http://`和`https://`。在`docker login`中确实对其进行了处理，但是`docker login`的时候判断域名是否是`docker.io`是在 URL 处理之前的，也就是说：

> `处理官方域名兼容` \-\-\-\-\> `处理传入域名scheme`
> 
> 



所以如果`docker login ``https://docker.io`最终会绕过解析化流程最终成功在`config.json`中写入`docker.io`\.\.\.\.\.\.

```Go
func runLogin(ctx context.Context, dockerCLI command.Cli, opts loginOptions) error {
    ······
    // 在这里将docker.io进行处理
    if opts.serverAddress != "" && opts.serverAddress != registry.DefaultNamespace {
       serverAddress = opts.serverAddress
    } else {
       serverAddress = registry.IndexServer
    }
    isDefaultRegistry := serverAddress == registry.IndexServer

    // 在这里GetDefaultAuthConfig方法会检测"://"并进行处理，统一处理为不带协议前缀的形式
*    *authConfig, err := command.GetDefaultAuthConfig(dockerCLI.ConfigFile(), opts.user == "" && opts.password == "", serverAddress, isDefaultRegistry)
    if err == nil && authConfig.Username != "" && authConfig.Password != "" {
       msg, err = loginWithStoredCredentials(ctx, dockerCLI, authConfig)
    }
    ······
}
```



在`login.go`文件中会调用`register.go`文件的`authConfig, err := command.GetDefaultAuthConfig()`方法，该方法会在`register.go`文件中进行`scheme`前缀的处理，但这一个流程是在将`docker.io`解析化为`index.docker.io`流程之后，因此如果输入的是`https://docker.io`的话，会跳过前方的解析流程，在后方的`register.go`文件中才被`scheme`前缀处理，最终落库到`config.json`中的键就是`docker.io`而不是之前的`index.docker.io`

于是：

- `docker login ``https://docker.io`，写入`config.json`为`docker.io`

- `buildKit`推送失败，因为镜像引用不支持`scheme`，因此无论如何都不会读取`docker.io`



buildx 不会接受外部或者环境变量传入的 host，而是通过镜像引用解析出来的，比如镜像引用为`ghcr.io/yin2hao/test:latest`，buildx就会自动解析registry为`ghcr.io`。

但是，如果镜像引用没有指定的话，就会默认是`docker.io`，也就是会被解析为`index.docker.io`。在尝试获取凭证的时候，就会发现：`config.json`中只有`docker.io`的key没有`index.docker.io`的key，因此推送就会失败