# 推荐系统 AI 升级技术方案（v1.0）

> 目标：把现有「多路召回 + 手工权重融合」升级为「多路召回 + 双塔语义召回 + DeepFM 精排 + LLM 可解释推荐」，
> 并建立离线评测体系，让简历上每个数字都有真实出处。
> 预计总工期：**8 个工作日**（每天 3~4 小时）。环境：Windows + CPU，无需 GPU。

## 一、目标架构

```
[现有]
Vue3 → Spring Boot → 并行: ItemCF/UserCF/内容/热度 → 手工加权合并 → Top-N

[升级后]
Vue3 → Spring Boot 编排
  召回层: ① ItemCF/UserCF/内容/热度（现有，保留）
          ② 双塔语义召回（新增，Faiss 向量检索）
  精排层: DeepFM 打分（新增，替代手工加权，ONNX 推理）
  解释层: LLM 推荐理由（新增）
  数据层: MySQL（主数据）/ Redis（相似度 + 缓存 + 向量）
Python 离线侧: 导出 → 切分 → 训练 → 评测 → 导出 ONNX / Embedding
```

关键原则：**离线训练与在线服务解耦**——Python 负责训练和评测，Java 只做推理调用；模型挂了自动降级回现有手工加权逻辑（服务稳定性故事）。

## 二、新增目录结构

```
data/dl/                      # Python 离线侧（新建）
  export_data.py              # 从 MySQL 导出 ratings/books 为 CSV
  split.py                    # 留一法 + 时间序切分
  metrics.py                  # HR@K / Recall@K / NDCG@K
  baseline.py                 # 基线实现（热门/ItemCF/手工加权混合）
  deepfm.py                   # DeepFM 训练 + 评测 + 导出 ONNX
  two_tower.py                # 双塔训练 + 导出 Embedding + Faiss 索引
  build_book_embeddings.py    # 书籍文本向量化（RAG 用）
  eval_report.py              # 汇总各轮实验指标表

backend/src/main/java/com/bookrecommend/backend/
  controller/RankController.java        # /api/rank（DeepFM 精排，调用模型服务）
  service/RecommendReasonService.java   # LLM 推荐理由生成
  controller/SearchController.java      # /api/search/nl 自然语言找书（RAG）
  controller/BehaviorController.java    # 埋点上报（behavior 表已存在）

model-service/                # 模型推理服务（FastAPI + ONNX，新容器）
  main.py                     # /rank /embed 两个接口
  Dockerfile
```

## 三、模块设计

### 模块 1：数据导出（0.5 天）

`export_data.py`：从 MySQL 导出两张表——

- `ratings.csv`：user_id, book_id, score（约 20 万条）
- `books.csv`：id, title, author, category, publisher, publish_year（约 2,046 本，category 已由 classify_books.py 打好）

### 模块 2：切分 + 离线评测框架 + 基线（1 天）——**最重要，先做**

**切分**（`split.py`）：按用户留一法——每个用户的**最后一条**评分进测试集，其余进训练集；只保留评分 ≥ 3 条的用户进测试集。严格禁止随机切分（泄漏）。

**指标**（`metrics.py`）：

```python
HR@K    = 测试集用户中，真实评分书出现在推荐列表前 K 名的比例
Recall@K = 命中的真实评分书 / 该用户测试集评分数
NDCG@K  = 带位置权重的命中质量（排名越靠前分越高）
```

**基线**（`baseline.py`）：用 Python 复刻现有系统的三个参照算法——全局热门、ItemCF（余弦相似度）、手工加权混合（按现有 computeWeights 逻辑）——跑同一测试集，输出 baseline_report.md。

**产出 → 简历**：这是"基线 17%、HR@10 23%"等数字里**"基线"部分的唯一合法来源**。之后的每个模型都跟这张表对比。

### 模块 3：DeepFM 精排（2 天）

**样本构造**：score ≥ 7 → 正样本（label=1），负样本按**流行度^0.75 加权采样**，正负比 1:4。

**特征**（全部来自真实数据，无需伪造）：
- 稀疏 ID 特征：user_id、book_id、category、author、publisher
- 统计特征：用户历史评分次数/均值、物品被评次数/均值/流行度（只用训练集计算，防泄漏）

**结构**：稀疏特征 embedding（16 维）→ FM 二阶交叉 + DNN（64→32）→ sigmoid。

**训练**：BCE 损失，Adam（lr=1e-3），batch 4096，dropout 0.2，early stopping（val AUC），epochs ≤ 10。数据小，CPU 半小时内收敛。

**评测**：对每个测试用户——各召回通道并集取 Top-100 候选 → DeepFM 打分 → 取 Top-10 → 计算 HR@10 / NDCG@10，与基线报告对比。

**产出 → 简历**：这是"**相比人工加权基线，NDCG@10 提升 xx%**"的合法来源。

**导出**：`deepfm.onnx`（onnxruntime 推理）。

### 模块 4：双塔语义召回（2 天）

