import json
import sqlite3
from pathlib import Path
import pytest
from analysis import tags, salary, mentions, sanitize, export_snapshot, tokens

@pytest.mark.parametrize('title,expected', [('AI Agent FDE工程师',['AI','FDE','Agent']), ('AI漫剧生成',['AI']), ('售前工程师',[]), ('人工智能应用',['AI']), ('FDE前线部署\u2062工程师',['FDE'])])
def test_overlapping_title_labels(title, expected):
    assert tags(title) == expected

@pytest.mark.parametrize('raw,expected', [('20-25K·16薪',22.5), ('200-300元/天',None), ('30-40万/年',None), ('面议',None), ('25-20K',None)])
def test_salary_units(raw, expected):
    assert salary(raw) == expected


def test_mentions_do_not_confuse_java_and_javascript():
    assert 'Java' not in mentions('需要 JavaScript，熟悉RAG；Python优先')
    assert {'JavaScript/TypeScript','Python','RAG'} <= set(mentions('需要 JavaScript，熟悉RAG；Python优先'))


def test_snapshot_omits_personal_and_delivery_fields(tmp_path):
    db=tmp_path/'data.db'
    with sqlite3.connect(db) as conn:
        conn.execute('create table boss_jobs(id integer,data text,created_at text)')
        conn.execute('insert into boss_jobs values(1,?,?)',(json.dumps({'jobName':'AI','jobDescription':'联系 test@example.com 13812345678','hrName':'秘密','deliveryStatus':'已投递','jobUrl':'https://www.zhipin.com/job_detail/a.html'}),'2026-11-06'))
    snapshot=export_snapshot(db,tmp_path/'out')
    content=snapshot.read_text()
    assert 'hrName' not in content and 'deliveryStatus' not in content
    assert 'test@example.com' not in content and '13812345678' not in content
    assert json.loads(content)[0]['search_keywords']==[]


def test_technical_token_is_preserved_without_training_labels():
    assert tokens('向量数据库',True)==['向量数据库']
