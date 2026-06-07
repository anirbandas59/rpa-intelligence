# Contributing to RPA Intelligence Frontend

## Overview

The RPA Intelligence frontend follows patterns established in design exploration files (`backend/data/samples/web/`). This document provides guidelines for maintaining consistency and quality when contributing code.

---

## Getting Started

### Prerequisites

- Node.js 18+
- npm 9+
- Familiarity with Next.js 16 App Router
- Understanding of TypeScript

### Setup

```bash
cd frontend
npm install
npm run dev  # Start dev server at http://localhost:3000
```

### Environment

Create `frontend/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Code Style

### TypeScript

- Use strict type checking (no `any` unless absolutely necessary)
- Define interfaces for all API responses (`src/lib/types.ts`)
- Use type guards for runtime validation
- Prefer `interface` over `type` for object shapes

```typescript
// ✅ Good
interface UseCase {
  id: string;
  name: string;
  description: string | null;
}

// ❌ Avoid
type UseCase = {
  id: any;
  name: any;
  description?: any;
};
```

### Component Structure

**File organization:**
```
src/
  components/
    rpa/           # Design system components (Card, Btn, Pill, etc.)
    shared/        # Shared utilities (Icon, Gauge, EmptyState, etc.)
    ui/            # shadcn base components (rarely modified)
  app/             # Next.js pages (App Router)
  lib/             # Utilities, hooks, API clients
```

**Component template:**
```tsx
"use client";  // Only if needed (uses hooks, interactivity)

import React from "react";
import type { ComponentProps } from "react";

interface MyComponentProps {
  required: string;
  optional?: number;
  children?: React.ReactNode;
}

export function MyComponent({ required, optional = 10, children }: MyComponentProps) {
  return (
    <div style={{ padding: spacing.cardDefault }}>
      {children}
    </div>
  );
}
```

---

## Design Patterns

### When to Use Inline Styles vs Tailwind

**Inline styles for:**
- Precise optical values from explorations (fontSize: 10.5px, padding: 18px)
- Dynamic calculations (`width: ${percent}%`)
- CSS functions (`color-mix()`, `linear-gradient()`)
- Complex grid templates (`gridTemplateColumns: "340px 1fr"`)
- SVG properties (strokeDasharray, transform)

**Tailwind for:**
- Layout structure (`grid`, `flex`, `gap-*`)
- Responsive design (`md:`, `lg:`, `sm:max-w-*`)
- Hover states (`hover:bg-*`, `transition-*`)
- Common utilities (`text-muted-foreground`, `border-border`)

**Example:**
```tsx
// ✅ Hybrid approach
<div className="grid gap-4 md:gap-6">  {/* Tailwind: layout */}
  <Card
    className="hover:shadow-md transition-shadow"  {/* Tailwind: interactions */}
    style={{ padding: 18, borderRadius: 14 }}     {/* Inline: exploration values */}
  >
    <SectionLabel style={{ fontSize: 10.5 }}>   {/* Inline: optical precision */}
      Scoring Dimensions
    </SectionLabel>
  </Card>
</div>
```

---

### Component Library Usage

**Always prefer library components over custom markup:**

```tsx
// ❌ Don't reinvent
<div style={{
  borderRadius: 14,
  background: "var(--surface)",
  padding: 18,
  border: "1px solid var(--border)"
}}>
  <div style={{
    fontSize: 10.5,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: 1.4,
    color: "var(--muted-fg)"
  }}>
    Title
  </div>
</div>

// ✅ Use library
<Card pad={18}>
  <SectionLabel>Title</SectionLabel>
</Card>
```

---

### Design Tokens

**Never hardcode values:**

```tsx
// ❌ Magic numbers
<div style={{ padding: 18, gap: 22, borderRadius: 14 }}>

// ✅ Use tokens
import { spacing } from "@/lib/design-tokens";

<div style={{
  padding: spacing.cardDefault,
  gap: spacing.gapLoose,
  borderRadius: spacing.cardRadius
}}>
```

**Never hardcode colors:**

```tsx
// ❌ Hardcoded hex
<span style={{ color: "#10b981" }}>Success</span>

