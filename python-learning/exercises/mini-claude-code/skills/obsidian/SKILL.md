---
name: obsidian
description: Use when user asks to search, read, edit, or create notes in their Obsidian vault, or mentions Obsidian, notes, or knowledge base
---

# Obsidian Vault 操作

在用户的 Obsidian Vault 中搜索、读取、编辑和创建笔记。

## Vault 路径

```
/Users/qinzhenxin/Library/Mobile Documents/iCloud~md~obsidian/Documents
```

**重要**：路径含空格，所有命令和工具调用必须用双引号包裹路径。

## Vault 结构

| 文件夹 | 用途 |
|--------|------|
| AI | AI 相关调研笔记 |
| FuEditor | FuEditor 项目笔记与需求文档 |
| Tags | 标签 |
| 工作 | 工作相关笔记 |
| 灵感 | 灵感与创意 |
| 日记 | 日记 |

## 操作指南

### 搜索笔记

**按关键词搜索内容：**
```
Grep pattern="/关键词/" path="/Users/qinzhenxin/Library/Mobile Documents/iCloud~md~obsidian/Documents" glob="*.md"
```

**按文件名搜索：**
```
Glob pattern="**/*关键词*.md" path="/Users/qinzhenxin/Library/Mobile Documents/iCloud~md~obsidian/Documents"
```

**按文件夹筛选：**
```
Glob pattern="*.md" path="/Users/qinzhenxin/Library/Mobile Documents/iCloud~md~obsidian/Documents/文件夹名"
```

**按标签搜索（frontmatter tags）：**
```
Grep pattern="tags:.*标签名" path="/Users/qinzhenxin/Library/Mobile Documents/iCloud~md~obsidian/Documents" glob="*.md"
```

**按内联标签搜索：**
```
Grep pattern="#标签名" path="/Users/qinzhenxin/Library/Mobile Documents/iCloud~md~obsidian/Documents" glob="*.md"
```

### 读取笔记

使用 Read 工具，路径必须是绝对路径且用双引号包裹。

### 编辑笔记

使用 Edit 工具修改已有笔记。先 Read 再 Edit。

### 创建新笔记

使用 Write 工具创建新的 `.md` 文件。根据笔记主题放入对应文件夹。

新笔记模板：
```markdown
---
tags: []
created: YYYY-MM-DD
---

# 标题

内容
```

## 注意事项

- 路径含空格，始终用引号包裹
- 编辑前必须先读取笔记内容
- 创建笔记时根据内容选择合适的文件夹
- 不要删除或移动笔记，除非用户明确要求
- iCloud 同步：文件修改后会自动同步到其他设备
