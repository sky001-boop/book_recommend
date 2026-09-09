# 图书推荐系统 BookRec

基于 **多路召回 + DeepFM 精排** 的完整推荐系统：从数据处理、离线训练、模型服务化到在线实验的全链路实现，并接入大模型提供推荐可解释性与语义检索能力。

- **前端**：http://localhost（Vue 3 + Element Plus）
- **后端**：http://localhost:8080（Spring Boot + MyBatis）
- **模型服务**：http://localhost:8000（FastAPI + ONNX + Faiss）
- **测试账号**：`bx_user_11676` / `bx123456`（`bx_user_` 前缀用户均可登录）

## 系统架构

```
                    ┌────────────────────────────────────────────┐
                    │                  前端 (Vue3)                │
                    │   推荐流 / 自然语言找书 / 评分 / 埋点        │
                    └──────────────────┬─────────────────────────┘
                                       │ /api
                    ┌──────────────────▼─────────────────────────┐
                    │              后端 (Spring Boot)            │
                    │  ┌──────────── 召回层 ────────────┐         │
                    │  │ ItemCF / UserCF / 内容画像 / 热度│         │
                    │  │        + 融合排序(动态权重)      │         │
                    │  └──────────────┬─────────────────┘         │
                    │  ┌──────────────▼─────────────────┐         │
                    │  │      DeepFM 精排 (策略分入模)   │         │
                    │  │   模型不可用 → 降级混合加权      │         │
                    │  └──────────────┬─────────────────┘         │
                    │  ┌──────────────▼─────────────────┐         │
                    │  │  LLM 推荐理由 / RAG 语义找书    │         │
                    │  │  AB 分桶实验 + 行为埋点         │         │
                    │  └────────────────────────────────┘         │
                    └──────┬──────────────┬──────────────┬────────┘
                           │              │              │
                    ┌──────▼─────┐ ┌──────▼─────┐ ┌──────▼──────────┐
                    │   MySQL    │ │   Redis    │ │ 模型服务(FastAPI) │
                    │ 主数据/埋点 │ │ 相似度矩阵 │ │ DeepFM + 双塔     │
                    │            │ │ 缓存/热门榜│ │ + Faiss + bge     │
                    └────────────┘ └────────────┘ └─────────────────┘

离线侧 (Python): 数据导出 → 留一法切分 → 基线复刻 → DeepFM/双塔训练
                 → HR@K/NDCG@K 评测 → ONNX/Embedding 导出
```

## 核心技术

| 模块 | 方案 |
|---|---|
| 多路召回 | ItemCF / UserCF / 内容画像 / 热度 + 双塔语义召回（Faiss 向量检索） |
| 精排 | DeepFM（LR + FM + DNN），**多路召回策略分作为输入特征**，流行度加权负采样 |
| 相似度预计算 | 余弦相似度 + 倒排索引剪枝，离线预计算写入 Redis，每日定时重建 |
| 模型服务化 | PyTorch 训练 → ONNX 导出 → FastAPI 推理，**3 秒超时自动降级**混合加权 |
| LLM 应用 | 个性化推荐理由生成；bge 文本向量化 + RAG 语义找书（含关键词降级） |
| 在线实验 | userId 哈希分桶 AB 实验 + 曝光/点击埋点 + 分组 CTR 统计 |
| 冷启动 | 按用户行为量动态调整召回通道权重，新用户热门兜底 |

## 离线评测结果

**生产数据（Book-Crossing，22,808 本书 / 184,738 评分，留一法 14,551 测试用户）**

| 方法 | HR@10 | NDCG@10 |
|---|---|---|
| Hybrid（多路召回+手工加权基线） | 3.31% | 1.73% |
| **DeepFM 精排（同候选池，只换排序层）** | **3.93%** | **2.13%** |
| 相对提升 | **+18.9%** | **+23.2%** |

**标准基准（MovieLens-1M，1,000,209 评分 / 6,040 测试用户，论文同口径）**

| 方法 | HR@10 | NDCG@10 |
|---|---|---|
| Hybrid 基线 | 3.56% | 1.56% |
| **DeepFM 精排（同候选池）** | **5.75%** | **3.17%** |
| 相对提升 | **+61.4%** | **+103.1%** |

其他实测指标：

- 双塔召回（MovieLens-1M）：HR@100 = 14.95%
- RAG 语义找书：Top-5 命中率 **98%**（50 条人工查询）
- 模型服务压测：精排 P95 **41.9ms**（247 req/s），召回 P95 **36.7ms**（358 req/s）

