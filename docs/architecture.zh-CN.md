# TypEng 架构

当前重构遵循一个边界：词典数据描述“一个词有什么含义和例句”，学习数据描述“用户在哪个词库中如何学习它”。两者不再长期混在同一行中。

## 模块边界

```text
app.py                         Flask 路由与请求/会话适配
typeng/domain.py               无 Flask、无数据库的领域规则
typeng/dictionaries/           ECDICT、Wiktionary 数据源适配器
typeng/cefr.py                 EFLLex 难度画像导入
typeng/db.py                   SQLite 连接配置
typeng/schema.py               建表和版本迁移
typeng/repositories/           SQL 查询与持久化
typeng/services/               学习、复习等用例编排
typeng/entities.py             Word、Sense、Example 领域实体
```

路由可以读取表单和 session，但不应包含大段词典解析或 SQL；仓储只负责数据访问，不依赖 Flask；领域函数应可以在不启动服务器时测试。

## 统一词汇模型

```text
lexemes (Word)
    └── senses (Sense)
            └── sense_examples (Example)

words（词库成员 + 学习进度）
    └── word_sense_links ──────┘
```

- `lexemes`：规范化后的英文词形，同一个词只保存一次。
- `senses`：词性、中文释义、英文定义、音标、频率和来源信息。
- `sense_examples`：明确属于某个义项的例句，而不是只属于一个拼写。
- `words`：暂时保留旧表名，负责词库归属、掌握状态、复习日期和答题统计。
- `word_sense_links`：兼容旧学习记录与新词义模型的桥接表。

应用数据库版本 2 会自动、幂等地把已有 `words` 数据投影到新模型。旧表暂不删除，因此已有用户数据和现有页面无需一次性重写；新导入的数据会同时建立词义链接。版本 3 移除了不再使用的 WordNet 缓存。

## 词典数据源

ECDICT 负责中文释义、词频和考试候选标签；Wiktionary 提供例句、英文释义和开放的词形/词性验证。预设词库使用从完整 Kaikki 快照生成的小型词性存在索引；只有在索引可用且规范化词性仍不匹配时才清理该候选。是否存在可用例句不参与删除判断。

EFLLex 只用于剔除能够确定过于基础的候选：中考 A1+、高考 A2+、四级 B1+，其余考试 B2+。没有 EFLLex 分级的词全部保留。相关规则集中在 `typeng/preset_policy.py`，清理结果可由 `scripts/audit_preset_policy.py` 复现。
