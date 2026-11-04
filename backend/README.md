# Python 后端

完整安装、启动和功能边界见根目录 [README](../README.md)。

在根目录执行：

```sh
backend/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 9527
backend/.venv/bin/python -m pytest backend/tests -q
```

默认数据库 `backend/db/getjobs.db`，图片与浏览器缓存位于 `backend/data/`。仅运行一个后端进程；不要直接使用原 Java 数据库。

API 文档：`http://127.0.0.1:9527/docs`。
