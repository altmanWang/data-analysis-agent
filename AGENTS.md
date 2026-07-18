## 语言约束
使用中文进行回答/代码注释以及文档书写

## 环境配置
### 后端
框架使用fastapi==0.115.12
agents框架使用
langgraph>=1.0.5
langchain>=1.2.0
deepagents>=0.6.0
python使用python 3.11

### 前端
前端使用JS+VUE3

### 数据库
MySQL 8, localhost:3306, user:root, password:123456, database:data_analysis_agent

### 环境变量 (.env)
```
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DATABASE=data_analysis_agent
```

## 启动命令
### 后端
```bash
conda activate py311
pip install -r requirements.txt
cd backend && uvicorn main:app --reload --port 8000
```

### 前端
```bash
cd frontend
npm install
npm run dev
```
访问 http://localhost:5173