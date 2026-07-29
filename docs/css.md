# 对话框消息样式规范

> 风格：AI-Native UI — 参考 DeepSeek 实测参数设计

---

## 一、设计 Token（`design-tokens.css`）

```css
:root {
  /* 主色系 */
  --color-primary: #3964FE;          /* DeepSeek 激活色 */
  --color-primary-hover: #2551E6;
  --color-primary-light: #EDF3FE;
  --color-primary-subtle: #F5F7FF;

  /* 语义色 */
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --color-error: #EF4444;

  /* 表面层级 */
  --color-bg: #FFFFFF;
  --color-bg-card: #FFFFFF;
  --color-bg-muted: #F3F4F6;
  --color-bg-hover: #F0F2F5;
  --color-bg-active: #EDF3FE;

  /* 文字层级 */
  --color-text: #0F1115;
  --color-text-secondary: #61666B;
  --color-text-muted: #81858C;
  --color-text-inverse: #FFFFFF;

  /* 边框 */
  --color-border: rgba(0, 0, 0, 0.10);
  --color-border-light: rgba(0, 0, 0, 0.04);
  --color-border-focus: #3964FE;

  /* 消息气泡 */
  --user-bubble-bg: #EDF3FE;

  /* 排版 */
  --font-family: 'Inter', system-ui, -apple-system, sans-serif;
  --font-size-xs: 12px;    /* 辅助文字 */
  --font-size-sm: 13px;
  --font-size-base: 14px;  /* AI 回复正文 */
  --font-size-md: 16px;    /* 用户消息 */
  --font-size-lg: 18px;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;
  --line-height: 1.6;
  --line-height-relaxed: 1.7;

  /* 间距（8dp 节奏） */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 12px;
  --spacing-lg: 16px;
  --spacing-xl: 20px;
  --spacing-2xl: 24px;

  /* 圆角 */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-bubble: 22px;
  --radius-input: 24px;

  /* 阴影 */
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.06);
  --shadow-input: 0 4px 10px rgba(0,0,0,0.02), 0 2px 4px rgba(0,0,0,0.04);

  /* 布局 */
  --sidebar-width: 261px;
  --topbar-height: 48px;
  --chat-max-width: 768px;

  /* 过渡 */
  --transition-fast: 150ms ease;
}
```

---

## 二、消息行布局

```
┌──────────────────────────────────────────────┐
│ 消息行 (max-width: 768px, margin: 0 auto)    │
│ ┌────┐ ┌──────────────────────────────────┐  │
│ │头像│ │ 思考块 / 消息体 / 工具卡片        │  │
│ │28px│ │ (flex: 1, min-width: 0)         │  │
│ └────┘ └──────────────────────────────────┘  │
│  gap: 12px                                   │
└──────────────────────────────────────────────┘
```

```css
.message-row {
  display: flex;
  gap: var(--spacing-md);           /* 12px */
  padding: var(--spacing-md) var(--spacing-2xl); /* 12px 24px */
  max-width: var(--chat-max-width); /* 768px */
  margin: 0 auto;
}

/* 用户消息右对齐 */
.message-row.user {
  flex-direction: row-reverse;
}
```

---

## 三、用户消息气泡

```css
.message-row.user .text-content {
  background: var(--user-bubble-bg);   /* #EDF3FE 浅蓝 */
  color: var(--color-text);            /* #0F1115 */
  border-radius: var(--radius-bubble); /* 22px */
  padding: 10px 16px;
  font-size: var(--font-size-md);      /* 16px */
  line-height: var(--line-height);     /* 1.6 */
  max-width: calc(100% - 88px);
}

.message-row.user .msg-body {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
```

---

## 四、AI 回复消息

```css
/* 无气泡，直接展示文字 */
.message-row:not(.user) .text-content {
  font-size: var(--font-size-base);          /* 14px */
  line-height: var(--line-height-relaxed);   /* 1.7 */
  color: var(--color-text-secondary);        /* #61666B */
  padding: 0;
}
```

### AI 头像

```css
.msg-avatar {
  width: 28px; height: 28px;
  border-radius: 50%;
  background: var(--color-primary);   /* #3964FE */
  color: var(--color-text-inverse);   /* #FFFFFF */
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
```

---

## 五、Markdown 渲染

### 解析引擎

```javascript
import { marked } from 'marked'
function renderMd(text) {
  return marked.parse(text)
}
```

### 段落 & 标题

```css
.text-content :deep(p)    { margin-bottom: var(--spacing-md); }
.text-content :deep(p:last-child) { margin-bottom: 0; }
.text-content :deep(h1),
.text-content :deep(h2),
.text-content :deep(h3) {
  color: var(--color-text);
  margin-top: var(--spacing-xl);
  margin-bottom: var(--spacing-sm);
  font-weight: var(--font-weight-semibold);
}
```

### 代码块

