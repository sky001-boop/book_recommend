"""
模型推理服务（Phase 4b）

职责: 加载训练侧导出的推理资产（ONNX + Faiss + serving_meta.json），
向 Java 后端提供两个接口:
  - POST /rank   : DeepFM 对 (user, book) 候选对打分（精排）
  - POST /embed  : 双塔用户向量 -> Faiss Top-100 召回
设计要点: 算法侧与工程侧解耦 —— Java 只通过 HTTP 调用，服务不可用时后端降级。
"""

import json
import os

import faiss
import numpy as np
import onnxruntime as ort

MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
RECALL_K = 100

# ---------------- 启动时加载 ----------------

with open(os.path.join(MODEL_DIR, "serving_meta.json"), encoding="utf-8") as f:
    META = json.load(f)

ITEM_ORDER = META["item_order"]
ITEM_ORDER_REV = {bid: pos for pos, bid in enumerate(ITEM_ORDER)}

DEEPFM = ort.InferenceSession(os.path.join(MODEL_DIR, "deepfm.onnx"),
                              providers=["CPUExecutionProvider"])
USER_TOWER = ort.InferenceSession(os.path.join(MODEL_DIR, "user_tower.onnx"),
                                  providers=["CPUExecutionProvider"])
FAISS_INDEX = faiss.read_index(os.path.join(MODEL_DIR, "item_emb.faiss"))
print(f"[model-service] 资产加载完成: DeepFM + UserTower + Faiss({FAISS_INDEX.ntotal} 向量)")

# 语义检索（RAG）：bge 文本编码器 + 全量书籍向量
_TEXT_MODEL = None
BOOK_EMB = None
BOOK_EMB_ORDER = None
_emb_path = os.path.join(MODEL_DIR, "book_emb.npy")
_order_path = os.path.join(MODEL_DIR, "book_emb_order.json")
if os.path.exists(_emb_path) and os.path.exists(_order_path):
    from sentence_transformers import SentenceTransformer

    _TEXT_MODEL = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    BOOK_EMB = np.load(_emb_path)
    with open(_order_path, encoding="utf-8") as f:
        BOOK_EMB_ORDER = json.load(f)
    print(f"[model-service] RAG 资产加载完成: bge-small-zh + 书籍向量({BOOK_EMB.shape[0]})")
else:
    print("[model-service] 未找到书籍向量资产，/search_nl 不可用")


def _user_inputs(user_id: int):
    """用户塔输入: user_id [batch]（rank-1）+ [cnt, avg]（z-score）"""
    uidx = META["user_index"].get(str(user_id))
    if uidx is None:
        return None
    cnt, avg = META["user_feats"].get(str(user_id), [0.0, 0.0])
    mean, std = META["tower_u_mean"], META["tower_u_std"]
    num = np.array([[(cnt - mean[0]) / std[0], (avg - mean[1]) / std[1]]], dtype=np.float32)
    return np.array([uidx], dtype=np.int64), num


def _rank_inputs(user_id: int, pairs):
    """DeepFM 输入: sparse[5] + numeric[9]
    数值特征 = [用户评分次数, 用户评分均值, 图书被评次数, 图书被评均值, log流行度,
               cf分, icf分, 内容分, 热度分]（后 4 维策略分由 Java 召回侧传入）"""
    n = len(pairs)
    sparse = np.zeros((n, 5), dtype=np.int64)
    numeric = np.zeros((n, 9), dtype=np.float32)
    uidx = META["user_index"].get(str(user_id), 0)
    u_cnt, u_avg = META["user_feats"].get(str(user_id), [0.0, 0.0])
    mean, std = META["deepfm_mean"], META["deepfm_std"]
    for i, (_, bid, cf, icf, content, pop) in enumerate(pairs):
        bs = META["book_sparse"].get(str(bid), [0, 0, 0, 0])
        sparse[i] = [uidx, bs[0], bs[1], bs[2], bs[3]]
        b_cnt, b_avg, b_logpop = META["book_feats"].get(str(bid), [0.0, 0.0, 0.0])
        raw = [u_cnt, u_avg, b_cnt, b_avg, b_logpop, cf, icf, content, pop]
        numeric[i] = [(raw[j] - mean[j]) / std[j] for j in range(9)]
    return sparse, numeric


# ---------------- FastAPI ----------------

from fastapi import FastAPI, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

app = FastAPI(title="BookRec Model Service")


class RankRequest(BaseModel):
    pairs: list[list[float]]  # [[user_id, book_id, cf分, icf分, 内容分, 热度分], ...]


class EmbedRequest(BaseModel):
    user_id: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/rank")
def rank(req: RankRequest):
    """DeepFM 精排打分，返回与 pairs 对齐的 sigmoid 分数（按单用户批量调用）"""
    if not req.pairs:
        return {"scores": []}
    users = [int(p[0]) for p in req.pairs]
    assert all(u == users[0] for u in users), "rank 接口按单用户批量调用"
    sparse, numeric = _rank_inputs(users[0], req.pairs)
    out = DEEPFM.run(None, {"sparse": sparse, "numeric": numeric})[0]
    scores = (1.0 / (1.0 + np.exp(-out.reshape(-1)))).tolist()
    return {"scores": scores}


@app.post("/embed")
def embed(req: EmbedRequest):
    """双塔召回: user vec -> Faiss Top-100 -> book ids"""
    inputs = _user_inputs(req.user_id)
    if inputs is None:
        raise HTTPException(404, f"user {req.user_id} not in vocab")
    uid, num = inputs
    vec = USER_TOWER.run(None, {"user_id": uid, "user_num": num})[0]
    vec = vec / (np.linalg.norm(vec, axis=1, keepdims=True) + 1e-8)
    _, ids = FAISS_INDEX.search(vec.astype(np.float32), RECALL_K)
    items = [ITEM_ORDER[i] for i in ids[0]]
    return {"items": items, "user_vec": vec[0].tolist()}


class SearchNLRequest(BaseModel):
    query: str


@app.post("/search_nl")
def search_nl(req: SearchNLRequest):
    """RAG 语义找书: 查询向量化 -> 书籍向量余弦 Top-10"""
    if _TEXT_MODEL is None or BOOK_EMB is None:
        raise HTTPException(503, "RAG 资产未加载")
    q_vec = _TEXT_MODEL.encode([req.query], normalize_embeddings=True)[0].astype(np.float32)
    sims = BOOK_EMB @ q_vec
    top_idx = np.argsort(-sims)[:10]
    items = [BOOK_EMB_ORDER[i] for i in top_idx]
    return {"items": items, "scores": [float(sims[i]) for i in top_idx]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
