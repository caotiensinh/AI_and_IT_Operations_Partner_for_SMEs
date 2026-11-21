# UX & Responsive Design Specification

## Interaction philosophy
Flat, quiet, fast, task-oriented, accessible. Avoid decorative dashboards and deep nested menus. Default Japanese; also English and Vietnamese. Every task has visible progress, success/failure and safe undo or confirmation for dangerous actions.

## Shared information architecture
Workspace → Action Inbox → Operations → Assets → Reports → Settings.
Product modules are grouped under Operations, filtered by tenant entitlements and user permissions. Global search must enforce scope.
Tenant selector and current site/role must always be apparent.

## Desktop (>=1200px)
Persistent left navigation, top global search/context, table/detail split pane, batch operations, accessible keyboard shortcuts. Primary operational monitor at 1440×900 and 1920×1080.

## Tablet (768–1199px)
Collapsible navigation, two-column panels where room permits, touch-first lists and full-screen task detail. Field inspections support camera upload and on-device drafts if offline policy permits.

## Mobile (320–767px)
Bottom navigation with 3–5 top actions, one primary action per page, stacked cards, quick acknowledgment, search, photo upload. No hidden desktop-only critical control. Small screens must not require horizontal scrolling.

## Key role journeys
- Operator: open pending alert → inspect context → acknowledge, <=3 main actions after dashboard.
- Manager: see team queue → review evidence → approve/reject with reason.
- Tenant admin: invite user → assign scope/role → confirm.
- Platform operator: review tenant health metadata without seeing customer payloads.

## Design and quality
Use semantic tokens, typography scale, consistent spacing, high-contrast focus, visible permission errors, loading/empty states and accessible tap targets. Confirm dangerous actions. Accessibility target WCAG 2.2 AA.
Test 320, 390, 768, 1024, 1440 and 1920px plus keyboard and screen readers.
