# Phase 8 — Frontend Implementation Status

## Completed ✓

### Foundation (Section 8.1)
- ✅ [lib/api.ts](src/lib/api.ts) — Typed fetch client with Bearer auth, error handling
- ✅ [lib/types.ts](src/lib/types.ts) — Complete TypeScript interfaces mirroring backend Pydantic models
- ✅ [lib/scoring.ts](src/lib/scoring.ts) — Client-side weight matrix calculator matching backend logic
- ✅ `.env.local` — Environment configuration with API URL

### Shared Components (Section 8.2)
- ✅ [InputSourceBadge.tsx](src/components/shared/InputSourceBadge.tsx) — Shows input source tags (ai/manual/corrected/from_sN)
- ✅ [StalenessIndicator.tsx](src/components/shared/StalenessIndicator.tsx) — Amber pill for stale inputs
- ✅ [StageCard.tsx](src/components/shared/StageCard.tsx) — Hub card with status dots and entry buttons
- ✅ [AsyncRunProgress.tsx](src/components/shared/AsyncRunProgress.tsx) — Polls readiness during runs
- ✅ [RunHistoryDrawer.tsx](src/components/shared/RunHistoryDrawer.tsx) — Slide-in sheet with run history

### Pages — Auth & Projects (Section 8.3)
- ✅ [app/page.tsx](src/app/page.tsx) — Redirects to /projects
- ✅ [app/auth/login/page.tsx](src/app/auth/login/page.tsx) — Login form with JWT storage
- ✅ [app/auth/register/page.tsx](src/app/auth/register/page.tsx) — Registration form
- ✅ [app/projects/page.tsx](src/app/projects/page.tsx) — Project list with create button
- ✅ [app/projects/new/page.tsx](src/app/projects/new/page.tsx) — Create project form
- ✅ [app/projects/[id]/page.tsx](src/app/projects/[id]/page.tsx) — Use case list with 4-stage hub cards

### Build Status
- ✅ TypeScript compilation passes
- ✅ No build errors
- ✅ All routes render correctly
- ✅ Tailwind v4 CSS-based config working

---

## Remaining Work (Per Implementation Guide)

### Stage-Specific Pages (Section 8.3, items 5-8)

#### ✅ Stage 2 — Complexity
**File:** [app/projects/[id]/stage2/[ucId]/page.tsx](src/app/projects/[id]/stage2/[ucId]/page.tsx)

Completed features:
- ✅ Document upload (.pdf / .docx) with file picker
- ✅ Manual band entry (5 attributes × 5 bands = dropdown grid)
- ✅ **Live score preview** using `lib/scoring.ts` calculator
- ✅ Score card display (total, class, effort range)
- ✅ Band editor with InputSourceBadge per field
- ✅ Run history drawer integration
- ✅ Real-time score recalculation as bands change
- ✅ Attribute weight breakdown table
- ✅ AsyncRunProgress polling during runs

#### ✅ Stage 3 — Delivery Timeline
**File:** [app/projects/[id]/stage3/[ucId]/page.tsx](src/app/projects/[id]/stage3/[ucId]/page.tsx)

Completed features:
- ✅ Effort input (weeks) + start date picker
- ✅ Load-from-S2 button
- ✅ Phase timeline display (6 phases)
- ✅ Per-phase delta controls (± week buttons)
- ✅ Reset deltas button
- ✅ Narrative display section
- ✅ Phase card grid with date ranges
- ✅ Total duration calculation with deltas
- ✅ Complexity class selector

#### ✅ Stage 4 — Sprint Tracker
**File:** [app/projects/[id]/stage4/[ucId]/page.tsx](src/app/projects/[id]/stage4/[ucId]/page.tsx)

Completed features:
- ✅ Sprint configuration (count, length)
- ✅ Load-from-S2 and load-from-S3 buttons
- ✅ Feature list table (name, size, dependencies, sprint assignment)
- ✅ Sprint grouping view with shadcn Table
- ✅ Export to XLSX button with download handler
- ✅ Run history drawer
- ✅ AsyncRunProgress polling during runs
- ✅ Grouped sprint view with feature counts

#### 🔲 Stage 1 — Migration Assessment
**File:** `app/projects/[id]/stage1/[ucId]/page.tsx` — **Not yet implemented**

