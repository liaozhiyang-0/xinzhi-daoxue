# M5：React Workspace Feature Migration

## 目标
把旧 workspace 的展示和交互逐步迁移成组件/feature。

## 顺序
### 1. 纯展示
Message / Markdown / Math / Citation / Source / Artifact / TaskStatus / Error。

### 2. Session
session list、create/select、continuity、course/context display。

### 3. Composer
text input、submit、attachment preview/upload、cancel。

## 组件健康
- component > 400-500 行 → review
- hook > 300 行 → review
- feature module > 1000-1200 行 → review
生成文件除外。

## 状态原则
React state 为 UI 状态 owner，不再依靠 DOM class / dataset 作为核心状态。

## UI
Phase M 只迁架构，不同时做大规模视觉重设计。尽量复用现有 CSS/布局。

本阶段不 commit。
