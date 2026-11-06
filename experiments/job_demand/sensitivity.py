"""Near-duplicate sensitivity; no deletion from the source snapshot/database."""
import argparse
import json
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from analysis import analyze, clean_jd


def run(source, out):
    rows = json.loads(source.read_text())
    x = TfidfVectorizer(analyzer='char', ngram_range=(3,5), min_df=1).fit_transform([clean_jd(r['jd']) for r in rows])
    similarities = cosine_similarity(x)
    keep, removed = [], []
    # Fixed threshold, deterministic first-seen representative; not transitive merging.
    for i, row in enumerate(rows):
        similar = [(j, float(similarities[i,j])) for j in keep if similarities[i,j] >= .90]
        if similar:
            j, score = max(similar, key=lambda pair: pair[1])
            removed.append(dict(id=row['id'], kept=rows[j]['id'], cosine=score))
        else:
            keep.append(i)
    out.mkdir(parents=True, exist_ok=True)
    path=out/'snapshot_near_dedup.json'
    path.write_text(json.dumps([rows[i] for i in keep], ensure_ascii=False, indent=2))
    (out/'removed_pairs.json').write_text(json.dumps(removed,ensure_ascii=False,indent=2))
    result=analyze(path,out)
    print('NEAR_DUPLICATES_REMOVED',len(removed))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();run(args.snapshot,args.out)