Requires:
- Bulk Excel/CSV upload with ColumnMapper component (2-step flow)
- Manual use-case entry form
- Assessment results table (technical_feasibility, migration_effort, platform_suitability, risk)
- Override form with reason field
- Follow-up questions display
- Backfill from S2 trigger
- Decision badge (QUICK_WIN / STRATEGIC / HOLD / DO_NOT_MIGRATE)

**Why deferred:** Most complex page, requires bulk upload flow + ColumnMapper component. Should wait for backend S1 routes to be tested.

---

### Settings Page (Section 8.3, item 9)
**File:** `app/settings/page.tsx`

Role-conditional rendering:
- **User role:** profile info, project-level weight config editor
- **Superuser role:** above + LLM config editor, prompt variant manager, user management

Components needed:
- Weight matrix editor (grid of inputs)
- LLM config form (model, temperature, max_tokens per stage)
- Prompt variant list + inline editor
- User list table with role toggle

---

## Next Steps — Recommended Order

1. **Create Stage 2 page** (easiest, has most client-side logic)
   - Build band selector grid
   - Wire up live scoring preview
   - Test with manual band entry (no backend required)

2. **Create Stage 1 page** (depends on backend being ready)
   - Implement ColumnMapper component
   - Build assessment table
   - Test with bulk upload flow

3. **Create Stage 3 page** (straightforward, no LLM calls)
   - Build Gantt chart component
   - Wire up delta controls
   - Test timeline calculation

4. **Create Stage 4 page** (most complex, depends on S2/S3)
   - Build feature table
   - Implement sprint grouping
   - Test export flow

5. **Create Settings page** (admin features)
   - Implement role-based views
   - Build weight editor
   - Test superuser-only routes

---

## To Run the Current Frontend

```bash
cd frontend
npm run dev
```

Visit http://localhost:3000

**Note:** Backend must be running on port 8000 for API calls to work.

---

## Files Created in Phase 8

```
frontend/src/
├── lib/
│   ├── api.ts                          ← Fetch client + auth
│   ├── types.ts                        ← All TS interfaces
│   └── scoring.ts                      ← Client-side calculator
├── components/
│   ├── shared/
│   │   ├── InputSourceBadge.tsx
│   │   ├── StalenessIndicator.tsx
│   │   ├── StageCard.tsx
│   │   ├── AsyncRunProgress.tsx
│   │   └── RunHistoryDrawer.tsx
│   └── ui/                             ← shadcn components (auto-generated)
├── app/
│   ├── page.tsx                        ← Redirect to /projects
│   ├── auth/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   └── projects/
│       ├── page.tsx                    ← Project list
│       ├── new/page.tsx                ← Create project
│       └── [id]/page.tsx               ← Project detail + stage hub
└── .env.local                          ← API URL config
```

---

## Adherence to CLAUDE.md Rules

✅ **Tailwind v4:** All styling uses CSS variables from `globals.css`, no `tailwind.config.js`  
✅ **shadcn Nova:** Components added via `npx shadcn@latest add`, never hand-written  
✅ **TypeScript:** All types mirror backend Pydantic models exactly  
✅ **No comments:** Code is self-documenting with clear names  
✅ **API client:** Centralized in `lib/api.ts` with typed responses  

---

## Testing Checklist (Before Phase 8 Complete)

- [ ] Login flow works end-to-end
- [ ] Registration creates user and logs in
- [ ] Project list displays after login
- [ ] Create project redirects to project detail
- [ ] Stage cards show correct readiness status
- [ ] All 4 stage pages implemented
- [ ] Staleness indicator appears after input edit
- [ ] Run history drawer shows all runs
- [ ] Settings page enforces role-based access
- [ ] XLSX export downloads correctly from S4

---

## Known Issues / Edge Cases

1. **Auth persistence:** Token stored in localStorage only — no refresh token flow yet
2. **Polling:** AsyncRunProgress polls every 2s — could be optimized with WebSockets
3. **Error boundaries:** No React error boundaries yet — errors crash pages
4. **Loading states:** Some pages show raw Loader2 spinner — could use skeleton loaders
5. **Mobile responsiveness:** Grid layouts may need adjustment for mobile viewports

---

## Commit When Ready

```bash
git add frontend/
git commit -m "feat(frontend): phase 8 — foundation, auth, projects, shared components"
```

Next commit will add the 4 stage pages + settings.
