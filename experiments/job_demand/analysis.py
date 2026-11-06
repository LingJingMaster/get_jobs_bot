"""Offline, read-only JD analysis agent. No model API, browser or sending access."""
import argparse
import csv
import hashlib
import json
import re
import sqlite3
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import jieba
import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import adjusted_rand_score, silhouette_score

SEEDS = [7, 17, 27, 37, 47]
SKILLS = {
    'Python': r'(?<![a-z])python(?![a-z])', 'SQL': r'(?<![a-z])(?:sql|mysql|postgresql)(?![a-z])',
    'Java': r'(?<![a-z])java(?![a-z])', 'JavaScript/TypeScript': r'javascript|typescript|node\.?js',
    'RAG': r'(?<![a-z])rag(?![a-z])|检索增强', 'Agent': r'(?<![a-z])agents?(?![a-z])|智能体',
    'LLM': r'(?<![a-z])llms?(?![a-z])|大(?:语言)?模型', 'Prompt': r'prompt|提示词',
    'LangChain': r'langchain', 'Dify': r'dify', 'Docker/K8s': r'docker|kubernetes|(?<![a-z])k8s(?![a-z])',
    '模型微调': r'微调|fine[ -]?tun|(?<![a-z])lora(?![a-z])',
    '评测/测试': r'评测|评估|测试', '客户沟通': r'客户.{0,8}(?:沟通|需求|对接)|(?:沟通|对接).{0,8}客户',
    '部署/交付': r'部署|交付', '业务理解': r'业务场景|业务需求|业务理解|需求分析',
}
STOP = set('的 了 和 与 及 或 等 在 对 将 为 中 上 下 有 能 相关 进行 负责 参与 能够 具备 熟悉 掌握 优先 良好 工作 能力 要求 职位 岗位 职责 任职 以上 包括 以及 使用 我们 你 需要 具有 公司 团队 经验'.split())
TERMS = ['大模型', '智能体', '知识库', '向量数据库', '机器学习', '深度学习', '自然语言处理', '前沿部署', '客户需求', '业务场景', '数据分析', '需求分析', '模型评测', '提示词', '微调', '部署', '交付', '低代码', '多模态']


def normalize(value):
    value = unicodedata.normalize('NFKC', value or '')
    return re.sub(r'[\u200b-\u200f\u2060-\u206f\ufeff]', '', value)


