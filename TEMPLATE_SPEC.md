# SPEC.md

> For technical implementation details, architecture, and developer documentation, see [AGENTS.md](./AGENTS.md).

---

## Table of Contents

- [Overview](#overview)
- [Users & Roles](#users--roles)
- [Business Rules](#business-rules)
- [Features](#features)
- [User Flows](#user-flows)
  - [Flow 1: New User Onboarding](#flow-1-new-user-onboarding)
  - [Flow 2: Creating a Project](#flow-2-creating-a-project)
- [Out of Scope](#out-of-scope)
- [Open Questions](#open-questions)

---

## Overview

<!--
Provide a high-level description of the product or feature:
- What is this product/feature?
- What problem does it solve for users?
- What is the core value proposition?
- Who is the target audience?
- What are the primary goals and objectives?
- How does this fit into the broader product strategy?
- What are the key success metrics or KPIs?

Keep this section concise but comprehensive - it should give anyone reading this document a clear understanding of what's being built and why.
-->

---

## Users & Roles

<!--
Define the different types of users and their roles in the system:

For each user type, document:
- Role name and description
- Key characteristics or personas
- Primary goals and motivations
- Pain points this product addresses
- Permissions and access levels
- Typical use cases

Example format:

### Admin User
- Full system access and management capabilities
- Responsible for: user management, system configuration, monitoring
- Can: create/edit/delete users, configure settings, view all data, generate reports
- Cannot: [any restrictions]
- Typical persona: IT manager, system administrator

### End User
- Standard application user
- Responsible for: daily task completion, data entry
- Can: view own data, create items, edit own content
- Cannot: access admin features, view other users' private data
- Typical persona: [description]

Include permission matrices if helpful:
| Action | Admin | Manager | User | Guest |
|--------|-------|---------|------|-------|
| View dashboard | ✓ | ✓ | ✓ | ✗ |
| Create items | ✓ | ✓ | ✓ | ✗ |
| Delete items | ✓ | ✓ | Own only | ✗ |
-->

---

## Business Rules

<!--
Document the core business logic and rules that govern the system:

Include:
- Validation rules (what makes data valid/invalid)
- Constraints and limitations (character limits, file sizes, quantity limits)
- Calculation rules (pricing, scoring, rankings)
- State transitions (status changes, workflow states)
- Conditional logic (if-then rules, eligibility criteria)
- Data integrity rules (relationships, dependencies)
- Temporal rules (expiration, scheduling, time-based logic)
- Access rules (who can do what under what conditions)

Example format:

### User Account Rules
- Username must be 3-20 characters, alphanumeric plus underscore/hyphen
- Email must be unique across all users
- Password must contain: 8+ chars, 1 uppercase, 1 lowercase, 1 number, 1 special char
- Account locked after 5 failed login attempts
- Accounts inactive for 90+ days are automatically archived

### Project Creation Rules
- Users can create up to 10 projects on free tier, unlimited on paid tier
- Project names must be unique per user
- Projects must have at least one team member
- Project deletion requires confirmation and admin approval if >100 items exist

### Pricing Rules
- Base price = $X per month
- Discount: 10% for annual billing, 20% for 100+ users
- Proration: charged/refunded based on days remaining in billing period
- Free trial: 14 days, credit card required, auto-converts to paid

Be specific and unambiguous - these rules should be clear enough to implement directly.
-->

---

## Features

<!--
Describe the features and functionality of the product:

For each major feature, document:
- Feature name and description
- User value and purpose
- Functional requirements (what it does)
- User interactions (how users interact with it)
- Edge cases and error states
- Success criteria (when is it working correctly)

Example format:

### Feature Name: User Dashboard

**Description:**
A personalized dashboard showing users their most relevant information and actions.

**User Value:**
Provides quick overview of account status, recent activity, and pending actions without navigation.

**Functionality:**
- Display user's name, profile picture, and account status
- Show 5 most recent activities with timestamps
- Display pending tasks/notifications with count badge
- Quick action buttons for common tasks
- Refresh data every 30 seconds automatically
- Load in <2 seconds on average connection

**User Interactions:**
- Click activity item → navigate to detail view
- Click notification → mark as read and navigate to source
- Click quick action → open modal/navigate to action page
- Pull to refresh → reload dashboard data
- Hover over items → show tooltips with additional context

**Edge Cases:**
- No recent activity: show placeholder message and suggested actions
- Failed data load: show error message with retry button
- Slow connection: show loading skeleton, timeout after 10s
- Very long names/titles: truncate with ellipsis, show full text on hover

**Success Criteria:**
- Dashboard loads within 2 seconds for 95% of users
- All widgets display accurate, real-time data
- Mobile responsive design works on screens 320px+
- Accessibility score 95+ on Lighthouse

---

### Feature Name: [Next Feature]

**Description:**
[What it is]

**User Value:**
[Why users need it]

**Functionality:**
- [What it does]

[Continue for each feature...]
-->

---

## User Flows

<!--
Document the step-by-step flows for key user journeys:

For each flow, include:
- Starting point (where user begins)
- Each step in the process
- Decision points and branches
- Success outcome
- Failure/error paths
- Alternative paths

Consider using:
- Numbered step-by-step lists
- Mermaid flowcharts for complex flows
- Screenshots or wireframes if available

Focus on user-facing flows that represent core value or common tasks.
-->

### Flow 1: New User Onboarding

<!--
Example flow structure:

**Goal:** Get new users set up and to their first value moment

**Starting Point:** User clicks "Sign Up" button

**Steps:**
1. User lands on registration page
   - Sees value proposition and example screenshots
   - Options: Sign up with email, Google, GitHub

2. User enters credentials
   - Email + password, or OAuth provider
   - Email validation: must be valid format
   - Password requirements displayed inline
   - Error states: invalid email, weak password, email already exists

3. Email verification (if email signup)
   - Confirmation email sent immediately
   - Email contains verification link (expires in 24h)
   - User clicks link → account activated
   - Alternative: user can resend verification email

4. Complete profile setup
   - Required fields: Name, Company (optional), Role
   - Optional fields: Avatar upload, Bio
   - Skip button available (can complete later)

5. Product tour
   - Interactive walkthrough of 3 key features
   - Progress indicator (step 1 of 3)
   - Skip tour option at any point
   - "Got it" to advance, tooltips pointing to UI elements

6. First action
   - Prompted to create first project/item
   - Template options or blank start
   - Celebratory message on completion

**Success Outcome:**
User completes onboarding and creates their first project within 5 minutes

**Error Paths:**
- Email verification not received: Resend button, check spam instructions
- Email link expired: Login page with option to resend
- Profile incomplete: Can proceed but prompted to complete on next login
- User abandons mid-flow: Progress saved, email reminder after 24h

**Metrics:**
- Time to complete: Target <5 minutes
- Completion rate: Target >60%
- Drop-off points: Track exits at each step
-->

### Flow 2: Creating a Project

<!--
Document the flow for creating a project:

**Goal:** [What user wants to accomplish]

**Starting Point:** [Where user begins]

**Steps:**
1. [First step]
   - [Details]
   - [Validations]
   - [Options/branches]

2. [Second step]
   - [Details]

[Continue steps...]

**Success Outcome:**
[What happens on success]

**Error Paths:**
[What can go wrong and how it's handled]

**Metrics:**
[Key metrics to track]
-->

<!--
Add more user flows as needed:
- Critical paths (must-work flows)
- Common workflows (frequently used)
- Complex processes (multi-step, decision-heavy)
- Error recovery flows
- Edge case scenarios
-->

---

## Out of Scope

<!--
Explicitly document what is NOT included in this specification:

Categories to consider:
- Features considered but deliberately excluded
- Future enhancements (V2, V3 features)
- Related functionality that belongs elsewhere
- Technical implementation details (belongs in AGENTS.md)
- Platform limitations or unsupported use cases
- Known constraints or acceptable limitations

Be specific about why items are out of scope:
- Not yet: planned for future release
- Never: doesn't align with product goals
- Elsewhere: covered by different product/team
- Technical limitation: not feasible with current technology

Example format:

### Not in V1 (Future Enhancements)
- Advanced reporting dashboard
- Mobile native apps (iOS/Android)
- Third-party integrations (Slack, Jira)
- Custom branding/white-labeling
- API access for external developers

### Explicitly Excluded
- Support for IE11 (browser too old, <1% users)
- Offline mode (requires complex sync, low ROI)
- File uploads >100MB (storage cost, edge cases)
- Real-time collaboration (complexity, different product direction)

### Out of Team Scope
- Payment processing: handled by billing team
- Email delivery: managed by platform infrastructure
- User analytics: separate analytics product

This helps prevent scope creep and sets clear expectations.
-->

---

## Open Questions

<!--
Document unresolved questions, decisions to be made, and areas needing clarification:

For each question:
- State the question clearly
- Provide context (why it matters)
- List possible options/answers being considered
- Note who needs to decide (PM, eng, design, legal, etc.)
- Track status (researching, blocked on X, answered)
- Link to related discussions/docs if applicable

Example format:

### Technical Questions
- **Q:** What's the maximum file upload size?
  - **Context:** Affects storage costs and user expectations
  - **Options:** 10MB (cheap), 50MB (moderate), 100MB (expensive)
  - **Owner:** PM + Eng
  - **Status:** Pending cost analysis
  - **Related:** [Link to cost doc]

### Product Questions
- **Q:** Should admins be able to impersonate users for support purposes?
  - **Context:** Helpful for debugging but privacy/security concerns
  - **Options:** Yes with audit log, Yes with user consent, No (train support differently)
  - **Owner:** PM + Legal
  - **Status:** Legal review in progress

### Design Questions
- **Q:** How should we handle project deletion - soft delete or hard delete?
  - **Context:** Users may accidentally delete, but soft delete adds complexity
  - **Options:** 30-day soft delete with restore option, Immediate hard delete with confirmation
  - **Owner:** PM + Design + Eng
  - **Status:** Leaning toward soft delete, need to confirm technical feasibility

### Business Questions
- **Q:** What happens when user downgrades from paid to free with >10 projects?
  - **Context:** Free tier allows 10 projects, paid allows unlimited
  - **Options:** Archive oldest, let user choose which to keep, mark all read-only until upgraded
  - **Owner:** PM + Business
  - **Status:** Researching competitor approaches

Mark questions as resolved once answered, but keep them in the doc for reference.
Move resolved Q&A to appropriate sections above.
-->

---
<!-- AI Agent should use to section to keep track when it last updated this file -->
*Last Updated: YYYY-MM-DD*
*This document is maintained for AI agent context and onboarding.*
