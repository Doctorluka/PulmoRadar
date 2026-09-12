# PulmoRadar

肺部与肺血管 **basic research** 的每周文献雷达。选题、筛选、解读由 DeepSeek 完成，邮件发到 `doctorfhz@gmail.com`。

| 时间（北京） | 主题 | 已发表额度 | 预印本 |
| --- | --- | --- | --- |
| 周一 08:00 | 慢性肺病机制：COPD / 肺气肿 + 肺纤维化（成纤维细胞 / 免疫） | 各最多 3 篇 | **另加**最多 3 篇 |
| 周四 08:00 | 肺动脉高压 / PAH + 流感病毒肺损伤 | 各最多 3 篇 | **另加**最多 3 篇 |

预印本不占用已发表额度，也不显示 IF / 分区。检索窗 **10 → 30 → 60 → 90 天** 逐步放宽。已推送 PMID / DOI 不重复。已发表与预印本都走 **NCBI PubMed / E-utilities**（预印本加 `preprint[pt]`），不再用 Europe PMC。

当前进度：邮件模板（header、logo、卡片、概述）已定型；首期 Monday 样刊在 [`archive/2026-09-12-monday.html`](archive/2026-09-12-monday.html)。周四共用同一套 renderer，只换蓝色 PAH 主题与对应 logo。

## 邮件版式（当前）

- **Header**：`chronic-lung-icon-108.png`（周一）或 `pah-icon-108.png`（周四），显示 54px，无色块底。邮件用 CID 内嵌；归档 HTML 用相对路径或 data URI。
- **概述**：本期期刊、研究亮点、时间概览分成三条 list，不再用分号揉成一段。
- **模块标题**：只写栏目名（如 `COPD / 肺气肿机制`、`预印本精选`），不跟 `（2）` / `+3`。篇数看顶部三格统计即可。栏目名里自带的括号（如 `肺纤维化（成纤维细胞 / 免疫）`）保留。
- **论文卡片**：杂志 / 文章 / 作者 / 机构用 chip 分行；EDITOR'S TAKE 只保留 AHA 式 **What Is New?**；**可借鉴之处** 放在后面的 AI 解读。

## 选题口径

- **COPD / 肺气肿**：肺泡破坏、稳态、再生、炎症细胞与肺泡损伤；尤其成纤维细胞和免疫细胞。
- **肺纤维化**：机制研究，尤其成纤维细胞、肌成纤维细胞与免疫互作。
- **PAH**：不限细分方向；优先 Circulation / Circulation Research / EHJ / ERJ / AJRCCM，其次 ATVB、Hypertension、Nature Communications 等。
- **流感肺损伤**：上皮 / 基底细胞 / 免疫，偏病毒模型与修复读出。
- 第一作者与通讯作者若同属一个大学 / 医院 / 研究所，机构栏合并，不拆开写。

## 期刊指标（本地固定表，运行时不联网）

邮件里的 IF / JCR / 中科院分区**只读仓库内两张表**，周报运行时不去 Clarivate、中科院或 LetPub 实时查询。

| 表 | 含义 | 当前年份 | 文件 |
| --- | --- | --- | --- |
| JCR IF | Journal Impact Factor + Quartile | **2025**（Clarivate 2026 年 6 月发布；LetPub 2026-06 核对） | [`data/jcr_if.yaml`](data/jcr_if.yaml) |
| 中科院分区 | 升级版大类分区 | **2025** | [`data/cas_zone.yaml`](data/cas_zone.yaml) |

表头 `year` / `retrieved` 必须与数据一致。个别刊在 `jcr_if.yaml` 里标了 `source:`：

- `letpub_2026_06`：已按 ISSN 在 LetPub 核对
- `user_confirmed`：人工确认的数字
- `carry_forward`：本次未重新核对，沿用上一版

表里没有的刊显示「未收录」，表示**本地表没有这条**。缺刊把 ISSN、IF、JCR、中科院分区发来即可补进表。

**已发表硬门槛（周一、周四相同）**：IF ≥ 5 **或** 中科院 2025 年 3 区及以上（满足其一）。排除 Frontiers、MDPI（DOI `10.3389` / `10.3390`）以及 config 里的其他出版社。表外期刊默认不入选。预印本不套用 IF / 分区门槛。

## 主题 Logo

周一与周四各一枚扁平双色肺标，母稿在 [`assets/logos/`](assets/logos/)。邮件头用 108 源图缩到 54px（Retina）；不要给 logo 再铺圆角色底，标题行会把色块拉高。重导 PNG：

```bash
python -m pip install pillow
python scripts/export_logos.py   # macOS：用 qlmanage 栅格化 SVG
```

## 为什么不用 Cloudflare

Cloudflare Workers / Cron 适合当闹钟，不适合跑 NCBI + LLM。云端用 **GitHub Actions**。本机 SMTP 有时会被校园网拦截，Actions 一般不受影响。

## 本地运行

Python 3.11+。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
python -m pulmoradar run --topic monday --dry-run
python -m pulmoradar run --topic thursday --dry-run
python -m pulmoradar run --topic monday --send
```

密钥放项目根目录 `.env`（已 gitignore）：`DEEPSEEK_API_KEY`、`SMTP_USERNAME`、`SMTP_PASSWORD`、可选 `NCBI_API_KEY`。

## GitHub Actions

Secrets 同上。手动运行选 `monday` / `thursday`。北京时间周一 / 周四 08:00 定时。
