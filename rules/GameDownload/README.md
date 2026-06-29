# GameDownload — Mokka 的游戏分流合并规则集

一个**合并去重**后的单一规则集。目标：游戏相关流量（尤其是下载）**全部直连**，
配置里只需一条 `RULE-SET,GameDownload,DIRECT` 就能搞定，干净利落。

## 合并了哪些来源

| # | 来源 | 内容 |
|---|------|------|
| ① | blackmatrix7 `Steam`（Clash + Loon） | Steam 全集：商店 / 社区 / API / 国服 CDN |
| ② | blackmatrix7 `Game/GameDownload`（Clash + Loon） | 九平台下载 CDN：Steam · Epic · 暴雪 · Xbox · EA · R星 · GOG · 育碧 · Riot |
| ③ | 本目录 `custom.list` | 上游漏收 / 额外补充的域名（见下） |

上游路径写在仓库根目录 `config.yaml` 的 `GameDownload` 规则里（`clash_paths` / `loon_paths`）。

## custom.list 补了什么、为什么

- **`steamserver.net`** —— Steam 下载主力 CDN，**①②两个上游都没收录**，实测会漏到代理。必须补。
- **`steamcontent.com`** —— 最早发现的漏网下载域名；GameDownload 上游已含，**合并去重后只保留一份**，custom 里留一份作双保险。
- **`dl.playstation.net`** —— **PS5 游戏下载**（含 `gs2.ww.prod.dl.playstation.net`）。只下载直连；PSN 账号 / 港服·美服商店不在此列，仍走代理。

## 合并 + 去重是怎么做的

`scripts/sync.py` 支持一条规则填多个上游（`clash_paths` / `loon_paths`）：
逐个下载 → 提取规则行（丢掉注释和 `payload:` 头）→ 接上 `custom.list` → **按首次出现顺序去重** →
生成 `GameDownload.yaml`（Clash/Mihomo）和 `GameDownload.list`（Loon）。
GitHub Actions 每天自动跑一次，两个上游有更新会自动合并进来。

## 订阅地址

- Clash / Mihomo：`https://raw.githubusercontent.com/zgwtm/flux/main/rules/GameDownload/GameDownload.yaml`
- Loon：`https://raw.githubusercontent.com/zgwtm/flux/main/rules/GameDownload/GameDownload.list`

## 历史

2026-06-29 由旧的 `Steam` + `PlayStation` 两个独立规则集合并而来，二者已下线。
