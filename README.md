# PulmoRadar

肺部与肺血管 **basic research** 的每周文献雷达。从 PubMed 检索已发表论文和预印本，按机制向口径筛选，再用 DeepSeek 选题并写中文解读，输出 HTML 邮件和 `archive/` 归档。

| 时间（北京） | 主题 | 已发表 | 预印本 |
| --- | --- | --- | --- |
| 周一 08:00 | 慢性肺病机制：COPD / 肺气肿 + 肺纤维化（成纤维细胞 / 免疫） | 各最多 3 篇 | 另加最多 3 篇 |
| 周四 08:00 | 肺动脉高压 / PAH + 流感病毒肺损伤 | 各最多 3 篇 | 另加最多 3 篇 |

预印本不占用已发表额度，也不显示 IF / 分区。检索窗按 **10 → 30 → 60 → 90 天** 放宽，直到候选池够用。已推送的 PMID / DOI 记在 `data/history.json`，不会重复入选。已发表与预印本都走 **NCBI PubMed / E-utilities**（预印本加 `preprint[pt]`）。

样刊：[`archive/2026-09-12-monday.html`](archive/2026-09-12-monday.html)、[`archive/2026-09-12-thursday.html`](archive/2026-09-12-thursday.html)。周四共用同一套 renderer，换蓝色 PAH 主题和对应 logo。

## 流水线

1. **检索**：按 `config.yaml` 里各 track 的 query 拉 PubMed；窗口不够就沿梯子放宽。
2. **硬过滤**：丢掉综述 / Editorial / Letter / Case Report 等；丢掉纯临床试验；丢掉已推送条目；丢掉 Frontiers、MDPI 等配置里的出版社。
3. **质量门槛**（只对已发表）：本地期刊表里 **IF ≥ 5 或 中科院 2025 年 3 区及以上**（满足其一）。表外期刊默认不入选。预印本不套这道门。
4. **选题与解读**：关键词 / 旗舰期刊加分 → DeepSeek screening / ranking → 补全文与 graphical abstract → 中文分析。
5. **输出**：HTML 邮件 + `archive/{date}-{topic}.html` / `.md`。`--send` 才会发信并写入 history。

云端由 [GitHub Actions](.github/workflows/digest.yml) 在北京时间周一、周四 08:00（UTC 00:00）跑 `python -m pulmoradar run --topic … --send`，并把更新后的 history 与 archive 提交回仓库。

## 选题口径

- **COPD / 肺气肿**：肺泡破坏、稳态、再生，以及炎症细胞与肺泡损伤；尤其成纤维细胞和免疫细胞。
- **肺纤维化**：机制研究，尤其成纤维细胞、肌成纤维细胞与免疫互作。
- **PAH**：不限细分方向；优先 Circulation / Circulation Research / EHJ / ERJ / AJRCCM，其次 ATVB、Hypertension、Nature Communications 等。
- **流感肺损伤**：上皮 / 基底细胞 / 免疫，偏病毒模型和修复读出。

第一作者与通讯作者若同属一个大学 / 医院 / 研究所，机构栏合并。

## 期刊指标

邮件里的 IF / JCR / 中科院分区只读仓库内两张表，运行时不联网查询。

| 表 | 含义 | 年份 | 文件 |
| --- | --- | --- | --- |
| JCR IF | Journal Impact Factor + Quartile | 2025（Clarivate 2026 年 6 月；LetPub 2026-06 核对） | [`data/jcr_if.yaml`](data/jcr_if.yaml) |
| 中科院分区 | 升级版大类分区 | 2025 | [`data/cas_zone.yaml`](data/cas_zone.yaml) |

表头 `year` / `retrieved` 必须与数据一致。`jcr_if.yaml` 里个别刊会标 `source:`：`letpub_2026_06`（已按 ISSN 核对）、`user_confirmed`（人工确认）、`carry_forward`（沿用上一版）。表里没有的刊显示「未收录」。

## 邮件版式

- **Header**：周一 `chronic-lung-icon-108.png`，周四 `pah-icon-108.png`，显示 54px。邮件用 CID 内嵌；归档 HTML 用 data URI。
- **概述**：本期期刊、研究亮点、时间概览分成三条 list。
- **栏目标题**：只写栏目名，篇数看顶部统计。
- **论文卡片**：杂志 / 文章 / 作者 / 机构分行；EDITOR'S TAKE 只保留 **What Is New?**；**可借鉴之处** 放在 AI 解读里。

Logo 母稿在 [`assets/logos/`](assets/logos/)。重导 PNG：

```bash
python -m pip install pillow
python scripts/export_logos.py
```

## 本地运行

Python 3.11+。密钥放项目根目录 `.env`（已 gitignore）：`DEEPSEEK_API_KEY`、`SMTP_USERNAME`、`SMTP_PASSWORD`，可选 `NCBI_API_KEY`。收件人、抄送和检索式在 `config.yaml`。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
python -m pulmoradar run --topic monday --dry-run
python -m pulmoradar run --topic thursday --dry-run
python -m pulmoradar run --topic monday --send
```

`--topic` 也可直接跑单个 track：`copd` / `fibrosis` / `pah`。`--dry-run` 跳过 LLM 和发信，只用启发式排序。

## GitHub Actions

仓库 Secrets 与本地 `.env` 同名：`DEEPSEEK_API_KEY`、`SMTP_USERNAME`、`SMTP_PASSWORD`、可选 `NCBI_API_KEY`。Actions 页可手动选 `monday` / `thursday` 跑一期。
