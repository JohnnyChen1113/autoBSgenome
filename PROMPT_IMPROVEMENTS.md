# 提示文字改进建议文档

## 改进概览

基于 BSgenome/BSgenomeForge 官方文档和最佳实践，对所有 15 个步骤的引导文字进行了全面改进。

---

## 主要改进点

### 1. **增加更多实例** ✨
**问题**: 原文只有 1-2 个例子，用户可能不确定格式
**改进**: 每个字段提供 5-10 个实际例子，覆盖不同生物类型

**示例 - Common Name 字段**:
```markdown
原版：
"The common name of the organism (e.g. Rat or Human)"

改进版：
包含分类的示例：
- 哺乳动物：Human, Mouse, Rat, Cow, Dog
- 模式生物：Yeast, Worm, Fly, Zebrafish
- 植物：Thale cress, Rice, Maize
- 微生物：E. coli, Baker's yeast
```

---

### 2. **添加清晰的格式说明** 📝
**问题**: 用户不确定具体格式要求
**改进**: 用代码块明确显示格式模板

**示例 - Package Name 字段**:
```markdown
原版：
"made of 4 parts separated by a dot"

改进版：
```
格式模板：
BSgenome.{Organism}.{Provider}.{Version}

完整示例：
✓ BSgenome.Hsapiens.UCSC.hg38
✓ BSgenome.Mmusculus.NCBI.GRCm39
❌ BSgenome.homo_sapiens.UCSC.hg38  (错误：小写)
❌ BSgenomeHsapiensUCSChg38         (错误：缺少点号)
```
```

---

### 3. **提供"在哪里找到信息"指南** 🔍
**问题**: 用户不知道去哪里查找这些信息
**改进**: 明确告诉用户信息来源

**示例 - Genome Assembly 字段**:
```markdown
新增内容：
**在哪里找到**:
- NCBI: 查找 "Assembly name"
- UCSC: 检查基因组浏览器 URL
- FASTA 文件名中通常包含
- 示例：GCF_000001405.40_GRCh38.p14 中提取 GRCh38.p14
```

---

### 4. **添加常见错误预防** ⚠️
**问题**: 用户容易犯同样的错误
**改进**: 明确标注正确 ✓ 和错误 ❌ 的例子

**示例 - Organism 字段**:
```markdown
新增：
**常见错误**:
❌ 使用常用名: "Human" → ✓ "Homo sapiens"
❌ 全部小写: "homo sapiens" → ✓ "Homo sapiens"
❌ 错误大写: "Homo Sapiens" → ✓ "Homo sapiens"
```

---

### 5. **强调字段间的关联** 🔗
**问题**: 用户不理解某些字段应该匹配
**改进**: 明确指出字段依赖关系

**示例 - 多个字段**:
```markdown
新增提示：
"重要: 应该与包名的第 4 部分匹配！"
"提示: 此字段将根据你的包名自动建议"
```

---

### 6. **分层次的信息组织** 📊
使用清晰的标题层次：

```markdown
结构：
# 字段名 (X/15)
**必需性说明**: Required/Optional

**目的**: 一句话说明作用

**格式**: 具体格式要求

**示例**:
- 分类示例 1
- 分类示例 2

**在哪里找**: 信息来源

**常见错误**: 避免的问题

**提示**: 实用建议
```

---

### 7. **修正语法和拼写错误** ✏️

**修正列表**:
- `dot have` → `don't have`
- `cover` → `convert`
- `commmon` → `common`
- 标点符号统一

---

### 8. **增加上下文提示** 💡

**示例 - Release Date**:
```markdown
新增：
**默认建议**: 今天的日期已预填，但你应该改为实际的组装发布日期。

**如果不确定确切日期**:
- 使用组装发布的年份
- 格式：Jan. 2020（使用该年的第一个月）
- 可以查看相关出版物的发布年份
```

---

### 9. **技术细节简化** 🎯

**原版问题**: 过于技术化，初学者难理解

