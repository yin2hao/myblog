---
layout: layout
title: github action使用docker/build-push-action@v6推送失败，提示401 Unauthorized,已排除权限问题
date: 2026-09-18 21:54:13
tags: docker
---

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

先检查版本号，比如`v1.0.0`这样的三段式，`v*.*.*`的格式，不是指定格式的规范成这个格式

然后开始构建前端。先通过 `docker/setup-buildx-action@v3` 安装docker cli，然后使用`docker/login-action@v3`通过 github secret中的信息登录 docker hub。最后通过 `docker/build-push-action@v6` 构建并push镜像。
但是测试运行的时候，发现推送时报错

```YAML
ERROR: failed to build: failed to solve: failed to fetch oauth token: unexpected status from GET request to https://auth.docker.io/token?scope=repository%3A***%2Fvideobackup-frontend%3Apull%2Cpush&service=registry.docker.io: 401 Unauthorized: access token has insufficient scopes
```

一般来说这个的意思是PAT的权限不足以 push 上 dockerhub 。但是我很明确是授予了 `read & write` 权限的

而且这一个发布的工作流是从另一个已经正常跑了 5 个月的仓库直接扒下来的，理论上配置什么的都相同，不应该出问题才对。

于是尝试各种替换 github secrets测试，无论怎样都是 401 错误。于是开始尝试根据流程排查。首先可以确认的是`docker/login-action@v3`是没有问题的，因为该步骤提示`Login Succeeded!`，说明`REGISTRY_USERNAME`和`REGISTRY_PASSWORD`是可以正常登录的，但是最后仍然提示没有授权。



已知：

- 提示令牌权限不足

- 确认令牌生成时给足了权限

- 确认填入的是我的令牌

那么可能的原因只剩下了

1. docker官方权限管理出问题了

2. 工作流没有使用我的PAT

docker hub官方我没办法，且社区没有看到有明确的帖子讨论这件事情，因此不太可能是官方的问题。那就只能往工作流中没有使用我的 PAT 上面靠。



先了解一下整体的流程代码，借助 GPT 对整体流程的相关代码进行扫描：

查阅了三个action脚本的代码没有发现明显问题

这里`docker/login-action@v3`对于register的处理只有一个当不存在时自动设置为`docker.io`，无伤大雅

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



在 [docker cli](https://github.com/docker/cli) 中检索到了代码
`cli/command/registry/login.go` line 161

```Go
if opts.serverAddress != "" && opts.serverAddress != registry.DefaultNamespace {
    serverAddress = opts.serverAddress
} else {
    serverAddress = registry.IndexServer
}
```

在`docker login`流程中，传入的`serverAddress`不为空且不为`docker.io`时，设置为传入值，否则设置为默认`https://index.docker.io/v1/`



`cli/config/configfile/file.go` line 44

```Go
func getAuthConfigKey(domainName string) string {
    if domainName == "docker.io" || domainName == "index.docker.io" {
        return authConfigKey
    }
    return domainName
}
```

而`const authConfigKey = "``https://index.docker.io/v1/``"`， 也就是说，当 DomainName 为`docker.io`的时候，会直接返回`https://index.docker.io/v1/`。



这两串代码一起，会导致`docker login docker.io`时在本地`config.json`文件写入的domian为`https://index.docker.io/v1/`而不是`docker.io`



在 [container](https://github.com/containerd/containerd) 中检索到代码

`core/remotes/docker/config/hosts.go` line 102

```Go
if host == "docker.io" {
    hosts[len(hosts)-1].scheme = "https"
    hosts[len(hosts)-1].host = "registry-1.docker.io"
}
```

在传入是`docker.io`时，container会将其映射回`registry-1.docker.io`



同时在 [docker buildx](https://github.com/docker/buildx) 仓库发现了类似的逻辑

`util/dockerutil/dockerconfig/configprovider.go`文件 line 122\~125

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

在 docker 中， buildx用于管理BuildKit的各种控制器，此处代码用于读取本地 `config.json` 以为 BuildKit 提供镜像仓库认证信息



也就是说，从配置文件读取的时候，如果传入 host 为`docker.io`的话，container会将host替换为`registry-1.docker.io`，然后又被`configprovider`修改为读取 `https://index.docker.io/v1/`。于是读取配置文件时不会读取`docker.io`对应的 PAT，而是使用`https://index.docker.io/v1/`对应的PAT



这两者刚好使`docker.io`能够正常运行



如果传入的`registry host`为`registry-1.docker.io`的话，那么在`docker login registry-1.docker.io`环节能够正常的写入`config.json`文件，但是在 buildx 构建完成推送的时候，会被`configprovider`替换为`https://index.docker.io/v1/`



但是如果是这样的话，还有一个问题：原本的本地记录里面有一个对应的PAT，并且这个PAT的权限不足以推送，才会导致后续的出现401 Unauthorized。这个PAT是哪来的呢？为此单独开了一个仓库测试:



在 registry host为`registry-1.docker.io`时，登录前和登录后的`config.json`分别为

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

在 registry host为`docker.io`时，登录前和登录后的`config.json`分别为

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

与代码逻辑相同。

如实验结果所示，在登录工作流运行之前，Action Runner容器中就已经存在了一份config\.json文件。查找资料后，感觉可能是因为[这个](https://docs.github.com/zh/actions/how-tos/write-workflows/choose-where-workflows-run/run-jobs-in-a-container)的原因

> Docker Hub 通常会对推送和拉取操作设置速率限制，这将影响自托管运行程序上的作业。 不过，根据 GitHub 和 Docker 之间的协议，GitHub 托管的运行程序不受这些限制的约束。