"""
Phase 3b: 汇总评测报告

合并 baseline / deepfm / two_tower 三阶段结果，
输出最终对比表 eval_report.md —— 简历数字的唯一合法出处。
"""

import json
import os
import time

HERE = os.environ.get("DL_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))


def load(name):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    base = load("baseline_results.json")
    dm = load("deepfm_results.json")
    tt = load("two_tower_results.json")

    rows = []
    if base:
        rows.append(("Hybrid（现有基线）", base["results"]["Hybrid(现有基线)"], None))
        for name in ("Popularity", "ItemCF", "UserCF", "ContentBased"):
            rows.append((name, base["results"][name], None))
    if dm:
        m = dm["DeepFM精排"]
        rows.append(("DeepFM 精排（同候选池）", m, base["results"]["Hybrid(现有基线)"] if base else None))
    if tt:
        rows.append(("双塔召回（HR@100）", tt["TwoTower召回(HR@100)"], None))
        if "双塔+DeepFM端到端" in tt:
            rows.append(("双塔 + DeepFM 端到端", tt["双塔+DeepFM端到端"],
                         base["results"]["Hybrid(现有基线)"] if base else None))

    keys = []
    for _, m, _ in rows:
        for k in m:
            if k not in keys:
                keys.append(k)

    lines = ["# 推荐系统离线评测报告（汇总）", ""]
    lines.append(f"- 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("- 数据集: Book-Crossing 清洗后 22,808 本书 / 15,044 用户 / 184,738 条评分")
    lines.append("- 切分: 留一法（每用户最后一条评分入测试集），测试用户 14,551")
    lines.append("- 口径: DeepFM 与 Hybrid 使用同一召回候选池（4 路通道 Top-20 并集），隔离排序层差异；")
    lines.append("  端到端 = 候选池并入双塔 Top-100 召回后 DeepFM 精排")
    lines.append("")
    lines.append("| 方法 | " + " | ".join(keys) + " | 相对基线提升 |")
    lines.append("|---|" + "---|" * (len(keys) + 1))

    for name, m, hyb in rows:
        vals = " | ".join(f"{m.get(k, 0):.4f}" for k in keys)
        if hyb and hyb.get("NDCG@10", 0) > 0:
            delta = (m.get("NDCG@10", 0) - hyb["NDCG@10"]) / hyb["NDCG@10"] * 100
            vals += f" | NDCG@10 {delta:+.1f}%"
        else:
            vals += " | -"
        lines.append(f"| {name} | {vals}")

    lines.append("")
    lines.append("## 结论要点（简历可引用）")
    if dm and base:
        hyb = base["results"]["Hybrid(现有基线)"]
        m = dm["DeepFM精排"]
        for k in ("HR@10", "NDCG@10"):
            if hyb.get(k, 0) > 0:
                lines.append(f"- DeepFM 精排（同候选池）: {k} {hyb[k]:.4f} -> {m[k]:.4f}（{(m[k] - hyb[k]) / hyb[k] * 100:+.1f}%）")
    if tt and base:
        hyb = base["results"]["Hybrid(现有基线)"]
        m = tt["双塔+DeepFM端到端"]
        for k in ("HR@10", "NDCG@10"):
            if hyb.get(k, 0) > 0:
                lines.append(f"- 双塔+DeepFM 端到端: {k} {hyb[k]:.4f} -> {m[k]:.4f}（{(m[k] - hyb[k]) / hyb[k] * 100:+.1f}%）")

    rag = load("rag_eval_results.json")
    bench = load("bench_results.json")
    if rag or bench:
        lines.append("")
        lines.append("## RAG 语义检索与模型服务性能")
        if rag:
            lines.append(f"- 语义检索 Top-5 命中率（50 条人工查询）: {rag['overall_top5_hit_rate']:.2%}"
                         f"（分类查询 {rag['cat_hit_rate']:.2%}，书名查询 {rag['title_hit_rate']:.2%}）")
        if bench:
            lines.append(f"- DeepFM 精排 /rank（68 候选）: P95={bench['rank_deepfm']['p95']}ms, "
                         f"吞吐 {bench['rank_deepfm']['qps']} req/s")
            lines.append(f"- 双塔召回 /embed（Top-100）: P95={bench['embed_tower']['p95']}ms, "
                         f"吞吐 {bench['embed_tower']['qps']} req/s")

    report = "\n".join(lines)
    with open(os.path.join(HERE, "eval_report.md"), "w", encoding="utf-8") as f:
        f.write(report)
    print(report)


if __name__ == "__main__":
    main()
