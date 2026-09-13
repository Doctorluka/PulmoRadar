# PulmoRadar

肺部与肺血管 **basic research** 的每周文献雷达。从 PubMed 检索已发表论文和预印本，按机制向口径筛选，再用 DeepSeek 选题并写中文解读，输出 HTML 邮件和 `archive/` 归档。

| 时间（北京） | 主题 | 已发表 | 预印本 |
| --- | --- | --- | --- |
| 周一 08:00 | 慢性肺病机制：COPD / 肺气肿 + 肺纤维化（成纤维细胞 / 免疫） | **各恰好 3 篇** | **恰好 3 篇** |
| 周四 08:00 | 肺动脉高压 / PAH + 流感病毒肺损伤 | **各恰好 3 篇** | **恰好 3 篇** |

每栏 3 篇是硬配额，凑不齐就失败、不发信。已发表三篇角色固定：**近一月高质量**、**年内旗舰系统研究**、**领域经典**。预印本只要 3 篇，不拆角色。已推送的 PMID / DOI 记在 `data/history.json`。已发表与预印本都走 **NCBI PubMed / E-utilities**（预印本加 `preprint[pt]`）。

样刊：[`archive/2026-09-12-monday.html`](archive/2026-09-12-monday.html)、[`archive/2026-09-12-thursday.html`](archive/2026-09-12-thursday.html)。周四共用同一套 renderer，换蓝色 PAH 主题和对应 logo。

## 流水线

1. **检索**：每个已发表 track 拉「近 1 年最新」+「约 20 年 relevance」两路 PubMed，合并去重。预印本仍按 10 → 30 → 60 → 90 天扩窗。
2. **硬过滤**：丢掉综述 / Editorial / Letter / Case Report 等；丢掉纯临床试验；丢掉已推送条目；丢掉 Frontiers、MDPI 等出版社。
3. **质量门槛**（只对已发表，满足其一即可）：**IF > 5**，或 **中科院 2025 大类 2 区及以上**，或 **新锐 2026 大类 2 区及以上**。表外期刊默认不入选。预印本不套这道门。
4. **三槽选题**（质量优先，新近度只做近一月槽的排序）：
   - 第 1 篇：近 30 天里最新的高质量论文；不够则回退 90 天，再回退到质量最高篇。
   - 第 2 篇：近 1 年、CNS / 大子刊 / 领域旗舰上的系统机制研究；不够则回退到一年内高质量。
   - 第 3 篇：领域或子方向奠基性论文，可超出常规时间窗。
5. **输出**：HTML 邮件 + `archive/{date}-{topic}.html` / `.md`。`--send` 才会发信并写入 history。凑不齐 3 篇会 `QuotaError`。

云端由 [GitHub Actions](.github/workflows/digest.yml) 在北京时间周一、周四 08:00（UTC 00:00）跑 `python -m pulmoradar run --topic … --send`，并把更新后的 history 与 archive 提交回仓库。

## 选题口径

- **COPD / 肺气肿**：肺泡破坏、稳态、再生，以及炎症细胞与肺泡损伤；尤其成纤维细胞和免疫细胞。
- **肺纤维化**：机制研究，尤其成纤维细胞、肌成纤维细胞与免疫互作。
- **PAH**：不限细分方向；优先 Circulation / Circulation Research / EHJ / ERJ / AJRCCM，其次 ATVB、Hypertension、Nature Communications 等。
- **流感肺损伤**：上皮 / 基底细胞 / 免疫，偏病毒模型和修复读出。

第一作者与通讯作者若同属一个大学 / 医院 / 研究所，机构栏合并。

## 期刊指标

邮件里的 IF / JCR / 中科院 / 新锐分区只读仓库内本地表，运行时不联网查询。

| 表 | 含义 | 年份 | 文件 |
| --- | --- | --- | --- |
| JCR IF | Journal Impact Factor + Quartile | 2025（Clarivate 2026 年 6 月；LetPub 2026-06 核对） | [`data/jcr_if.yaml`](data/jcr_if.yaml) |
| 中科院分区 | 升级版大类分区 | 2025 | [`data/cas_zone.yaml`](data/cas_zone.yaml) |
| 新锐分区 | XinRui Journal Ranking 大类 | 2026 年 3 月 | [`data/xinyue_zone.yaml`](data/xinyue_zone.yaml) |
| 期刊档 | CNS / 大子刊 / 旗舰，供年内槽使用 | — | [`data/journal_tiers.yaml`](data/journal_tiers.yaml) |

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
