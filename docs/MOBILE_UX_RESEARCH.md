# Task-Daddy Mobile UX Research (<= 767px)

Date: 2026-02-23

## What works in top mobile task tools (patterns)

### 1) Bottom navigation (thumb-first)
- Five primary destinations works well on phones: Boards/Projects, My Tasks, Inbox, Search, Settings.
- Keep actions near the bottom (FAB) so creating work is effortless.
- Notion’s mobile app uses a persistent bottom navigation (home/search/inbox/create), which reinforces the pattern for Task-Daddy: “primary destinations are always one tap away”.

### 2) Quick capture and shortcuts
- Best-in-class mobile apps prioritize “capture now, refine later”.
- Asana highlights “Quick Actions” to create tasks and jump to Inbox/Search quickly.
- Trello exposes “quick add” affordances (including iOS widgets) to create cards fast, emphasizing capture without navigating deep into the app.

### 3) Boards on mobile: avoid multi-column horizontal swimlanes
What not to do:
- Tiny multi-column kanban on phones: hard to read, hard to drag, lots of horizontal scrolling.
- Hover-only UI (tooltips, menus) doesn’t translate to touch.
- Touch/drag can fight scroll (historically a common issue on Jira-style boards), so we should avoid making “drag” the only move mechanism.

What to do:
- “Single-lane-at-a-time” with a lane selector (chips/segmented control).
- Optional “accordion” to view all lanes stacked vertically.
- Task move via explicit action (move sheet) instead of cross-column drag.
- Also provide a non-drag “Move…” action from task details or card quick actions (Trello supports “Move” from the card menu).

Evidence:
- Jira mobile continues evolving board UX (e.g., board keyword search, column scroll bars), but mobile drag can be constrained by workflow rules or policies; relying on drag-only interactions is risky.

### 4) Search and filters must be always-accessible
- Search is a core mobile behavior: quick keyword search and filter chips (Overdue, Blocked, Mine, High Priority).

### 5) Full-screen task detail sheet
- A full-screen sheet (not a side drawer) avoids cramped layouts.
- Keep comment input pinned at bottom to work well with the on-screen keyboard.

## What NOT to do (mobile anti-patterns)
- Horizontal kanban columns on a phone.
- Drag-and-drop as the only way to move tasks.
- Dense top bars with multiple dropdowns.
- Forms that require precision taps (small targets).

## Proposed Task-Daddy Mobile IA (information architecture)

Bottom tabs (<= 767px):
1) Boards
2) Tasks (My Tasks)
3) Inbox
4) Search
5) Settings (admin items shown only for admins)

Global:
- Floating “+” quick add task button.
- Board picker available from Board/Tasks/Search contexts.
