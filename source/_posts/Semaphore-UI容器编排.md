---
title: Semaphore UI 容器编排
date: 2026-10-23 19:10:35
tags:
  - docker
  - Semaphore UI
  - Ansible
---

Semaphore UI 可以在浏览器中运行 Ansible 剧本和自动化脚本。下面使用官方镜像和 SQLite，适合个人服务器上的单实例部署，无需额外运行数据库容器。

宿主机需要安装 Docker Engine 和 Docker Compose。本文命令在 Linux 服务器上执行，镜像固定为 `v2.19.12`。

## 容器编排

创建部署目录，后续命令都在这个目录执行：

```bash
mkdir -p /opt/semaphore
cd /opt/semaphore
```

新建 `compose.yaml`：

```yaml
services:
  semaphore:
    image: semaphoreui/semaphore:v2.19.12
    restart: unless-stopped
    ports:
      - "${SEMAPHORE_PORT:-3000}:3000"
    environment:
      TZ: Asia/Shanghai
      SEMAPHORE_DB_DIALECT: sqlite
      SEMAPHORE_DB_PATH: /var/lib/semaphore
      SEMAPHORE_ADMIN: admin
      SEMAPHORE_ADMIN_NAME: Admin
      SEMAPHORE_ADMIN_EMAIL: admin@localhost
      SEMAPHORE_ADMIN_PASSWORD: ${SEMAPHORE_ADMIN_PASSWORD:?请在 .env 中设置管理员密码}
      SEMAPHORE_ACCESS_KEY_ENCRYPTION: ${SEMAPHORE_ACCESS_KEY_ENCRYPTION:?请在 .env 中设置加密密钥}
    volumes:
      - semaphore-data:/var/lib/semaphore
      - semaphore-config:/etc/semaphore

volumes:
  semaphore-data:
  semaphore-config:
```

`semaphore-data` 保存 SQLite 数据库，`semaphore-config` 保存生成的配置文件。重建容器时，Docker 会继续使用这两个命名卷。保持部署目录名称不变，避免 Compose 创建另一组卷。

## 设置密码和密钥

运行下面的命令，生成随机的 32 字节加密密钥，并将输出完整保存：

```bash
head -c32 /dev/urandom | base64
```

在 `compose.yaml` 旁新建 `.env`，填写管理员密码和刚生成的密钥：

```dotenv
SEMAPHORE_PORT=3000
SEMAPHORE_ADMIN_PASSWORD=
SEMAPHORE_ACCESS_KEY_ENCRYPTION=
```

密码可用单引号包裹，避免其中的 `$` 等字符被 Compose 插值。密码或密钥留空时，Compose 会提示缺少配置并停止启动。

限制 `.env` 的读取权限：

```bash
chmod 600 .env
```

如果部署目录由 Git 管理，将 `.env` 加入 `.gitignore`。加密密钥用于保护数据库中的凭据，需要和数据一起备份；丢失或更换密钥后，已有凭据将无法解密。

## 启动和访问

先检查配置，再启动服务并查看日志：

```bash
docker compose config --quiet
docker compose up -d
docker compose logs --tail=100 semaphore
```

在浏览器中访问 `http://服务器IP:3000`，使用 `admin` 和 `.env` 中填写的密码登录。如果修改了 `SEMAPHORE_PORT`，访问地址也要使用对应端口。

管理员环境变量用于首次初始化。初始化完成后，在 Semaphore UI 中修改密码；修改 `.env` 中的初始密码不会重置已有账户。

编排默认将端口发布到宿主机的所有网卡。公网使用时应配置 HTTPS 反向代理并限制端口访问。如果反向代理直接运行在宿主机上，可将端口映射改为 `127.0.0.1:3000:3000`。使用域名访问时，在 `environment` 中增加 `SEMAPHORE_WEB_ROOT`，值填写完整的访问地址。

## 停止和升级

停止并删除容器，保留数据卷：

```bash
docker compose down
```

升级前先停止服务，备份两个命名卷及 `.env`。将 `compose.yaml` 中的镜像标签改为目标版本，再执行：

```bash
docker compose pull
docker compose up -d
docker compose logs --tail=100 semaphore
```

**不要执行 `docker compose down -v`，它会删除命名卷中的数据库和配置。**

## 参考资料

- [Semaphore UI 官方快速开始](https://semaphoreui.com/docs/getting-started)
- [Semaphore UI 官方 Docker 安装说明](https://semaphoreui.com/docs/admin-guide/installation/docker)
- [v2.19.12 容器启动脚本](https://github.com/semaphoreui/semaphore/blob/v2.19.12/deployment/docker/server/server-wrapper)
- [Semaphore UI 配置说明](https://semaphoreui.com/docs/admin-guide/configuration)