// ✅ CSS custom properties
<span style={{ color: "var(--c-green)" }}>Success</span>
```

---

## State Management

### Server State (API data)

Use React state + useEffect for API calls:

```tsx
const [data, setData] = useState<Project | null>(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState("");

useEffect(() => {
  async function fetchData() {
    try {
      const result = await apiGet<Project>(`/api/v1/projects/${id}`);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }
  fetchData();
}, [id]);
```

### Local State (UI state)

Use useState for component-local state:

```tsx
const [activeTab, setActiveTab] = useState<"pipeline" | "portfolio">("pipeline");
const [selectedId, setSelectedId] = useState<string | null>(null);
```

### Form State

Use controlled components:

```tsx
const [name, setName] = useState("");
const [description, setDescription] = useState("");

<Input
  value={name}
  onChange={(e) => setName(e.target.value)}
  required
/>
```

---

## API Integration

### API Client Usage

All API calls go through `src/lib/api.ts`:

```tsx
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";

// GET
const projects = await apiGet<Project[]>("/api/v1/projects");

// POST
const newProject = await apiPost("/api/v1/projects", {
  name: "New Project",
  description: "Description",
});

// PUT
await apiPut(`/api/v1/projects/${id}`, { name: "Updated Name" });

// DELETE
await apiDelete(`/api/v1/projects/${id}`);
```

### Error Handling

Always handle errors with user feedback:

```tsx
try {
  await apiPost("/api/v1/projects", data);
  toast.success("Project created");
  router.push("/projects");
} catch (err) {
  toast.error(err instanceof Error ? err.message : "Failed to create project");
}
```

### Loading States

Show loading indicators for async operations:

```tsx
const [creating, setCreating] = useState(false);

async function handleCreate() {
  setCreating(true);
  try {
    await apiPost("/api/v1/projects", data);
  } catch (err) {
    toast.error(err.message);
  } finally {
    setCreating(false);
  }
}

<Btn disabled={creating}>
  {creating ? (
    <>
      <Loader2 className="h-4 w-4 animate-spin mr-2" />
      Creating...
    </>
  ) : (
    "Create"
  )}
</Btn>
```

---

## Visualization Components

### SVG-based Visualizations

Use inline styles for dynamic SVG properties:

```tsx
<svg width={width} height={height}>
  <circle
    cx={x}
    cy={y}
    r={radius}
    fill={`color-mix(in oklab, ${color} 30%, transparent)`}
    stroke={color}
    strokeWidth={1.5}
  />
</svg>
```

### Dynamic Calculations

Calculate positions/sizes in JavaScript, render in SVG:

```tsx
const x = (value / max) * 100;  // Percentage
const angle = (value / max) * 360;  // Degrees
const width = `${(value / total) * 100}%`;  // CSS percentage

<div style={{
  position: "absolute",
  left: `${x}%`,
  width: width,
  transform: `rotate(${angle}deg)`,
}}>
```

---

## Accessibility

### Keyboard Navigation

All interactive elements must be keyboard accessible:

```tsx
// ✅ Button (Tab, Enter/Space)
<button onClick={handleClick}>Click me</button>

// ✅ Link (Tab, Enter)
<Link href="/projects">Projects</Link>

// ❌ Non-interactive div
<div onClick={handleClick}>Click me</div>

// ✅ Div with role + keyboard
<div
  role="button"
  tabIndex={0}
  onClick={handleClick}
  onKeyDown={(e) => e.key === "Enter" && handleClick()}
>
  Click me
</div>
```

### Semantic HTML

Use correct elements for their purpose:

```tsx
// ✅ Semantic form
<form onSubmit={handleSubmit}>
  <Label htmlFor="name">Name</Label>
  <Input id="name" type="text" required />
  <button type="submit">Submit</button>
</form>

// ❌ Div soup
<div>
  <span>Name</span>
  <div onClick={handleChange}>...</div>
  <div onClick={handleSubmit}>Submit</div>
</div>
```

### Focus Management

Manage focus for modals/sheets:

```tsx
<Input
  autoFocus  // Focus first field when modal opens
  onKeyDown={(e) => {
    if (e.key === "Escape") {
      onClose();
    }
  }}
/>
```

---

## Testing

### Component Tests

Write unit tests for isolated components:

```tsx
import { render, screen } from "@testing-library/react";
import { Card } from "./Card";

test("renders children", () => {
  render(<Card>Content</Card>);
  expect(screen.getByText("Content")).toBeInTheDocument();
});

test("applies padding", () => {
  const { container } = render(<Card pad={20}>Content</Card>);
  const card = container.firstChild as HTMLElement;
  expect(card.style.padding).toBe("20px");
});
```

### Integration Tests

Test user flows:

```tsx
test("creates new project", async () => {
  render(<NewProjectPage />);
  
  await userEvent.type(screen.getByLabelText("Name"), "Test Project");
  await userEvent.click(screen.getByText("Create"));
  
  await waitFor(() => {
    expect(screen.getByText("Project created")).toBeInTheDocument();
  });
});
```

### Visual Regression

Compare against exploration references:

```bash
npm run test:visual  # Compares screenshots
```

---

## Performance

### Memoization

Use React.memo for expensive components:

```tsx
export const ExpensiveComponent = React.memo(function ExpensiveComponent({ data }) {
  // Heavy computation
  return <div>{data}</div>;
});
```

### useCallback for Event Handlers

Prevent unnecessary re-renders:

```tsx
const handleClick = useCallback(() => {
  doSomething(id);
}, [id]);  // Only recreate if id changes
```

### useMemo for Computed Values

Cache expensive calculations:

```tsx
const sortedItems = useMemo(() => {
  return items.sort((a, b) => b.score - a.score);
}, [items]);
```

### Lazy Loading

Defer loading heavy visualizations:

```tsx
const Gantt = dynamic(() => import("@/components/shared/Gantt"), {
  loading: () => <Loader2 className="animate-spin" />,
  ssr: false,
});
```

---

## Git Workflow

### Branching

- `main` — Production-ready code
- `dev` — Integration branch (default)
- `feat/*` — Feature branches
- `fix/*` — Bug fix branches

### Commit Messages

Follow conventional commits:

```
type(scope): description

- feat: New feature
- fix: Bug fix
- refactor: Code restructure
- test: Add/update tests
- docs: Documentation
- chore: Maintenance
```

**Examples:**
```
feat(stage1): add gauge component
fix(api): handle null readiness response
refactor(hub): extract portfolio matrix component
test(card): add padding tests
docs(design): update color system
chore(deps): upgrade next to 16.2.6
```

### Pull Requests

**Before opening PR:**
1. Run `npm run build` — Ensure TypeScript compiles
2. Run `npm run lint` — Fix linting errors
3. Run `npm run test` — All tests pass
4. Check visual diff against exploration files

**PR template:**
- What: Brief description of changes
- Why: Motivation (bug fix, feature request, refactor)
- How: Technical approach
- Testing: How you tested the changes
- Screenshots: Before/after for UI changes

---

## Common Mistakes

### ❌ Inline event handlers in map

```tsx
// ❌ Creates new function on every render
{items.map(item => (
  <button onClick={() => handleClick(item.id)}>
    {item.name}
  </button>
))}

// ✅ Use data attributes
{items.map(item => (
  <button data-id={item.id} onClick={handleClick}>
    {item.name}
  </button>
))}

function handleClick(e: React.MouseEvent<HTMLButtonElement>) {
  const id = e.currentTarget.dataset.id;
  doSomething(id);
}
```

### ❌ Missing keys in lists

```tsx
// ❌ Index as key (breaks on reorder)
{items.map((item, i) => <div key={i}>{item.name}</div>)}

// ✅ Stable unique ID
{items.map(item => <div key={item.id}>{item.name}</div>)}
```

### ❌ Mutating state directly

```tsx
// ❌ Direct mutation
items.push(newItem);
setItems(items);

// ✅ Create new array
setItems([...items, newItem]);
```

### ❌ Not handling loading/error states

```tsx
// ❌ Assumes data exists
<div>{data.name}</div>

// ✅ Handle all states
{loading && <Loader2 />}
{error && <Alert>{error}</Alert>}
{data && <div>{data.name}</div>}
```

---

## Resources

- **Design System:** `DESIGN_SYSTEM.md`
- **Exploration Files:** `backend/data/samples/web/`
- **Component Library:** `src/components/rpa/`
- **Next.js 16 Docs:** `node_modules/next/dist/docs/`
- **Tailwind v4:** CSS-based config in `globals.css`

---

## Questions?

- Check `DESIGN_SYSTEM.md` for visual patterns
- Reference exploration files for exact implementations
- Ask in #frontend channel or open a discussion issue