```css
/* 行内代码 */
.text-content :deep(code) {
  background: var(--color-bg-muted);    /* #F3F4F6 */
  padding: 2px 6px;
  border-radius: var(--radius-sm);      /* 6px */
  font-size: 0.9em;
  color: var(--color-primary);          /* #3964FE */
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
}

/* 多行代码 */
.text-content :deep(pre) {
  background: #1a1a2e;                  /* 深色背景 */
  color: #e2e8f0;
  padding: var(--spacing-lg);           /* 16px */
  border-radius: var(--radius-lg);      /* 12px */
  overflow-x: auto;
  margin: var(--spacing-md) 0;
  font-size: var(--font-size-base);
}
.text-content :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
  font-size: inherit;
}
```

### 表格

```css
.text-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: var(--spacing-md) 0;
  font-size: var(--font-size-base);
}
.text-content :deep(th),
.text-content :deep(td) {
  border: 1px solid var(--color-border);
  padding: var(--spacing-sm) var(--spacing-md);
  text-align: left;
}
.text-content :deep(th) {
  background: var(--color-bg-muted);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-secondary);
}
.text-content :deep(tr:hover td) {
  background: var(--color-bg-muted);
}
```

### 引用块

```css
.text-content :deep(blockquote) {
  border-left: 3px solid var(--color-border);
  padding-left: var(--spacing-md);
  color: var(--color-text-secondary);
  margin: var(--spacing-md) 0;
}
```

### 列表

```css
.text-content :deep(ul),
.text-content :deep(ol) {
  padding-left: var(--spacing-xl);
  margin-bottom: var(--spacing-md);
}
.text-content :deep(li) {
  margin-bottom: var(--spacing-xs);
}
```

### 链接

```css
.text-content :deep(a) {
  color: var(--color-primary);
  text-decoration: none;
}
.text-content :deep(a:hover) {
  text-decoration: underline;
}
```

### 分割线

```css
.text-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-border-light);
  margin: var(--spacing-xl) 0;
}
```

### 图片

```css
.text-content :deep(img) {
  max-width: 100%;
  max-height: 360px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
  margin: var(--spacing-sm) 0;
}
```

---

## 六、思考过程块

```css
.thinking-block {
  margin-bottom: var(--spacing-sm);
  border: 1px solid var(--color-border-light);
  border-left: 3px solid var(--color-primary);  /* 蓝色左边线 */
  border-radius: var(--radius-md);
  background: var(--color-bg);                  /* 白色背景 */
  overflow: hidden;
  cursor: pointer;
}
.thinking-header {
  display: flex; align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-md);
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
}
.thinking-body {
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  white-space: pre-wrap;
  line-height: 1.6;
  border-top: 1px solid var(--color-border-light);
  max-height: 300px;
  overflow-y: auto;
}
```

---

## 七、中断问题消息（ask_user）

```css
.interrupt-msg {
  border-left: 3px solid var(--color-primary);
  background: var(--color-primary-subtle);     /* #F5F7FF 极浅蓝 */
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  padding: var(--spacing-md);
  font-size: var(--font-size-base);             /* 14px */
  line-height: var(--line-height-relaxed);      /* 1.7 */
  color: var(--color-text);
}
```

---

## 八、工具调用卡片

```css
.tool-card {
  margin: 4px auto;
  background: var(--color-bg-card);            /* 白色 */
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-primary); /* 动态色带 */
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  overflow: hidden;
  max-width: var(--chat-max-width);
  transition: all var(--transition-fast);
}
.tool-card:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}
```

---

## 九、错误提示

```css
.error-bar {
  display: flex; align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: #FEF2F2;
  border-left: 3px solid var(--color-error);
  border-radius: var(--radius-md);
  color: var(--color-error);
  font-size: var(--font-size-sm);
  max-width: var(--chat-max-width);
  margin: 0 auto;
}
```

---

## 十、打字指示器

```css
.typing-indicator span {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--color-primary);            /* #3964FE 蓝色 */
  animation: typing 1.4s infinite both;
}
@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}
```

---

## 十一、字数对照表（DeepSeek 实测 vs 本项目）

| 元素 | DeepSeek 实测 | 本项目变量 | 数值 |
|------|-------------|----------|------|
| 用户气泡底色 | `#EDF3FE` | `--user-bubble-bg` | `#EDF3FE` |
| 用户气泡圆角 | `22px` | `--radius-bubble` | `22px` |
| 用户字号 | `16px` | `--font-size-md` | `16px` |
| 用户最大宽度 | `calc(100% - 88px)` | 同 | — |
| AI 回复字号 | `14px` | `--font-size-base` | `14px` |
| AI 回复行高 | `24px` (~1.7) | `--line-height-relaxed` | `1.7` |
| AI 回复颜色 | `#61666B` | `--color-text-secondary` | `#61666B` |
| 消息行最大宽 | `768px` | `--chat-max-width` | `768px` |
| 页面底色 | `#FFFFFF` | `--color-bg` | `#FFFFFF` |
| 输入框圆角 | `24px` | `--radius-input` | `24px` |
| 输入框阴影 | `0 4px 10px … 0 2px 4px …` | `--shadow-input` | 同 |
| 顶栏高度 | `48px` | `--topbar-height` | `48px` |
| Sidebar 宽度 | `261px` | `--sidebar-width` | `261px` |