> 详细口径与完整结果见 [data/dl/eval_report.md](data/dl/eval_report.md)（书数据）与 [data/ml1m/eval_report.md](data/ml1m/eval_report.md)（基准数据）、[docs/项目成果总结.md](docs/项目成果总结.md)。

## 数据集

> ⚠️ **数据集文件未上传至本仓库**，请自行下载后放置到对应目录（下载链接如下）。

### 1. Book-Crossing（生产系统数据）

- **来源**：Book-Crossing Dataset，Cai-Nicolas Ziegler，Universität Freiburg
- **下载**：http://www2.informatik.uni-freiburg.de/~cziegler/BX/
- **原始规模**：278,858 用户 / 271,379 图书 / 约 115 万评分
- **放置位置**：
  - `data/Books.csv`、`data/Ratings.csv`、`data/Users.csv`（原始文件）
- **处理流程**：`data/preprocess.py` 清洗（迭代过滤：用户 ≥3 条且图书 ≥3 条评分）→ 生成 `data/import_data.sql`（22,808 本书 / 184,738 条评分入库文件，MySQL 容器启动时自动导入）；分类标签由 `data/classify_books.py` + `data/cat_fix2.sql` 生成

### 2. MovieLens-1M（离线标准基准数据）

- **来源**：GroupLens Research，University of Minnesota（推荐系统论文标准基准）
- **下载**：https://grouplens.org/datasets/movielens/1m/ （ml-1m.zip，约 6MB）
- **原始规模**：6,040 用户 / 3,706 电影 / 1,000,209 评分
- **放置位置**：`data/ml1m/` 下解压出 `ratings.dat`、`movies.dat`、`users.dat`，重命名为 `.csv` 后运行 `python data/ml1m/export_data.py` 完成适配

## 快速开始

```bash
# 0. 前置：按上文下载 Book-Crossing 数据并运行 data/preprocess.py 生成 import_data.sql

# 1. 启动 Docker Desktop 后，一键构建并启动（首次构建约 20~40 分钟）
docker compose up -d --build

# 2. 浏览器打开 http://localhost，用测试账号登录
#    用户名 bx_user_11676，密码 bx123456

# 3. 可选：配置 LLM API Key 激活推荐理由与 RAG 生成层
#    在项目根目录 .env 中设置 LLM_API_KEY=sk-xxx 后重启后端
```

环境要求：Docker Desktop 4.x，空闲内存 ≥ 4GB（构建期建议 ≥ 6GB）。

## 项目结构

```
backend/           Spring Boot 后端（多路召回 / 精排链路 / LLM / 埋点 / 鉴权）
frontend/          Vue 3 前端（推荐流 / 自然语言找书 / 评分 / 埋点）
model-service/     FastAPI 模型服务（DeepFM ONNX + 双塔 + Faiss + bge）
data/dl/           离线训练与评测管线（切分 / 基线 / DeepFM / 双塔 / RAG 评测 / 压测）
data/ml1m/         MovieLens-1M 标准基准适配与评测
docs/              设计与成果文档
```

## 离线实验复现

```bash
# 书数据（生产口径）
cd data/dl
python export_data.py                     # SQL -> CSV
python split.py                           # 留一法切分
python baseline.py                        # 基线评测
python deepfm.py                          # DeepFM 训练+评测+ONNX
python two_tower.py && python eval_end2end.py   # 双塔+端到端
python eval_report.py                     # 汇总报告

# MovieLens-1M 基准（论文同口径）
cd data/ml1m
python export_data.py
DL_DATA_DIR=$PWD DL_ADJUSTED=1 DL_COMMON_ITEM=5 DL_COMMON_USER=5 DL_NORM_CF=1 python ../dl/split.py
# ... 同上的 baseline/deepfm/two_tower/eval_end2end/eval_report
```

## 主要接口

| 接口 | 说明 |
|---|---|
| `GET /recommend/my` | 混合加权推荐（现有基线） |
| `GET /recommend/v2` | 双塔召回 + DeepFM 精排（模型服务不可用时自动降级） |
| `GET /recommend/ab` | AB 分桶推荐（userId % 2，返回 group/strategy） |
| `GET /recommend/v2/explain` | 推荐 + LLM 个性化推荐理由 |
| `GET /search/nl?q=` | 自然语言找书（RAG 语义检索 + LLM 回答） |
| `POST /behavior/report` | 行为埋点（exposure/click/rating） |
| `GET /behavior/ab-stats` | AB 分组 CTR 统计 |