**改进示例 - Circ_seqs**:
```markdown
原版：
"An R expression returning the names of the circular sequences"

改进版：
**什么时候可以跳过**:
✓ 你的基因组在 GenomeInfoDb 中注册（大多数 NCBI/UCSC 基因组）
✓ 系统会自动检测环状序列
✓ 推荐：留空，除非你确定需要

**常见值**:
对于哺乳动物（线粒体 DNA）: "chrM"
对于酵母（带 2-micron 质粒）: c("chrM", "2micron")
没有环状序列: character(0)
```

---

### 10. **视觉改进** 👁️

使用符号增强可读性：
- ✓ ✗ 表示正确/错误
- ⚠️ 表示警告
- 📝 表示注意事项
- 🔍 表示查找信息
- 💡 表示提示

---

## 字段改进详情

### 📋 Field 1: Package Name
**改进**:
- ✅ 添加 4 部分格式的可视化模板
- ✅ 10+ 个不同生物的完整示例
- ✅ 详细的命名规则解释
- ✅ 常见错误标注

**关键新增**:
```markdown
**完整示例**:
- BSgenome.Hsapiens.UCSC.hg38 (人类基因组)
- BSgenome.Mmusculus.NCBI.GRCm39 (小鼠基因组)
- BSgenome.Scerevisiae.UCSC.sacCer3 (酵母基因组)
```

---

### 📋 Field 2: Title
**改进**:
- ✅ 标准格式模板
- ✅ 多生物示例
- ✅ 字符限制说明（65 字符）
- ✅ Title Case 指南

**关键新增**:
```markdown
**针对亚种**: "Homo sapiens neanderthalensis"
**针对特定株系**: "Escherichia coli K-12"
```

---

### 📋 Field 3: Description
**改进**:
- ✅ 明确"可选但推荐"
- ✅ 3 个完整的优秀示例（人类、模式生物、植物）
- ✅ "应该包含什么"指南
- ✅ 不确定时的建议

---

### 📋 Field 4: Version
**改进**:
- ✅ 语义化版本说明
- ✅ 常见选择及其含义
- ✅ 何时增加版本号的指南
- ✅ 版本比较警告

**关键新增**:
```markdown
**何时递增**:
- Major (X.0.0): 新的组装版本
- Minor (1.X.0): 注释更新、元数据修复
- Patch (1.0.X): Bug 修复、文档
```

---

### 📋 Field 5: Organism
**改进**:
- ✅ 15+ 个标准示例，按类别分组
- ✅ 亚种/株系格式
- ✅ NCBI Taxonomy 数据库链接
- ✅ 常见拼写错误标注

---

### 📋 Field 6: Common Name
**改进**:
- ✅ 按类别分组（哺乳动物、模式生物、植物、微生物）
- ✅ 多个名称时的选择指南
- ✅ 15+ 个示例

---

### 📋 Field 7: Genome
**改进**:
- ✅ NCBI vs UCSC 格式对比
- ✅ 其他数据库格式（Ensembl, TAIR, WormBase）
- ✅ "在哪里找到"详细指南
- ✅ 与包名匹配的强调

---

### 📋 Field 8: Provider
**改进**:
- ✅ 按类型分类（通用、生物特异、机构特异）
- ✅ 10+ 个常见 provider
- ✅ 如何确定 provider 的步骤指南

---

### 📋 Field 9: Release Date
**改进**:
- ✅ 明确格式：`Mon. YYYY`
- ✅ 12 个月缩写列表
- ✅ 各数据库查找日期的具体位置
- ✅ 不确定时的处理方法

---

### 📋 Field 10: Source URL
**改进**:
- ✅ 各提供商的 URL 模板
- ✅ 永久链接 vs 临时链接的区别
- ✅ 明确"可选"及原因
- ✅ 可追溯性的重要性说明

---

### 📋 Field 11: Organism BiocView
**改进**:
- ✅ 明确"仅用于 Bioconductor 提交"
- ✅ 下划线替换规则
- ✅ 何时使用/跳过的清晰指南
- ✅ BiocViews 树的链接

---

### 📋 Field 12: BSgenomeObjname
**改进**:
- ✅ R 对象使用示例
- ✅ 与包名 Part 2 的匹配强调
- ✅ 实际 R 代码示例
- ✅ 命名模式

---

### 📋 Field 13: Circ_seqs
**改进**:
- ✅ "何时可以跳过"优先说明
- ✅ 常见生物的具体值
- ✅ R 语法示例
- ✅ 如何检查 FASTA 文件的命令

