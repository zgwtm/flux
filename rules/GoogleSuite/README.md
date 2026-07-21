# 谷歌全家桶（GoogleSuite）

将 Google、Gemini 与 YouTube 合并去重后生成的一份规则集，方便在 Loon 或
Clash/Mihomo 中把整套 Google 服务交给同一个策略。

## 合并来源

| 顺序 | blackmatrix7 上游 | 主要内容 |
|---|---|---|
| ① | `Gemini` | Gemini、生成式 AI 与 DeepMind 相关服务 |
| ② | `YouTube` | YouTube、Google Video 与视频静态资源 |
| ③ | `Google` | Google 通用服务、账号、Gmail、Drive、API 与相关 IP 段 |
| ④ | 本目录 `custom.list` | 三个上游均未覆盖时的本地补充规则 |

同步脚本按上表顺序提取规则并保留首次出现项，因此重复规则只会输出一次。
原有 `Google`、`Gemini`、`YouTube` 独立规则继续保留，可按需要单独分流。

## 订阅地址

- Loon：`https://raw.githubusercontent.com/zgwtm/flux/main/rules/GoogleSuite/GoogleSuite.list`
- Clash / Mihomo：`https://raw.githubusercontent.com/zgwtm/flux/main/rules/GoogleSuite/GoogleSuite.yaml`

在 Loon 中添加远程规则时，将标签设为“谷歌全家桶”，策略选择需要使用的
日本节点或日本策略组即可。

> 这份规则只负责网络分流，不会修改 Google 账号的国家/地区资料。
