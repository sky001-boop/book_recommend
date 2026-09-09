FROM python:3.12-slim

WORKDIR /app

# 国内网络使用镜像源下载模型权重
ENV HF_ENDPOINT=https://hf-mirror.com \
    SENTENCE_TRANSFORMERS_HOME=/app/models

COPY requirements.txt .
# 先装 CPU 版 torch（体积 ~200MB vs CUDA 版 ~2.5GB），sentence-transformers 检测到已装不会重复拉 CUDA 版
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY serving_meta.json .
COPY deepfm.onnx .
COPY deepfm.onnx.data .
COPY user_tower.onnx .
COPY user_tower.onnx.data .
COPY item_emb.faiss .
COPY book_emb.npy .
COPY book_emb_order.json .

# 构建期预下载 bge-small-zh 权重（镜像内离线可用）
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

EXPOSE 8000
CMD ["python", "main.py"]