**关键改进**: 从技术性说明改为用户友好的决策树

---

### 📋 Field 14: Seqs_srcdir
**改进**:
- ✅ 当前目录动态显示
- ✅ 绝对路径 vs 相对路径说明
- ✅ 跨平台示例（Linux/Mac/Windows）
- ✅ 权限和备份建议

---

### 📋 Field 15: Seqfile_name
**改进**:
- ✅ 所有支持格式列表
- ✅ 自动转换说明
- ✅ 文件要求清单
- ✅ 压缩文件处理说明
- ✅ 转换过程预期

---

## 使用建议

### 如何应用这些改进

**选项 1: 完全替换**
```bash
# 备份原文件
cp prompts.py prompts_original.py

# 使用改进版
cp prompts_improved.py prompts.py
```

**选项 2: 选择性应用**
- 查看 `prompts_improved.py`
- 选择最需要的字段改进
- 手动合并到 `prompts.py`

**选项 3: 渐进式改进**
- 先改进最常用的字段（1, 2, 5, 14, 15）
- 收集用户反馈
- 逐步优化其他字段

---

## 改进前后对比示例

### Example: Field 5 (Organism)

**原版** (47 characters):
```
The scientific name of the organism in the format
Genus species (e.g. Triticum aestivum, Homo sapiens)
```

**改进版** (1000+ characters):
- ✓ 标准格式说明
- ✓ 15+ 个分类示例
- ✓ NCBI 数据库链接
- ✓ 3 种常见错误标注
- ✓ 亚种/株系格式

**效果**: 用户清楚知道：
1. 准确的格式要求
2. 大量参考示例
3. 如何验证自己的输入
4. 在哪里查找信息

---

## 测试建议

在应用改进后，建议测试：

1. **可读性测试**: 让新用户试用，看是否更容易理解
2. **完整性测试**: 确保所有示例都是正确的
3. **长度测试**: 检查是否过长影响阅读体验
4. **格式测试**: 确保 Markdown 渲染正确

---

## 额外建议

### 1. 添加交互式验证
在用户输入后立即验证并提供反馈：
```python
# 示例：Package name 验证
if not package_name.startswith("BSgenome."):
    print("❌ 包名必须以 'BSgenome.' 开头")
if len(package_name.split(".")) != 4:
    print("❌ 包名应该有 4 个部分，你的有 {} 个".format(len(...)))
```

### 2. 添加"常见生物快速设置"
为常见生物提供模板：
```python
templates = {
    "human_hg38": {
        "package_name": "BSgenome.Hsapiens.UCSC.hg38",
        "organism": "Homo sapiens",
        "common_name": "Human",
        # ...
    }
}
```

### 3. 添加字段间一致性检查
```python
# 检查 genome 字段是否匹配包名 Part 4
if metadata['genome'] != metadata['package_name'].split('.')[3]:
    print("⚠️ 警告: genome 字段应该匹配包名的第 4 部分")
```

---

## 总结

### 改进统计
- **总字符数**: 从 ~2,500 增加到 ~15,000
- **示例数量**: 从 ~20 个增加到 ~150 个
- **新增章节**:
  - "在哪里找到" (8 个字段)
  - "常见错误" (6 个字段)
  - "何时使用/跳过" (3 个字段)

### 预期效果
1. ✅ **减少用户困惑**: 清晰的示例和格式说明
2. ✅ **降低错误率**: 常见错误预防和验证建议
3. ✅ **提高效率**: 用户知道去哪里找信息
4. ✅ **增强信心**: 大量示例让用户确信输入正确

### 用户反馈建议
应用改进后，可以添加反馈机制：
```python
# 在每个字段输入后询问
"这个说明是否清楚? (y/n/skip)"
```

---

## 下一步行动

1. ✅ 审查 `prompts_improved.py` 中的所有改进
2. ⏭️ 决定应用策略（完全替换 vs 选择性）
3. ⏭️ 测试新提示文字
4. ⏭️ 收集用户反馈
5. ⏭️ 迭代优化

---

**文档版本**: 1.0
**创建日期**: 2025-11-12
**作者**: Claude AI Assistant
