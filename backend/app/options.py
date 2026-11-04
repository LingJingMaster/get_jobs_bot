"""Small curated Boss option dictionary. Unsupported names fail rather than silently dropping filters."""
from .jobs import parse_list

VALUES = {
    'city': [('全国', '100010000'), ('北京', '101010100'), ('上海', '101020100'), ('广州', '101280100'), ('深圳', '101280600'), ('杭州', '101210100'), ('成都', '101270100'), ('武汉', '101200100'), ('南京', '101190100'), ('苏州', '101190400')],
    'jobType': [('不限', '0'), ('全职', '1901'), ('兼职', '1903'), ('实习', '1902')],
    'experience': [('不限', '0'), ('应届生', '102'), ('1年以内', '103'), ('1-3年', '104'), ('3-5年', '105'), ('5-10年', '106'), ('10年以上', '107')],
    'degree': [('不限', '0'), ('高中', '202'), ('大专', '203'), ('本科', '204'), ('硕士', '205'), ('博士', '206')],
    'salary': [('不限', '0'), ('3K以下', '402'), ('3-5K', '403'), ('5-10K', '404'), ('10-20K', '405'), ('20-50K', '406'), ('50K以上', '407')],
    'scale': [('不限', '0'), ('0-20人', '301'), ('20-99人', '302'), ('100-499人', '303'), ('500-999人', '304'), ('1000-9999人', '305'), ('10000人以上', '306')],
    'stage': [('不限', '0'), ('未融资', '801'), ('天使轮', '802'), ('A轮', '803'), ('B轮', '804'), ('C轮', '805'), ('D轮及以上', '806'), ('已上市', '807'), ('不需要融资', '808')],
    'industry': [('不限', '0')],
}


def options():
    return {kind: [{'id': i + 1, 'type': kind, 'name': name, 'code': code, 'sortOrder': i} for i, (name, code) in enumerate(values)] for kind, values in VALUES.items()}


def codes(kind, raw):
    names = dict(VALUES[kind])
    result = []
    for value in parse_list(raw):
        code = names.get(value, value)
        if not code.isdigit():
            raise ValueError(f'未知筛选项 {kind}: {value}；请选择支持的选项或使用平台数字代码')
        if code != '0':
            result.append(code)
    return ','.join(result)
