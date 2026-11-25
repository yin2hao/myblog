---
title: grafana通知模板问题
date: 2026-11-7 19:10:35
tags:
  - grafana
---


## Grafana

写通知模板

```SQL
{{ define "server.alert.message" }}
{{ range .Alerts -}}
服务器：{{ index .Labels "instance" }}
{{ index .Annotations "summary" }}
{{ index .Annotations "description" }}
{{ if eq .Status "firing" -}}
{{ index .Annotations "firing_message" }}
{{ else -}}
{{ index .Annotations "resolved_message" }}
{{ end -}}
{{ end }}
{{ end }}
```

但是这个通用模板存在排版问题，最终呈现的效果是这样的：

![image\.png](https://picgocloud.com/m/f5732d6a-b243-4b6f-bf23-20a273455f5e.png)

可以看到，模板的首尾出现了预期外的空行

于是尝试将它进行修改，最后修改出来的结果是这样的：

```SQL
{{- define "server.alert.message" -}}
{{- range .Alerts }}
服务器：{{ index .Labels "instance" }}
{{ index .Annotations "summary" }}
{{ index .Annotations "description" }}
{{- if eq .Status "firing" }}
{{ index .Annotations "firing_message" }}
{{- else }}
{{ index .Annotations "resolved_message" }}
{{- end }}
{{- end -}}
{{- end -}}
```

![image\.png](https://picgocloud.com/m/3108a523-adaf-43fc-9108-fa7e5795ab10.png)

但是出现了一个问题，就是修改之后的通知模板无法保存。

![image\.png](https://picgocloud.com/m/de3ffe0b-c08d-4bce-adf6-cc49c941af60.png)

而且它的前端没有显示更细节的说明

挣扎未果之后，gpt给出了新的解题思路：F12看一下浏览器请求

从浏览器请求中抓出来了一些有用的信息

```YAML
{
  "kind": "Status",
  "apiVersion": "v1",
  "metadata": {},
  "status": "Failure",
  "message": "Template is in invalid format. Correct the payload and try again.",
  "reason": "BadRequest",
  "details": {
    "uid": "alerting.notifications.templates.invalidFormat",
    "causes": [
      {
        "message": "\"invalid template: template: :2: unexpected \\u003cdefine\\u003e in command\"",
        "field": "Error"
      }
    ]
  },
  "code": 400
}
```

也就是说，在我的 define 外层，还被套了一层 define ，导致解析失败

查看一下入参

```YAML
{
  "spec": {
    "title": "aas",
    "content": "{{ define \"aas\" }}\n  {{- define \"server.alert.message\" -}}\r\n  {{- range .Alerts }}\r\n  服务器：{{ index .Labels \"instance\" }}\r\n  {{ index .Annotations \"summary\" }}\r\n  {{ index .Annotations \"description\" }}\r\n  {{- if eq .Status \"firing\" }}\r\n  {{ index .Annotations \"firing_message\" }}\r\n  {{- else }}\r\n  {{ index .Annotations \"resolved_message\" }}\r\n  {{- end }}\r\n  {{- end -}}\r\n  {{- end -}}\n{{ end }}",
    "kind": "grafana"
  },
  "metadata": {},
  "apiVersion": "notifications.alerting.grafana.app/v1beta1",
  "kind": "TemplateGroup"
}
```

可以看到确实别叠了两层define，其中第一层是我的`模板组名称 *`

但是第一次为什么不会出现这种情况呢？再F12一下

```YAML
{
    "kind": "TemplateGroup",
    "apiVersion": "notifications.alerting.grafana.app/v1beta1",
    "metadata": {
        "name": "Z3JhZmFuYXzpgJrnlKjmiqXoraYt5oGi5aSN5q2j5bi4IChjb3B5KQ",
        "namespace": "default",
        "uid": "Mh2Py3bBBpms7k1eiH6H9XA89rdZN5CvoMXBpgZP5ucX",
        "resourceVersion": "7dbf22aab3d21713"
    },
    "spec": {
        "title": "通用报警-恢复正常 (copy)",
        "content": "{{ define \"server.alert.message_NEW_1794067928846\" }}\r\n{{ range .Alerts -}}\r\n服务器：{{ index .Labels \"instance\" }}\r\n{{ index .Annotations \"summary\" }}\r\n{{ index .Annotations \"description\" }}\r\n{{ if eq .Status \"firing\" -}}\r\n{{ index .Annotations \"firing_message\" }}\r\n{{ else -}}\r\n{{ index .Annotations \"resolved_message\" }}\r\n{{ end -}}\r\n{{ end }}\r\n{{ end }}",
        "kind": "grafana"
    }
}
```

可以看到只有一层define，控制变量法测试后发现
grafana检测到存在`{{ define "server.alert.message" }}`字段就不会自动添加，如果不存在就会自动附加上`{{ define "模板组名称" }}`。但是他似乎只检测`{{ define`开头的，`{{- define`不会被检测到
