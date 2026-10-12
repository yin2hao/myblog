# 文章图片上传

提交到 `master` 后，GitHub Actions 会扫描 `source/` 下的 Markdown。工作流将本地图片上传到 PicGo 官方的 [PicGo Cloud](https://cloud.picgo.app)，再把文章中的图片路径替换为上传后返回的 HTTPS 链接。随后，工作流提交修改后的文章，构建 Hexo，并部署到 `gh-pages`。

## 配置 GitHub Actions

在本地安装项目依赖，并登录 PicGo Cloud：

```powershell
npm ci
npx --no-install picgo login
```

登录命令会打开浏览器。完成登录后，PicGo 会把凭证保存到用户目录下的 `.picgo/config.json`。Windows 默认路径为 `C:\Users\你的用户名\.picgo\config.json`。

在 GitHub 仓库的 `Settings → Secrets and variables → Actions` 中，新建 Repository secret：

| 名称 | 值 |
| --- | --- |
| `PICGO_CLOUD_TOKEN` | 本地配置文件中 `settings.picgoCloud.token` 的值 |

凭证只填入 GitHub Secret。不要将凭证或本地 PicGo 配置文件提交到仓库。

上传脚本不再读取 S3 配置。确认仓库没有其他工作流使用后，可以删除 `S3_ENDPOINT`、`S3_BUCKET`、`S3_ACCESS_KEY_ID` 和 `S3_SECRET_ACCESS_KEY` 等旧 Secrets，以及 `S3_REGION`、`S3_PREFIX` 和 `IMAGE_PUBLIC_URL` 等旧 Variables。

## 写文章和发布

图片文件必须随文章一起提交到仓库。支持文章相对路径和相对于 Hexo `source/` 的根路径：

```markdown
![截图](./images/example.png)
![截图](/images/example.png)
<img src="./images/example.png" alt="截图">
```

已有的网络图片链接保持原样。代码块和行内代码中的图片示例也保持原样。脚本保留图片地址上的查询参数、锚点、标题和 HTML 属性。同一次运行中，内容和扩展名相同的图片只上传一次。

脚本会先检查所有本地引用，再上传图片。全部上传成功且返回有效的 HTTPS 链接后，才回写文章。图片缺失、路径越出仓库或上传失败时，工作流停止，文章保持原样。

没有本地图片引用时，脚本直接结束，无需配置 `PICGO_CLOUD_TOKEN`。上传后的文章使用网络链接，后续部署会跳过这些图片。本地图片文件仍保留在仓库中。

## 在本地上传

需要 Node.js 22 和 Python 3.12，或兼容的更新版本。在仓库根目录执行：

```powershell
$env:PICGO_CLOUD_TOKEN = '你的 PicGo Cloud token'
npm run upload-images
Remove-Item Env:PICGO_CLOUD_TOKEN
```

命令会直接改写本地文章。检查差异后再提交。脚本通过环境变量传递凭证，并为 PicGo 创建临时配置目录，结束时删除目录。脚本不会读取或覆盖你原有的 PicGo 配置。

上传工具位于 `tools/`，用于独立执行。Hexo 会将 `scripts/` 下的文件当作 JavaScript 插件加载，因此不要将 Python 上传工具放入该目录。

## 故障处理和使用限制

- 提示缺少 `PICGO_CLOUD_TOKEN`：检查 GitHub Secret 名称和是否已填写值。
- 提示未登录或凭证失效：重新执行 `picgo login`，更新 GitHub Secret。
- 提示配额不足或文件过大：在 PicGo Cloud 账号中检查套餐、存储空间和文件限制。
- 部分图片上传后发生失败：文章不会回写；已上传的图片可能留在云端。重跑可能产生重复文件，可在云端相册中清理。
- GitHub Actions 无法提交文章：确认仓库允许工作流写入 `master`。分支保护规则可能阻止机器人直接提交。

图片链接由 PicGo Cloud 返回，脚本不会再拼接 S3 桶地址或自定义图片域名。以前写入文章的 S3 网络链接保持原样，需要迁移时另行处理。

PicGo Cloud 提供可公开访问的文件链接。接入后，图片托管和访问使用 PicGo Cloud 的服务及套餐规则；更换图床本身不会阻止他人转发或访问图片链接。删除云端图片会使文章中的对应链接失效。

## 参考资料

- [PicGo Core 配置文件](https://docs.picgo.app/zh/core/guide/config)：图床选择、登录 token 和配置文件路径。
- [PicGo Core CLI 命令](https://docs.picgo.app/zh/core/guide/commands)：登录和云端账号操作。
- [PicGo Core API](https://docs.picgo.app/zh/core/api/)：程序化上传和单次上传配置。
- [PicGo Cloud 文件上传与托管](https://docs.picgo.app/zh/cloud/file-hosting)：文件格式、公开链接和删除行为。
