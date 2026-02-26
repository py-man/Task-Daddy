# Task-Daddy Mobile Spec (V1)

Goal: A phone-first experience that does not reflow the desktop UI.

## Breakpoints

- Mobile: `<= 767px`
- Tablet: `768–1023px` (uses the compact UI)
- Desktop: `>= 1024px` (must remain unchanged)

Implementation approach:
- Desktop shell renders at `lg:` and above.
- Compact shell renders below `lg`.

## Navigation (compact)

Bottom tab bar:
- `/app/boards`
- `/app/tasks` (My Tasks in current board for now; global later)
- `/app/inbox`
- `/app/search`
- `/app/settings`

Header:
- Shows app mark + context title.
- In Board/Tasks/Search contexts: shows a board picker.
- Quick icons: Search, Inbox unread badge.

Quick add:
- Floating “+” button.
- Opens a Quick Add sheet: title, lane, priority, due date.

## Board UX (compact)

Single-lane view (no horizontal swimlanes):
- Lane selector chips (scrollable).
- One lane list visible at a time.
- Task card actions:
  - Tap opens the task sheet (existing task drawer is full-screen on mobile).
  - “Move” opens a lane chooser sheet and moves task to selected lane.

No drag/drop required on compact layouts.

## Task sheet (compact)

Uses the existing task drawer (full-screen overlay on mobile) with:
- Details tab (edit fields, export .ics, reminders)
- Checklist, Comments, Activity
- Jira tab (create/sync) unchanged

## Non-regression constraints

- Jira sync UI/flows unchanged.
- Desktop layout unchanged at `>= 1024px`.
- No hover-only controls required for mobile.
- Background layers remain pointer-events none and respect Reduced Motion.

