# HelpDesk Pro Roadmap

This roadmap keeps the project focused on a reliable internal DRN TECH help desk before adding advanced features.

## Phase 0 — Stabilise the current build

**Goal:** Make the current feature set safe to release as a baseline.

- [ ] Test as a normal user and an admin in separate browser sessions.
- [ ] Test registration, login, logout, settings, and password reset.
- [ ] Test ticket creation, reply, status update, progress update, and notifications.
- [ ] Test Live Chat claiming with two admins, rating, reopening, and deletion.
- [ ] Test user search, editing, deactivation, and deletion.
- [ ] Fix any regression discovered during testing.
- [ ] Commit the verified baseline to Git.

**Done when:** All key flows work without errors and the verified source is committed.

## Phase 1 — Production foundation

**Goal:** Prepare a stable, recoverable EC2 deployment.

- [ ] Provision PostgreSQL and migrate the existing SQLite data.
- [ ] Add Alembic/Flask-Migrate for future schema changes.
- [ ] Configure production environment variables and SMTP.
- [ ] Configure Gunicorn, Nginx, HTTPS, domain DNS, and EC2 security groups.
- [ ] Set up database and uploaded-image backups.
- [ ] Test a backup restore.
- [ ] Add basic log monitoring and uptime monitoring.

**Done when:** The site is HTTPS-only, uses PostgreSQL, survives a restart, sends reset emails, and can be restored from backup.

## Phase 2 — Better ticket operations

**Goal:** Help admins manage work without losing context.

- [ ] Add internal admin-only notes.
- [ ] Add ticket tags.
- [ ] Add due dates and simple SLA indicators.
- [ ] Add ticket status history/audit trail.
- [ ] Add ticket screenshot/file attachments with strict validation.

**Done when:** Admins can coordinate work, track commitments, and review every important ticket change.

## Phase 3 — Reporting and service quality

**Goal:** Turn support activity into useful decisions.

- [ ] Add ticket volume by status, category, and priority.
- [ ] Show unresolved and overdue tickets.
- [ ] Calculate average resolution time.
- [ ] Show Live Chat satisfaction-rating average and rating count.
- [ ] Add date-range filtering and CSV export.

**Done when:** An admin can explain support workload, response quality, and recurring issue types from the dashboard.

## Phase 4 — Notifications and scale

**Goal:** Make updates timely without making the system noisy.

- [ ] Send email notifications for ticket replies, progress updates, and resolutions.
- [ ] Add web push notifications during the EC2 stage.
- [ ] Add pagination for users, tickets, articles, and notifications.
- [ ] Replace frequent chat page refreshes with a more efficient real-time method if usage grows.

**Done when:** Users receive important updates promptly and the app stays responsive as data grows.

## Phase 5 — Final UI polish and project presentation

**Goal:** Make the product consistent, accessible, and ready to demonstrate.

- [ ] Standardise colours, buttons, cards, spacing, empty states, and mobile layouts.
- [ ] Run keyboard and small-screen checks.
- [ ] Prepare screenshots and a short user guide.
- [ ] Prepare proposal/defence notes explaining architecture, security, data model, and trade-offs.

**Done when:** The interface is polished on desktop and mobile, and the project can be confidently demonstrated and defended.

## Deliberately out of scope for now

Do not add AI chatbots, phone support, social-media channels, workforce scheduling, or enterprise CRM integrations before Phase 5. They add cost and complexity without improving the core DRN TECH support workflow enough at this stage.

## Recommended next action

Start **Phase 0** by running a full user/admin regression test. Once that is clean and committed, move directly to the PostgreSQL and EC2 production foundation in Phase 1.
