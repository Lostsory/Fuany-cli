# Fuany Web

React + TypeScript + Vite + 原生 CSS，连接项目根目录中的 FastAPI 服务。

## 开发

在项目根目录启动后端：

```bash
uv sync
uv run uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

在本目录启动前端：

```bash
npm ci
npm run dev
```

打开 http://127.0.0.1:5173。Vite 将 `/api` 代理到后端，无需配置 CORS。

## 构建与验证

```bash
npm run build
npm run lint
```

构建后在项目根目录运行 `uv run fuany-web`，即可从 http://127.0.0.1:8000 同时访问页面和 API。后端应在构建完成后启动。

## 交互

- Enter 发送消息，Shift + Enter 换行；中文输入法组合输入不会误发送。
- Cmd/Ctrl + K 新建对话。
- 实时显示模型回答和工具调用，Markdown 支持代码、列表、表格。
- 写文件、执行命令等操作通过网页逐次授权，5 分钟未处理自动拒绝。
- 刷新后可从左侧恢复会话；执行期间不能切换或重复提交。
- 会话保存在后端内存中，重启后端后清空。使用单个服务进程。
- 关闭页面会中断后续生成；正在执行的工具仍可能完成，已执行的文件操作不会撤销。

API Key 仅配置在后端 `.env`，不要添加到 Vite 环境变量或前端代码中。
