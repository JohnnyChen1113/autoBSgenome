# AutoBSgenome Web Tool — 项目构想与可行性调查

> 最后更新：2026-04-02

---

## 一、为什么要做这件事

### 背景

[TSSr](https://github.com/ZhenghuoLin/TSSr) 是一个用于转录起始位点（TSS）分析的 R/Bioconductor 包，支持 CAGE-seq、TSS-seq 等多种 5' 端测序数据。TSSr **强依赖 BSgenome**——在读取 BAM 文件时需要 BSgenome 提供参考基因组序列，用于：

1. **染色体验证**：确认 reads 的染色体名和坐标在参考基因组范围内
2. **G-mismatch 校正**：CAGE 数据中逆转录酶会在 5' 端添加非模板 G 碱基，TSSr 需要 `getSeq()` 从 BSgenome 获取参考序列来检测和移除这些假 G

### 问题

有用户给导师发邮件，问 TSSr 能否移除 BSgenome 依赖。原因是：**构建自定义 BSgenome 包太难了。**

Bioconductor 上只有约 30 多个模式物种（人、鼠、酵母、果蝇等）有预构建的 BSgenome 包。研究非模式生物的用户必须自己"锻造"（forge）BSgenome 包，这个过程需要：

- 下载并配置 `faToTwoBit`（UCSC 的 C 语言工具，平台相关）
- 编写格式严格的 `.seed` 文件（DCF 格式，15+ 个字段）
- 安装完整的 R + Bioconductor 工具链
- 运行 `forgeBSgenomeDataPkg()` + `R CMD build` + `R CMD INSTALL`

对于不熟悉命令行的生物学家来说，这个门槛太高了。

### 已有方案

autoBSgenome（本项目）是一个交互式 CLI 工具，通过问答向导引导用户一步步完成 BSgenome 包的构建。但仍然需要用户具备：
- Python 环境
- R + Bioconductor 环境
- 命令行操作能力

**门槛依然太高。**

### 核心洞察

> 用户的真正诉求不是"移除 BSgenome"，而是"让 BSgenome 变得容易获取"。

如果我们能提供一个 **零门槛的网页工具**——用户只需填表 + 上传 FASTA，就能下载到可直接安装的 BSgenome 包——那就从根本上解决了这个问题，TSSr 也不需要移除 BSgenome 依赖。

### 可持续性原则

> **这个项目必须零运营成本。**

作为一个服务全球研究者的开源工具，但凡有一点点成本，时间久了个人都无法支撑。因此架构选择的第一优先级是：**所有组件必须在免费额度内运行。**

---

## 二、什么是 BSgenome

### 概述

BSgenome（Biostrings genome）是 Bioconductor 生态中用于高效存储和访问完整参考基因组序列的基础设施。一个 BSgenome **数据包**将整个基因组封装成一个 R 包。

### 特点

- **惰性加载**：加载包时不会读入全部基因组（人类基因组 ~3GB），只有访问某条染色体时才加载
- **标准接口**：`seqnames()`, `seqlengths()`, `getSeq()`, `$chr1` 等统一 API
- **广泛依赖**：motifmatchr、Gviz、GenomicFeatures、ChIPseeker 等大量下游工具都依赖 BSgenome

### 包结构

```
BSgenome.Organism.Provider.Build/
├── DESCRIPTION                      # R 包元数据
├── NAMESPACE                        # 导入/导出声明
├── R/zzz.R                         # .onLoad() 创建 BSgenome 对象
├── inst/extdata/
│   └── single_sequences.2bit       # 基因组序列（2-bit 压缩格式）
└── man/package.Rd                  # 帮助文档
```

### 构建痛点

| 痛点 | 说明 |
|------|------|
| seed 文件格式 | DCF 格式不直观，缺少尾部换行会导致解析失败 |
| faToTwoBit | 平台相关的二进制工具，需手动下载和配置 |
| IUPAC 歧义碱基 | 许多基因组 FASTA 含 N/Y/R/M 等，.2bit 只支持 A/C/G/T/N |
| 注册表限制 | `forgeBSgenomeDataPkgFromNCBI()` 只支持 GenomeInfoDb 已注册的组装 |
| 依赖链 | BSgenome → BSgenomeForge → BiocManager → R，任何一环出错都会阻塞 |
| 概念负担 | 15 个元数据字段，4 段式命名约定，对生物学家不友好 |

---

## 三、什么是 TSSr

### 功能

TSSr 提供完整的 TSS 数据分析流程：

1. **TSS 识别**：从 BAM/BED/BigWig 文件中提取 5' 端信号
2. **过滤**：基于 Poisson 统计移除噪声
3. **聚类**：将邻近 TSS 聚合为 tag clusters（代表核心启动子）
4. **一致性聚类**：跨样本识别可重复的聚类
5. **启动子形态分析**：分类为 sharp（单一主导 TSS）或 broad（分散型）
6. **基因注释**：将聚类映射到下游基因
7. **差异表达**：通过 DESeq2 检测差异 TSS 使用
8. **启动子漂移检测**：识别条件间的替代启动子使用
9. **增强子识别**：基于双向转录特征

### BSgenome 依赖方式

TSSr 在运行时动态加载 BSgenome：

```r
.getGenome <- function(genomeName) {
    if (genomeName %in% rownames(installed.packages()) == FALSE) {
        stop("Requested genome is not installed!")
    }
    requireNamespace(genomeName)
    getExportedValue(genomeName, genomeName)
}
```

如果用户的物种没有对应的 BSgenome 包，TSSr **直接报错拒绝运行**。

---

## 四、技术方案：零成本架构

### 设计原则

**所有组件必须在免费额度内运行**，确保项目可以无限期服务全球研究者而不产生任何运营成本。

### 架构总览

```
用户浏览器 (Cloudflare Pages, 免费)
    │
    ├── 填写表单 ──────→ Worker API (接收元数据, 已付费无额外成本)
    ├── 上传 FASTA ────→ R2 (presigned PUT URL 直传, 免费额度内)
    │
Worker 触发 GitHub Actions workflow (via repository_dispatch API)
    │
    └──→ GitHub Actions Runner (Ubuntu, 公开仓库完全免费)
         │
         ├── 从 R2 下载 FASTA
         ├── faToTwoBit fasta.fa genome.2bit
         ├── Rscript build.R (forgeBSgenomeDataPkg + R CMD build)
         ├── 上传 .tar.gz 到 R2
         └── 回调 Worker 通知完成
    │
Worker 生成 presigned GET URL → 用户下载 .tar.gz
```

### 各组件成本分析

| 组件 | 服务 | 免费额度 | 我们的用量 | 成本 |
|------|------|----------|-----------|------|
| **前端** | Cloudflare Pages | 无限站点、无限带宽 | 一个静态站 | **$0** |
| **API** | Cloudflare Workers | 已有 Paid Plan | API 请求量极小 | **$0**（已付） |
| **文件存储** | Cloudflare R2 | 10 GB 存储 / 月，Class A 1M 次 / 月，Class B 10M 次 / 月 | 临时存 FASTA + 包，用完即清 | **$0** |
| **计算** | GitHub Actions | 公开仓库：**无限分钟数** | 每次构建约 5-10 分钟 | **$0** |
| **总计** | | | | **$0 / 月** |

### GitHub Actions Runner 规格

| 资源 | 规格 |
|------|------|
| CPU | 4 vCPU (GitHub-hosted larger runner for public repos) |
| 内存 | 16 GB RAM |
| 磁盘 | 14 GB SSD |
| 系统 | Ubuntu 24.04 LTS |
| 单次上限 | 6 小时 |
| 预装 | R 已预装在 ubuntu-latest runner |

对于构建 BSgenome 包来说绰绰有余——即使是人类基因组（~3 GB FASTA）也能轻松处理。

### 详细流程

#### 1. 用户提交（前端 → Worker）

用户在 Cloudflare Pages 托管的网页上填写表单：

- 物种学名（如 *Aspergillus luchuensis*）
- 常用名（如 Awamori koji mold）
- 基因组组装 ID（如 IFO4308）
- 数据提供者（NCBI / UCSC / 其他）
- 上传 FASTA 文件

Worker 接收元数据，生成 R2 presigned PUT URL 返回给前端。

#### 2. 文件上传（前端 → R2）

前端使用 presigned URL 将 FASTA 直传到 R2，**不经过 Worker**（绕过 Worker 的内存限制）。支持大文件 multipart 上传。

#### 3. 触发构建（Worker → GitHub Actions）

上传完成后，Worker 通过 GitHub API 发送 `repository_dispatch` 事件：

```json
{
  "event_type": "build_bsgenome",
  "client_payload": {
    "job_id": "uuid-xxx",
    "package_name": "BSgenome.Aluchuensis.NCBI.IFO4308",
    "organism": "Aspergillus luchuensis",
    "common_name": "Awamori koji mold",
    "genome": "IFO4308",
    "provider": "NCBI",
    "fasta_r2_key": "uploads/uuid-xxx/genome.fa",
    "callback_url": "https://api.autobsgenome.dev/callback/uuid-xxx"
  }
}
```

#### 4. 构建执行（GitHub Actions）

GitHub Actions workflow：

```yaml
name: Build BSgenome Package
on:
  repository_dispatch:
    types: [build_bsgenome]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Download FASTA from R2
        # 使用 AWS CLI (S3 兼容) 从 R2 下载

      - name: Install faToTwoBit
        run: |
          wget -q https://hgdownload.cse.ucsc.edu/admin/exe/linux.x86_64/faToTwoBit
          chmod +x faToTwoBit

      - name: Convert FASTA to 2bit
        run: ./faToTwoBit genome.fa genome.2bit

      - name: Setup R and Bioconductor
        uses: r-lib/actions/setup-r@v2

      - name: Install R dependencies
        uses: r-lib/actions/setup-r-dependencies@v2
        # 缓存 BSgenome, BSgenomeForge 等依赖

      - name: Generate seed file and build package
        run: Rscript build_bsgenome.R

      - name: Upload result to R2
        # 将 .tar.gz 上传回 R2

      - name: Notify completion
        # 回调 Worker API 通知构建完成
```

#### 5. 结果交付（R2 → 用户）

Worker 收到回调后，生成 R2 presigned GET URL（有效期如 24 小时），通过前端轮询或 WebSocket 通知用户下载。

### R2 存储管理

为确保不超出 10 GB 免费额度：

- 上传的 FASTA：构建完成后立即删除
- 生成的 .tar.gz：保留 24-48 小时后自动清理（R2 Lifecycle Rules）
- 相同参数的重复构建：可做简单缓存（包名 + FASTA hash 去重）

### 被排除的方案及原因

| 方案 | 排除原因 |
|------|----------|
| Cloudflare Containers | 按用量计费，无免费额度，长期不可持续 |
| Cloudflare Workflows | 配合 Containers 使用，同样有成本 |
| Workers 直接跑计算 | 128 MB 内存硬限制，不支持原生二进制 |
| webR（浏览器端 R） | 内存不足，Bioconductor 包兼容性差 |
| faToTwoBit → WASM | 无人做过，大文件处理受限 |
| 任何付费 VPS / 云函数 | 违反零成本原则 |

---

## 五、用户体验目标

### 最简流程（目标）

1. 用户打开网页
2. 填写 5-7 个必填字段（物种名、组装 ID、提供者等）
3. 上传 FASTA 文件（支持拖拽）
4. 点击"Build"
5. 等待几分钟（显示进度条 / 状态轮询）
6. 下载 `.tar.gz`，本地 `R CMD INSTALL` 即可使用

### 预期等待时间

| 阶段 | 首次 | 有缓存 |
|------|------|--------|
| GitHub Actions 启动 | ~15-30s | ~15-30s |
| 安装 R 依赖 | ~3-5 min | ~30s（缓存命中） |
| faToTwoBit 转换 | ~10s-2min（视基因组大小） | 同左 |
| R 包构建 | ~30s-2min | 同左 |
| **总计** | **~5-10 分钟** | **~2-4 分钟** |

### 进阶功能（后续迭代）

- **NCBI Accession 自动下载**：用户只输入 GCF_/GCA_ 编号，GitHub Actions 直接从 NCBI FTP 下载 FASTA，用户连文件都不用上传
- **构建缓存**：相同基因组不重复构建，直接返回已有结果
- **在线安装命令**：提供类似 `install.packages("url", repos=NULL)` 的一键安装
- **BSgenome 社区仓库**：用户构建的包自愿共享，形成一个 mini-CRAN 风格的非模式生物 BSgenome 仓库

---

## 六、下一步

1. **搭建前端原型**：Cloudflare Pages 上的简洁表单，连接 Worker API
2. **编写 GitHub Actions workflow**：包含 R 依赖缓存、faToTwoBit、BSgenomeForge 构建全流程
3. **Worker API**：处理元数据、生成 R2 presigned URL、触发 GitHub Actions、接收回调
4. **端到端测试**：用 test_data 中的 *Aspergillus luchuensis* 数据验证全流程
5. **R2 生命周期管理**：自动清理过期文件，确保存储在免费额度内
