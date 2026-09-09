"""DeepFM 训练问题诊断：标签分布 / 特征统计 / 输出检查"""
import os
import random
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from baseline import load_books, load_train  # noqa: E402
from deepfm import (build_samples, build_stat_features, build_vocabs,  # noqa: E402
                    normalize_numeric, DeepFM, _auc)

torch.manual_seed(42)
random.seed(42)

train = load_train()
books = load_books()
vocabs, _, book_ids = build_vocabs(train, books)
num_feats, b_pop = build_stat_features(train, books)
samples = build_samples(train, books, vocabs, book_ids, num_feats, b_pop)

labels = [s[2] for s in samples]
print(f"样本数 {len(samples)}, 正样本 {sum(labels):,}, 负样本 {len(labels) - sum(labels):,}")
print(f"正样本比例 {sum(labels) / len(labels):.3f}")

# 数值特征分布
arr = np.array([s[1] for s in samples], dtype=np.float32)
print("数值特征 mean:", arr.mean(0).round(2), "std:", arr.std(0).round(2))
pos_arr = arr[np.array(labels) == 1]
neg_arr = arr[np.array(labels) == 0]
print("正样本特征 mean:", pos_arr.mean(0).round(2))
print("负样本特征 mean:", neg_arr.mean(0).round(2))

# 稀疏索引范围检查
sp = np.array([s[0] for s in samples])
for i, name in enumerate(("user", "book", "category", "author", "publisher")):
    print(f"列{i}({name}): min={sp[:, i].min()}, max={sp[:, i].max()}, vocab={len(vocabs[name])}")

# 训练 6 个 epoch 无 early stop，观察 train/val AUC
sparse_norm, mean, std = normalize_numeric(samples)
sparse = torch.tensor([s[0] for s in samples], dtype=torch.long)
numeric = torch.tensor(sparse_norm, dtype=torch.float32)
labels_t = torch.tensor(labels, dtype=torch.float32)

n_val = int(len(samples) * 0.05)
tr_sp, tr_num, tr_y = sparse[n_val:], numeric[n_val:], labels_t[n_val:]
va_sp, va_num, va_y = sparse[:n_val], numeric[:n_val], labels_t[:n_val]

model = DeepFM([len(vocabs[k]) for k in ("user", "book", "category", "author", "publisher")], 5)
opt = torch.optim.Adam(model.parameters(), lr=1e-3)
loss_fn = torch.nn.BCEWithLogitsLoss()

for epoch in range(6):
    model.train()
    perm = torch.randperm(len(tr_sp))
    for i in range(0, len(perm), 4096):
        idx = perm[i:i + 4096]
        opt.zero_grad()
        loss = loss_fn(model(tr_sp[idx], tr_num[idx]), tr_y[idx])
        loss.backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        tr_out = model(tr_sp, tr_num).sigmoid().numpy()
        va_out = model(va_sp, va_num).sigmoid().numpy()
        # 抽查 5 个样本的预测
        probe = va_out[:5]
        print(f"epoch {epoch + 1}: train_auc={_auc(tr_y.numpy(), tr_out):.4f} "
              f"val_auc={_auc(va_y.numpy(), va_out):.4f}")
        print(f"  抽查预测 {probe.round(3)} 标签 {va_y[:5].tolist()}")
