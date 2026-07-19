# Event Streaming v3 迁移 + 技能加载渲染

**日期**: 2026-07-19  
**状态**: 已确认

## 目标

将后端从 `astream_events(v2)` 迁移到 `stream_events(v3)`，同时在前端对话界面中增加技能加载和子代理执行的可视化渲染。

## 架构

```
stream_events(v3)
  ├─ stream.messages      → message.text (coordinator 文本流)
  ├─ stream.tool_calls    → message.tool_call / message.tool_result
  └─ stream.subagents
       └─ subagent.tool_calls → message.tool_call (sub source)
       └─ subagent.status     → subagent.start / subagent.end
            ↓
       ws_handler.py (skill 嗅探: read_file + /skills/ → skill.loading/loaded)
            ↓
       WebSocket → websocket.js → chatStore.js → ChatPanel.vue
```

## WebSocket 消息协议

每条消息: `{ type, source, payload }`

| type | source | payload | 触发条件 |
|---|---|---|---|
| `message.text` | coordinator / subagent:xxx | `{ content }` | LLM 文本流 |
| `message.tool_call` | coordinator / subagent:xxx | `{ tool, input }` | 工具开始 |
| `message.tool_result` | coordinator / subagent:xxx | `{ tool, output }` | 工具结束 |
| `subagent.start` | system | `{ agent }` | 子代理启动 |
| `subagent.end` | system | `{ agent, status }` | 子代理结束 |
| `skill.loading` | system | `{ skill }` | 检测到 read_file(/skills/) |
| `skill.loaded` | system | `{ skill }` | 技能文件读取完成 |
| `file.tree` | system | `{ tree }` | 文件树更新 |
| `error` | system | `{ message }` | 异常 |

## 文件改动

### 后端

- `backend/ws_handler.py` — `astream_events(v2)` → `stream_events(v3)`，新增 skill 嗅探逻辑

### 前端

- `frontend/src/stores/chatStore.js` — 新增 `subagents`/`skills` 状态，`source` 感知的消息追加
- `frontend/src/utils/websocket.js` — 所有事件类型替换为 v3 协议
- `frontend/src/components/ChatPanel.vue` — 子代理卡片、技能加载条、按 source 分组的渲染

## 前端状态模型

```javascript
messages: [{ role, content, source, subagent?, skill?, ... }]
subagents: { "data-analyst": { status, toolCalls[] } }
skills: [{ name, status: "loading" | "loaded" }]
isStreaming: false
```

## 渲染层级

```
message.skill    → <SkillBar />        // 技能加载提示
message.subagent → <SubagentCard>      // 子代理卡片
  └─ toolCalls   → <ToolCallRow />     // 工具调用行
message.content  → <Markdown />        // 文本内容
```