def sanitize(value):
    value = normalize(value)
    value = re.sub(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', '[邮箱已脱敏]', value)
    value = re.sub(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)', '[电话已脱敏]', value)
    return re.sub(r'https?://\S+', '[链接已脱敏]', value)


def tags(title):
    return [name for name, pattern in [('AI', r'(?<![a-z])ai(?![a-z])|aigc|人工智能'), ('FDE', r'(?<![a-z])fde(?![a-z])|forward deployed'), ('Agent', r'(?<![a-z])agents?(?![a-z])|智能体')] if re.search(pattern, normalize(title), re.I)]


def salary(value):
    value = normalize(value).lower()
    if any(token in value for token in ['/天', '/时', '/年', '元/天', '万/年']):
        return None
    match = re.search(r'(\d+(?:\.\d+)?)\s*[-–~]\s*(\d+(?:\.\d+)?)\s*k', value)
    if not match:
        return None
    low, high = map(float, match.groups())
    return (low + high) / 2 if 0 < low <= high else None


def export_snapshot(db_path, target):
    # SQLite backup provides a consistent snapshot even while collection runs.
    with sqlite3.connect(f'file:{db_path.resolve()}?mode=ro', uri=True) as source:
        memory = sqlite3.connect(':memory:')
        source.backup(memory)
    records, source_map = [], []
    for pk, data, created in memory.execute('SELECT id,data,created_at FROM boss_jobs ORDER BY id'):
        job = json.loads(data)
        doc_id = f'J{pk:04d}'
        records.append(dict(id=doc_id, title=sanitize(job.get('jobName')), jd=sanitize(job.get('jobDescription')), salary=job.get('salary', ''), location=job.get('location', ''), created_at=created, search_keywords=job.get('searchKeywords', [])))
        source_map.append(dict(id=doc_id, url=job.get('jobUrl'), company=job.get('companyName')))
    target.mkdir(parents=True, exist_ok=True)
    (target/'snapshot.json').write_text(json.dumps(records, ensure_ascii=False, indent=2))
    (target/'source_map_PRIVATE.json').write_text(json.dumps(source_map, ensure_ascii=False, indent=2))
    (target/'source_map_PRIVATE.json').chmod(0o600)
    (target/'snapshot_meta.json').write_text(json.dumps(dict(exported_at=datetime.now(timezone.utc).isoformat(), rows=len(records), sha256=hashlib.sha256((target/'snapshot.json').read_bytes()).hexdigest(), historical_search_provenance='not recorded; title labels are not search-source labels'), ensure_ascii=False, indent=2))
    return target/'snapshot.json'


def tokens(text, enhanced=False):
    # Separate ASCII tokens before Chinese segmentation; keep RAG/LLM names intact.
    out = []
    tokenizer = enhanced_tokenizer if enhanced else plain_tokenizer
    for part in re.findall(r'[a-z][a-z0-9+#.\-]*|[\u4e00-\u9fff]+', normalize(text).lower()):
        for term in tokenizer.cut(part, HMM=False):
            if len(term) >= 2 and term not in STOP:
                out.append(term)
    return out


plain_tokenizer = jieba.Tokenizer()
enhanced_tokenizer = jieba.Tokenizer()
for term in TERMS:
    enhanced_tokenizer.add_word(term, freq=100000)


def clean_jd(text):
    # Conservative line-level removal: do not remove qualification or duty lines.
    return '\n'.join(line for line in normalize(text).splitlines() if not re.match(r'^\s*(?:BOSS安全提示|BOSS 安全提示|举报|微信扫码|工商信息|公司地址|福利待遇[:：]|薪酬福利[:：])', line))


def mentions(text):
    return [name for name, pattern in SKILLS.items() if re.search(pattern, normalize(text), re.I)]


def analyze(snapshot, out):
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    raw = json.loads(snapshot.read_text())
    records, duplicates, excluded, seen = [], [], [], {}
    for r in raw:
        jd = clean_jd(r['jd'])
        if len(re.sub(r'\s+', '', jd)) < 50:
            excluded.append(r['id']); continue
        digest = hashlib.sha256(re.sub(r'\s+', '', jd).encode()).hexdigest()
        if digest in seen:
            duplicates.append({'id': r['id'], 'kept': seen[digest]}); continue
        seen[digest] = r['id']
        records.append({**r, 'clean_jd': jd, 'title_tags': tags(r['title']), 'mentions': mentions(jd), 'monthly_mid_k': salary(r['salary'])})
    if len(records) < 12:
        raise ValueError('至少需要12条有效、非重复JD；不生成不可靠聚类')
    docs = [r['clean_jd'] for r in records]  # title excluded to avoid reproducing title tags
    models, trials, vectors = {}, [], {}
    for name, enhanced in [('分词基线', False), ('领域词表', True)]:
        vectorizer = TfidfVectorizer(tokenizer=lambda s, e=enhanced: tokens(s, e), token_pattern=None, lowercase=False, min_df=2, max_df=0.90, sublinear_tf=True, norm='l2')
        x = vectorizer.fit_transform(docs)
        vectors[name] = (vectorizer, x)
        for k in range(2, min(9, len(records))):
            labels, scores, sizes, run_seconds = [], [], [], []
            for seed in SEEDS:
                tick = time.perf_counter()
                model = KMeans(n_clusters=k, random_state=seed, n_init=20, max_iter=300)
                label = model.fit_predict(x)
                score = silhouette_score(x, label, metric='cosine')
                labels.append(label); scores.append(float(score)); sizes.append(int(np.bincount(label).min())); run_seconds.append(time.perf_counter()-tick)
                models[(name, k, seed)] = model
            stability = [adjusted_rand_score(labels[i], labels[j]) for i in range(len(SEEDS)) for j in range(i+1, len(SEEDS))]
            trials.append(dict(method=name, k=k, silhouette_mean=float(np.mean(scores)), silhouette_std=float(np.std(scores)), ari_mean=float(np.mean(stability)), min_cluster_size=min(sizes), seconds=float(sum(run_seconds)), seeds=SEEDS, silhouettes=scores))
    # Predeclared: select maximal mean silhouette among configurations with >=3 per cluster in every seed.
    eligible = [t for t in trials if t['min_cluster_size'] >= 3]
    if not eligible: raise ValueError('聚类均含小于3条的小簇，需补数据或调整范围')
    best = max(eligible, key=lambda t: t['silhouette_mean'])
    vectorizer, x = vectors[best['method']]
    model = models[(best['method'], best['k'], SEEDS[0])]
    feature_names = vectorizer.get_feature_names_out()
    clusters = []
    for c in range(best['k']):
        idx = np.flatnonzero(model.labels_ == c)
        distance = model.transform(x[idx])[:, c]
        representatives = [records[int(idx[i])]['id'] for i in np.argsort(distance)[:3]]
        keywords = feature_names[np.argsort(model.cluster_centers_[c])[-12:][::-1]].tolist()
        clusters.append(dict(cluster=c, n=len(idx), keywords=keywords, representatives=representatives, title_tags=dict(Counter(tag for i in idx for tag in records[int(i)]['title_tags']))))
    for r, label in zip(records, model.labels_): r['cluster'] = int(label)
    groups = {}
    for group in ['全部', 'AI', 'FDE', 'Agent', 'AI_only']:
        subset = [r for r in records if group == '全部' or (group == 'AI_only' and r['title_tags'] == ['AI']) or group in r['title_tags']]
        values = [r['monthly_mid_k'] for r in subset if r['monthly_mid_k'] is not None]
        degree = Counter('博士' if re.search('博士', r['jd']) else '硕士/研究生' if re.search('硕士|研究生', r['jd']) else '本科' if '本科' in r['jd'] else '大专/专科' if re.search('大专|专科', r['jd']) else '未标注' for r in subset)
        # These are explicit text mentions, not minimum eligibility inferred from missing metadata.
        groups[group] = dict(n=len(subset), skills=dict(Counter(s for r in subset for s in r['mentions'])), monthly_n=len(values), median_mid_k=float(np.median(values)) if values else None, degree_mentions=dict(degree), entry_mentions=sum(bool(re.search('实习|应届|校招|在校', r['title']+'\n'+r['jd'])) for r in subset))
    # Technical token retention is a controlled probe, not a human-labeled job benchmark.
    probe = {name: {term: term in tokens(term, name=='领域词表') for term in TERMS} for name in vectors}
    report = dict(snapshot_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(), raw_n=len(raw), n=len(records), duplicates=duplicates, excluded_short=excluded, first_created=min(r['created_at'] for r in raw), last_created=max(r['created_at'] for r in raw), locations=dict(Counter(r['location'] or '未标注' for r in records)), title_combinations=dict(Counter('+'.join(r['title_tags']) or '无标签' for r in records)), groups=groups, trials=trials, selected=best, clusters=clusters, token_probe=probe, elapsed_seconds=time.perf_counter()-started, warnings=['标题标签不等于搜索来源；组别重叠', '学历/技能仅为正文提及，非最低要求或强制要求', '无独立人工真值，轮廓系数不是准确率', '样本是单平台便利样本，不能推断整体就业市场'])
    (out/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (out/'assignments.json').write_text(json.dumps(records, ensure_ascii=False, indent=2))
    with (out/'trials.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[k for k in trials[0] if k not in ['seeds', 'silhouettes']]); writer.writeheader()
        writer.writerows({k:v for k,v in t.items() if k in writer.fieldnames} for t in trials)
    figures(report, records, out)
    html = '<!doctype html><meta charset="utf-8"><title>岗位需求分析结果</title><style>body{max-width:1100px;margin:40px auto;font:16px/1.7 sans-serif}img{width:100%}pre{white-space:pre-wrap}</style><h1>AI / FDE / Agent 岗位需求分析</h1>'
    html += f'<p>快照 {report["snapshot_sha256"][:12]}；原始 {len(raw)} 条，有效去重后 {len(records)} 条。</p>'
    html += f'<p>已执行：2种表示 × 7种簇数量 × 5个随机种子 = 70次拟合。选择 {best["method"]} / k={best["k"]}；平均余弦轮廓系数 {best["silhouette_mean"]:.4f}，ARI {best["ari_mean"]:.4f}。</p>'
    for warning in report['warnings']: html += '<p>'+warning+'</p>'
    for file in ['skills.png', 'clusters.png', 'comparison.png']: html += f'<img src="{file}">'
    html += '<h2>聚类与证据ID</h2><pre>'+json.dumps(clusters, ensure_ascii=False, indent=2)+'</pre>'
    (out/'index.html').write_text(html)
    print(json.dumps({k:report[k] for k in ['raw_n','n','selected','elapsed_seconds']}, ensure_ascii=False, indent=2))
    return report


def figures(result, records, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font_path = Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
    if font_path.exists():
        from matplotlib import font_manager
        font_manager.fontManager.addfont(str(font_path)); plt.rcParams['font.family'] = FontProperties(fname=str(font_path)).get_name()
    plt.rcParams['axes.unicode_minus'] = False
    skills = list(SKILLS)
    fig, ax = plt.subplots(figsize=(11,6))
    groups = ['AI','FDE','Agent']
    mat=np.array([[result['groups'][g]['skills'].get(s,0)/max(1,result['groups'][g]['n'])*100 for s in skills] for g in groups])
    im=ax.imshow(mat, cmap='YlGnBu',vmin=0,vmax=100,aspect='auto')
    ax.set_xticks(range(len(skills)), skills, rotation=50,ha='right'); ax.set_yticks(range(3),[f'{g} (n={result["groups"][g]["n"]})' for g in groups])
    for y in range(3):
        for z in range(len(skills)): ax.text(z,y,f'{mat[y,z]:.0f}',ha='center',va='center',color='white' if mat[y,z]>65 else 'black',fontsize=9)
    ax.set_title('标题标签组的 JD 技能/职责提及率（%，组间重叠）'); fig.colorbar(im,ax=ax); fig.tight_layout(); fig.savefig(out/'skills.png',dpi=180); plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(10,4))
    for name in ['分词基线','领域词表']:
        ts=[t for t in result['trials'] if t['method']==name]
        axs[0].errorbar([t['k'] for t in ts],[t['silhouette_mean'] for t in ts],yerr=[t['silhouette_std'] for t in ts],marker='o',label=name)
        axs[1].plot([t['k'] for t in ts],[t['ari_mean'] for t in ts],marker='o',label=name)
    axs[0].set_title('余弦轮廓系数（5随机种子）'); axs[1].set_title('随机种子间 ARI 稳定性')
    for ax in axs: ax.set_xlabel('簇数量 k'); ax.legend(); ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/'comparison.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4))
    cs=result['clusters']; ax.bar([f'C{c["cluster"]}\n'+ '/'.join(c['keywords'][:3]) for c in cs],[c['n'] for c in cs],color='#176b73')
    for i,c in enumerate(cs):ax.text(i,c['n']+.5,str(c['n']),ha='center')
    ax.set_ylabel('岗位数');ax.set_title('数据驱动聚类规模（名称待结合代表性 JD 解释）');fig.tight_layout();fig.savefig(out/'clusters.png',dpi=180);plt.close(fig)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',type=Path);parser.add_argument('--snapshot',type=Path);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    snapshot=args.snapshot or export_snapshot(args.db,args.out/'input')
    analyze(snapshot,args.out)
