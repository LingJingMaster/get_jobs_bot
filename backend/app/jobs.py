"""Boss job persistence, filtering and analysis shared by API and worker."""
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone


def parse_list(raw: str) -> list[str]:
    try:
        values = json.loads(raw)
        if isinstance(values, list):
            return [str(v).strip() for v in values if str(v).strip()]
    except (ValueError, TypeError):
        pass
    return [s.strip().strip('\"\'') for s in re.split('[,，]', (raw or '').strip('[]')) if s.strip()]


def salary_range(raw: str):
    # Monthly K only. Daily/hourly/yearly and undecodable salaries must not be treated as monthly.
    match = re.search(r'(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*[kK]', raw or '')
    if not match or any(x in raw for x in ('/天', '/时', '/年', '每天', '每年')):
        return None
    return float(match[1]), float(match[2])


def filter_reason(job: dict, config: dict, blacklist: list[dict]) -> str | None:
    fields = {'company': 'companyName', 'job': 'jobName', 'recruiter': 'hrName'}
    for entry in blacklist:
        value = entry.get('value', '').strip()
        field = fields.get(entry.get('type'))
        text = str(job.get(field, '')) if field else ''
        if field == 'hrName':
            text += str(job.get('hrPosition', ''))
        if value and value.casefold() in text.casefold():
            return '黑名单：' + value
    if config.get('filterDeadHr') and job.get('hrActiveStatus') in parse_list(config.get('deadStatus', '')):
        return 'HR 活跃度不符'
    low, high = config.get('expectedSalaryMin'), config.get('expectedSalaryMax')
    salary = salary_range(job.get('salary', ''))
    if (low or high) and salary is None:
        return '无法确认月薪范围'
    if salary and ((low and salary[1] < low) or (high and salary[0] > high)):
        return '薪资范围不符'
    return None


def initialize(db: sqlite3.Connection):
    db.execute('''CREATE TABLE IF NOT EXISTS boss_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, job_url TEXT UNIQUE NOT NULL,
        data TEXT NOT NULL, created_at TEXT NOT NULL)''')


def save_job(db: sqlite3.Connection, job: dict) -> int:
    initialize(db)
    url = job.get('jobUrl', '')
    if not url.startswith('https://www.zhipin.com/job_detail/'):
        raise ValueError('无效的 Boss 职位链接')
    data = dict(job)
    previous = db.execute('SELECT data FROM boss_jobs WHERE job_url=?', (url,)).fetchone()
    if previous and data.get('deliveryStatus') in {'未投递', '已过滤'}:
        old = json.loads(previous[0])
        if old.get('deliveryStatus') in {'已投递', '发送待确认', '投递失败'}:
            for key in ('deliveryStatus', 'deliveryNote', 'resumeStatus'):
                if key in old:
                    data[key] = old[key]
    data.pop('id', None)
    data.setdefault('deliveryStatus', '未投递')
    now = datetime.now(timezone.utc).isoformat()
    db.execute('INSERT INTO boss_jobs(job_url,data,created_at) VALUES (?,?,?) ON CONFLICT(job_url) DO UPDATE SET data=excluded.data',
               (url, json.dumps(data, ensure_ascii=False), now))
    db.commit()
    return db.execute('SELECT id FROM boss_jobs WHERE job_url=?', (url,)).fetchone()[0]


def selected_jobs(db: sqlite3.Connection, filters: dict) -> list[dict]:
    initialize(db)
    result = []
    statuses = parse_list(filters.get('statuses', ''))
    for row in db.execute('SELECT id,data,created_at FROM boss_jobs ORDER BY id DESC'):
        job = {**json.loads(row[1]), 'id': row[0], 'createdAt': row[2]}
        if statuses and job.get('deliveryStatus') not in statuses:
            continue
        if any(filters.get(key) and filters[key] not in str(job.get(key, '')) for key in ('location', 'experience', 'degree')):
            continue
        if filters.get('keyword') and filters['keyword'].casefold() not in ' '.join(str(job.get(k, '')) for k in ('companyName', 'jobName', 'jobDescription')).casefold():
            continue
        if filters.get('filterHeadhunter') == 'true' and '猎头' in str(job.get('hrPosition', '')):
            continue
        salary = salary_range(job.get('salary', ''))
        low, high = filters.get('minK'), filters.get('maxK')
        if (low or high) and (not salary or (low and salary[1] < float(low)) or (high and salary[0] > float(high))):
            continue
        result.append(job)
    return result


def statistics(items: list[dict]) -> dict:
    def counts(field):
        return [{'name': name, 'value': count} for name, count in Counter(str(i.get(field) or '未知') for i in items).most_common()]
    status = Counter(i.get('deliveryStatus') for i in items)
    salaries = [sum(r) / 2 for i in items if (r := salary_range(i.get('salary', '')))]
    charts = {name: counts(field) for name, field in {
        'byStatus': 'deliveryStatus', 'byCity': 'location', 'byIndustry': 'industry', 'byCompany': 'companyName',
        'byExperience': 'experience', 'byDegree': 'degree', 'hrActivity': 'hrActiveStatus'}.items()}
    charts['dailyTrend'] = [{'name': day, 'value': count} for day, count in sorted(Counter(i['createdAt'][:10] for i in items).items())]
    charts['salaryBuckets'] = [{'bucket': label, 'value': sum(low <= s < high for s in salaries)} for label, low, high in
                              [('0-10K', 0, 10), ('10-20K', 10, 20), ('20-30K', 20, 30), ('30-50K', 30, 50), ('50K+', 50, float('inf'))]]
    return {'kpi': {'total': len(items), 'delivered': status['已投递'], 'pending': status['未投递'],
                    'filtered': status['已过滤'], 'failed': status['投递失败'],
                    'avgMonthlyK': sum(salaries) / len(salaries) if salaries else None}, 'charts': charts}