- **User Tower**：user_id embedding(32) + 用户统计特征 → 32 维向量（L2 归一化）
- **Item Tower**：book_id embedding(32) + category/author embedding + 物品统计特征 → 32 维向量
- **训练**：in-batch 负采样 InfoNCE 损失，temperature 0.05，batch 2048
- **导出**：`item_emb.npy` → Faiss IndexFlatIP（2,046 本书，索引秒建）
- **在线**：实时算 user vector → Faiss 检索 Top-100 → 汇入融合召回池
- **评测**：单独汇报双塔召回 HR@100

**产出 → 简历**：这是"双塔模型 + Faiss 向量检索实现语义召回"的合法来源。

### 模块 5：模型服务化（1 天）

**方案 A（推荐）**：`model-service/` FastAPI 容器，onnxruntime 加载 DeepFM + 双塔 Embedding，提供 `/rank`、`/embed` 两个接口；Spring Boot 通过 WebClient 调用，**3 秒超时降级**——模型服务不可用时自动回落现有手工加权逻辑。docker-compose 新增一个容器。

**方案 B（备选）**：`onnxruntime-java` 在 JVM 内直接推理，少一个服务，但少了"算法侧/工程侧解耦"的故事。

**产出 → 简历**："FastAPI 模型服务化 + 超时降级"的合法来源；顺便用压测拿到 P95 延迟数字。

### 模块 6：LLM 推荐理由（0.5 天）

- 输入：用户画像（高分书 Top 分类/作者）+ 推荐书信息（title/author/category）
- Prompt 模板 + JSON 输出约束（理由一句话，引用用户历史偏好）
- 生成时机：后端批量生成，结果按 (userId, bookId) 存 Redis 缓存，避免重复调用
- 接口：推荐响应附带 `reason` 字段，前端 BookCard 展示

**产出 → 简历**："推荐结果 100% 附带个性化解释"——覆盖率的真实统计口径。

### 模块 7：RAG 语义找书（1 天）

- **离线**：`build_book_embeddings.py` 将 2,046 本书的 title + category + author 用 bge-small-zh（CPU 可跑，~10 分钟）生成向量，存 Redis
- **在线**：`POST /api/search/nl` → query 向量化 → 余弦 Top-10 → 可选 LLM 组织自然语言回答
- **评测**：手工构造 50 条查询（分类词/作者词/整句语义），计算 Top-5 命中率

**产出 → 简历**："RAG 检索链路 + 语义检索 Top-5 命中率"的合法来源。

### 模块 8：AB 实验 + 埋点（0.5 天）

- 前端埋点：曝光/点击上报 `POST /api/behavior`（**behavior 表 schema 已存在**，只需补接口和前端调用）
- 分桶：`userId % 2` → A 组（旧手工加权）/ B 组（DeepFM 精排）
- 指标：CTR = 点击/曝光，对比两组

**产出 → 简历**："哈希分桶 AB 实验方案与行为埋点"的合法来源。

## 四、实施顺序与里程碑

| Phase | 内容 | 工期 | 产出（简历数字回填点） |
|---|---|---|---|
| 0 | 数据导出 | 0.5 天 | 数据规模数字 |
| 1 | 切分 + 评测框架 + 基线跑分 | 1 天 | **真实基线 HR@K/NDCG@K** |
| 2 | DeepFM 训练 + 评测 | 2 天 | **真实 NDCG 提升百分比** |
| 3 | 双塔 + Faiss | 2 天 | 召回侧指标、HR@100 |
| 4 | FastAPI 服务化 + 降级 | 1 天 | 接口 P95 延迟 |
| 5 | LLM 理由 + RAG 找书 | 1.5 天 | 解释覆盖率、Top-5 命中率 |
| 6 | 埋点 + AB + 压测 | 0.5 天 | CTR 对比、部署时间 |

Phase 1 完成后，简历上的"基线"数字就变成真的了；Phase 2 完成后，"NDCG@10 提升"变真。**每完成一个 Phase，回填一句简历。**

## 五、预期指标区间（诚实参考，以实测为准）

| 指标 | 预期区间 | 说明 |
|---|---|---|
| 基线 HR@10 | 12~18% | 200k 评分、2k 书的规模下典型值 |
| DeepFM 后 NDCG@10 相对提升 | 5~15% | side information 是主要增益来源 |
| 语义检索 Top-5 命中率 | 70~85% | 50 条手工查询 |
| 推荐接口 P95 | 100~200ms（缓存命中 <50ms） | 现版可实测 |

## 六、风险与注意事项

1. **防泄漏三红线**：留一法切分；统计特征只用训练集计算；测试集用户只保留评分 ≥ 3 条者
2. **防过拟合**：小数据配小模型（embedding 16~32 维、网络 ≤ 2 层）、dropout、early stopping——大模型在此数据量下指标反而差
3. **冷启动保留**：评分 < 3 条的用户仍走热门/内容通道（现有逻辑不动），新模型只服务有行为历史的用户
4. **公平对比**：所有模型与基线跑同一份测试集、同一候选池口径，对比表才有说服力

## 七、可选扩展（时间富余再做，面试谈资）

- **消融实验**：DeepFM 去掉统计特征 / 去掉 FM 部分的指标对比——面试官最爱的追问素材
- **MCP Server**：把评测/回放能力封装成 MCP 工具，Claude Code 里一句话触发离线评测
- **失败案例分析**：导出 20 条模型判错的 case，分析原因（长尾用户/数据稀疏）——体现分析能力
