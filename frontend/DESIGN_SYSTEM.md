# RPA Intelligence — Design System

This document describes the design patterns, components, and conventions used in the RPA Intelligence frontend. All patterns are derived from the design explorations in `backend/data/samples/web/`.

## Philosophy

The RPA Intelligence design system follows a **hybrid approach**:
- **Tailwind CSS** for layout structure, responsive design, and common utilities
- **Inline styles** for precise optical values, dynamic calculations, and exploration-specific patterns
- **Component library** (`src/components/rpa/`) for reusable UI primitives

### When to Use What

**Use Tailwind for:**
- Layout structure (`grid`, `flex`, `gap-*`)
- Responsive breakpoints (`md:`, `lg:`, `sm:max-w-*`)
- Hover states and transitions (`hover:bg-*`, `transition-*`)
- Common utilities (`text-muted-foreground`, `border-border`)

**Use inline styles for:**
- Precise optical values (fontSize: 10.5px, padding: 18px)
- Dynamic calculations (`width: ${percent}%`, `fontSize: size * 0.31`)
- SVG properties (strokeDasharray, transform, fill)
- CSS functions (`color-mix()`, `linear-gradient()`, `calc()`)
- Complex grid templates (`gridTemplateColumns: "340px 1fr"`)

---

## Design Tokens

All design tokens are centralized in `src/lib/design-tokens.ts`.

### Typography Scale

```typescript
export const typography = {
  sectionLabel: 'text-[10.5px] font-bold uppercase tracking-[1.4px] text-muted-foreground',
  bodyDefault: 'text-[12.8px] leading-relaxed',
  bodyMuted: 'text-[11.5px] text-muted-foreground',
  mono: 'font-mono text-[11.5px]',
  monoLarge: 'font-mono text-[20px] font-bold',
  h1: 'text-[26px] font-bold tracking-tight',
  h2: 'text-[19px] font-bold',
  h3: 'text-[13.5px] font-semibold',
}
```

**Usage:**
```tsx
<SectionLabel>Assessment pipeline</SectionLabel>
<div style={{ fontSize: 12.5, fontWeight: 600 }}>Use case name</div>
<span style={{ fontFamily: "var(--mono)", fontSize: 11 }}>24</span>
```

### Spacing System

```typescript
export const spacing = {
  cardDefault: 18,    // padding: 18
  cardCompact: 13,    // padding: 13
  cardLarge: 22,      // padding: 22
  gapTight: 12,       // gap: 12
  gapDefault: 18,     // gap: 18
  gapLoose: 22,       // gap: 22
  cardRadius: 14,     // borderRadius: 14
  buttonRadius: 9,    // borderRadius: 9
  pillRadius: 6,      // borderRadius: 6
}
```

**Usage:**
```tsx
<Card pad={spacing.cardDefault}>
  <div style={{ display: "flex", gap: spacing.gapDefault }}>
```

### Color System

Colors use OKLCH color space for perceptual uniformity. Access via CSS custom properties:

**Surface colors:**
- `--bg` — App background (oklch(0.105 0.015 270))
- `--surface` — Card background (oklch(0.155 0.016 270))
- `--surface-2` — Elevated surfaces (oklch(0.205 0.016 270))

**Text colors:**
- `--fg` — Primary text (oklch(0.96 0.005 270))
- `--fg-2` — Secondary text (oklch(0.80 0.01 270))
- `--muted-fg` — Muted text (oklch(0.62 0.015 270))

**Semantic colors:**
- `--c-green` — Success, quick wins, complete (oklch(0.74 0.17 150))
- `--c-teal` — Information, strategic (oklch(0.74 0.13 195))
- `--c-blue` — Ready state (oklch(0.70 0.16 245))
- `--c-violet` — AI/agent indicators (oklch(0.68 0.21 292))
- `--c-amber` — Warnings, hold (oklch(0.78 0.15 66))
- `--c-red` — Errors, do not migrate (oklch(0.68 0.20 25))
- `--primary` — Primary blue-violet (oklch(0.66 0.20 264))

**Usage:**
```tsx
<div style={{ color: "var(--c-green)", background: "var(--surface)" }}>
<span style={{ color: "var(--muted-fg)" }}>Muted label</span>
```

---

## Component Library

All reusable components live in `src/components/rpa/`. Each component matches the exploration patterns exactly.

### Card

**File:** `src/components/rpa/Card.tsx`

**Props:**
- `pad?: number` — Padding in pixels (default: 18)
- `hover?: boolean` — Enable hover lift effect
- `style?: CSSProperties` — Additional inline styles
- `className?: string` — Additional Tailwind classes

**Usage:**
```tsx
<Card pad={18} hover>
  <SectionLabel>Scoring Dimensions</SectionLabel>
  {/* content */}
</Card>
```

**Visual:**
- Border: `1px solid var(--border)`
- Background: `var(--surface)`
- Border radius: `14px`
- Hover: `translateY(-2px)` + enhanced shadow

---

### Btn

**File:** `src/components/rpa/Btn.tsx`

**Props:**
- `variant?: "default" | "ghost" | "outline" | "subtle"` (default: "default")
- `size?: "sm" | "md" | "lg"` (default: "md")
- `icon?: IconName` — Left icon
- `iconR?: IconName` — Right icon
- `children` — Button text
- Standard button props (onClick, disabled, type, etc.)

**Sizes:**
- `sm`: height 30px, fontSize 12px, padding 0 12px
- `md`: height 36px, fontSize 13px, padding 0 16px
- `lg`: height 42px, fontSize 14px, padding 0 20px

**Variants:**
- `default`: Primary filled (blue-violet)
- `ghost`: Transparent, hover background
- `outline`: Border only
- `subtle`: Light background, no border

**Usage:**
```tsx
<Btn size="sm" icon="plus" onClick={handleCreate}>
  Create Use Case
</Btn>
<Btn variant="outline" iconR="arrowR">Next</Btn>
```

---

### SectionLabel

**File:** `src/components/rpa/SectionLabel.tsx`

**Props:**
- `children` — Label text
- `style?: CSSProperties` — Additional styles

**Visual:**
- Font size: 10.5px
- Weight: 700 (bold)
- Transform: uppercase
- Letter spacing: 1.4px
- Color: `var(--muted-fg)`

**Usage:**
```tsx
<SectionLabel>Assessment pipeline</SectionLabel>
<SectionLabel style={{ marginBottom: 12 }}>All use cases</SectionLabel>
```

---

### Pill

**File:** `src/components/rpa/Pill.tsx`

**Props:**
- `color?: string` — Badge color (CSS custom property or hex)
- `solid?: boolean` — Filled variant (default: outline)
- `mono?: boolean` — Use monospace font
- `children` — Badge text

**Usage:**
```tsx
<Pill color="var(--c-green)" solid>QUICK_WIN</Pill>
<Pill color="var(--primary)" mono>S1</Pill>
<Pill color="var(--c-amber)">ai_extracted</Pill>
```

---

### Icon

**File:** `src/components/shared/icons.tsx`

**Props:**
- `name: IconName` — Icon identifier (see list below)
- `size?: number` — Icon size in pixels (default: 16)
- `strokeWidth?: number` — Stroke width (default: 1.5)
- `style?: CSSProperties` — Additional styles

**Available icons:**
`target`, `grid`, `calendar`, `layers`, `check`, `x`, `plus`, `arrowR`, `arrowL`, `chevR`, `chevL`, `search`, `filter`, `upload`, `download`, `settings`, `user`, `users`, `bot`, `zap`, `clock`, `sliders`, `link`, `external`, `edit`, `trash`, `copy`, `file`, `folder`, `image`, `video`, `code`, `terminal`, `chart`, `pie`, `bar`, `line`, `scatter`, `alert`, `info`, `help`

**Usage:**
```tsx
<Icon name="target" size={15} style={{ color: "var(--muted-fg)" }} />
<Icon name="arrowR" size={11} />
```

---

### Gauge

**File:** `src/components/shared/Gauge.tsx`

**Props:**
- `value: number` — Current value (0-100)
- `band?: MigrationDecision` — Color band (QUICK_WIN, STRATEGIC, etc.)
- `size?: number` — Diameter in pixels (default: 80)
- `thick?: number` — Stroke thickness (default: 8)

**Usage:**
```tsx
<Gauge value={78} band="QUICK_WIN" size={170} thick={12} />
<Gauge value={score} band={decision} size={40} thick={5} />
```

**Visual:**
- SVG-based radial progress
- Arc from -90° (top) clockwise
- Color from band metadata
- Center displays numeric value

---

### ComplexityChip

**File:** `src/components/shared/ComplexityChip.tsx`

**Props:**
- `cls: Band` — Complexity class (XS, S, M, L, XL)
- `size?: number` — Chip size in pixels (default: 30)

**Usage:**
```tsx
<ComplexityChip cls="L" size={30} />
<ComplexityChip cls={complexity_class} size={26} />
```

**Visual:**
- Rounded square with complexity letter
- Color-coded background (XS=green, S=teal, M=yellow, L=amber, XL=red)
- Monospace font

---

### PriorityBadge

**File:** `src/components/shared/PriorityBadge.tsx`

**Props:**
- `band: MigrationDecision` — Priority band (QUICK_WIN, STRATEGIC, HOLD, DO_NOT_MIGRATE)

**Usage:**
```tsx
<PriorityBadge band="QUICK_WIN" />
<PriorityBadge band={migration_decision} />
```

**Visual:**
- Pill-shaped badge with band label
- Color-coded (green, teal, amber, red)
- Font size: 10px, weight: 600

---

### MiniSpark

**File:** `src/components/shared/MiniSpark.tsx`

**Props:**
- `values: number[]` — Data points
- `color?: string` — Line color (default: "var(--primary)")
- `w?: number` — Width in pixels (default: 60)
- `h?: number` — Height in pixels (default: 20)

**Usage:**
```tsx
<MiniSpark values={[1, 3, 2, 5, 4]} color="var(--c-teal)" w={70} h={22} />
<MiniSpark values={phases.map(p => p.weeks)} color="var(--primary)" w={56} h={22} />
```

**Visual:**
- SVG sparkline chart
- Smooth path connecting points
- No axes or labels

---

## Layout Patterns

### Scorecard Layout (Stage 1)

**Grid:** `gridTemplateColumns: "340px 1fr"`

```tsx
<div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 22 }}>
  {/* Left column: Gauge + inputs */}
  <Card pad={18}>
    <Gauge value={score} band={band} size={170} />
    {/* ... */}
  </Card>
  
  {/* Right column: Dimensions + analysis */}
  <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
    <Card pad={18}>
      {/* Dimensions grid */}
    </Card>
  </div>
</div>
```

---

### Band Picker Layout (Stage 2)

**Grid:** 5×5 interactive table

```tsx
<div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 2 }}>
  {BANDS.map(band => (
    <button
      onClick={() => handleBandSelect(band)}
      style={{
        padding: "8px 12px",
        background: selected === band ? color : "transparent",
        border: `1px solid ${color}`,
        borderRadius: 8,
      }}
    >
      {band}
    </button>
  ))}
</div>
```

---

### Gantt Layout (Stage 3)

**Structure:** Relative container + absolute gridlines + phase bars

```tsx
<div style={{ position: "relative", height: 400, padding: "20px 0" }}>
  {/* Gridlines */}
  <div style={{ position: "absolute", left: 168, right: 0, top: 0, bottom: 0, display: "flex" }}>
    {weekColumns.map((_, i) => (
      <div key={i} style={{ width: `${100/totalWeeks}%`, borderLeft: "1px solid var(--border)" }} />
    ))}
  </div>
  
  {/* Phase bars */}
  {phases.map(phase => (
    <div style={{
      position: "absolute",
      left: `${startPercent}%`,
      width: `${widthPercent}%`,
      height: 32,
      background: `linear-gradient(90deg, ${color}, color-mix(in oklab, ${color} 78%, black))`,
      borderRadius: 7,
    }}>
      {phase.name}
    </div>
  ))}
</div>
```

---

### Portfolio Matrix (Hub)

**Grid:** `gridTemplateColumns: "1.55fr 1fr"`

```tsx
<div style={{ display: "grid", gridTemplateColumns: "1.55fr 1fr", gap: 22 }}>
  {/* Left: Scatter plot */}
  <div style={{ position: "relative", borderLeft: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
    {useCases.map(uc => (
      <div style={{
        position: "absolute",
        left: `${xPercent}%`,
        top: `${yPercent}%`,
        transform: "translate(-50%, -50%)",
      }}>
        {/* Bubble */}
      </div>
    ))}
  </div>
  
  {/* Right: Ranked list */}
  <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
    {sortedUseCases.map((uc, i) => (
      <Card pad={13} hover>
        <span>{i + 1}</span>
        <span>{uc.name}</span>
      </Card>
    ))}
  </div>
</div>
```

---

## Micro-interactions

### Card Hover

**CSS class:** `rpa-card-hover`

```css
.rpa-card-hover {
  transition: all 0.15s ease;
  cursor: pointer;
}

.rpa-card-hover:hover {
  transform: translateY(-2px);
  border-color: color-mix(in oklab, var(--border) 200%, transparent);
  box-shadow: 0 4px 12px color-mix(in oklab, var(--primary) 15%, transparent);
}
```

---

### Pulse Animation

**CSS keyframes:** `rpaPulse`

```css
@keyframes rpaPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

**Usage:**
```tsx
<div style={{
  width: 7,
  height: 7,
  borderRadius: 99,
  background: "var(--primary)",
  animation: "rpaPulse 1.6s ease-in-out infinite",
}} />
```

---

### Gradient Text

**CSS class:** `rpa-gradient-text`

```css
.rpa-gradient-text {
  background: linear-gradient(135deg, var(--primary) 0%, var(--c-violet) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
```

**Usage:**
```tsx
<h1 className="rpa-gradient-text" style={{ fontSize: 30, fontWeight: 700 }}>
  {project.name}
</h1>
```

---

### Gradient Hero

**CSS class:** `gradient-hero`

```css
.gradient-hero {
  background: linear-gradient(135deg, oklch(0.66 0.20 264 / 12%), transparent 60%);
}
```

**Usage:**
```tsx
<div className="gradient-hero border-b border-border/50">
  <div className="py-6 px-7">
    {/* Hero content */}
  </div>
</div>
```

---

## Common Patterns

### Section Header

```tsx
<SectionLabel style={{ marginBottom: 12 }}>
  Assessment pipeline · {selectedUc.name}
</SectionLabel>
```

---

### Status Dot

```tsx
<span style={{
  width: 7,
  height: 7,
  borderRadius: 99,
  background: statusColor,
  display: "inline-block",
  ...(isRunning ? { animation: "rpaPulse 1.6s ease-in-out infinite" } : {}),
}} />
```

---

### Mono Stat

```tsx
<div>
  <div style={{ fontFamily: "var(--mono)", fontSize: 24, fontWeight: 700 }}>
    {value}
  </div>
  <div style={{ fontSize: 11, color: "var(--muted-fg)" }}>
    {label}
  </div>
</div>
```

---

### Progress Bar

```tsx
<div style={{ width: 52, height: 5, borderRadius: 99, background: "var(--track)", overflow: "hidden" }}>
  <div style={{ width: `${percent}%`, height: "100%", background: "var(--c-green)" }} />
</div>
```

---

### Field Row (Stage 1 inputs)

```tsx
<FieldRow label="Process name" value={processName} source="manual" />
```

**Visual:**
- Label: 10.5px, uppercase, muted
- Value: 12.5px, semibold
- Source pill: 9px, tight padding

---

## Accessibility

- All interactive elements have visible focus states
- Forms use semantic HTML (`<form>`, `<label>`, `<input>`)
- Buttons have descriptive text (avoid icon-only buttons)
- Color is never the only indicator (use text + icons)
- Keyboard navigation works everywhere (Tab, Enter, Escape)

---

## Performance

- Use CSS animations, not JavaScript
- Lazy-load heavy visualizations (Gantt, matrix)
- Debounce expensive calculations (scoring, layout)
- Virtualize long lists (>100 items)
- Memoize component props with useMemo/useCallback

---

## Development Guidelines

### 1. Always use design tokens
```tsx
// ❌ Don't
<div style={{ padding: 18, gap: 22 }}>

// ✅ Do
<div style={{ padding: spacing.cardDefault, gap: spacing.gapLoose }}>
```

### 2. Reference exploration files for patterns
Before implementing a new UI pattern, check `backend/data/samples/web/` for the exploration equivalent.

### 3. Component library over custom implementations
```tsx
// ❌ Don't
<div style={{ borderRadius: 14, background: "var(--surface)", padding: 18, border: "1px solid var(--border)" }}>

// ✅ Do
<Card pad={18}>
```

### 4. Inline styles for visualization, Tailwind for utilities
```tsx
// ✅ Good hybrid
<div className="grid gap-4 md:gap-6">
  <Card style={{ padding: spacing.cardDefault, borderRadius: spacing.cardRadius }}>
    <SectionLabel style={{ fontSize: 10.5 }}>Title</SectionLabel>
  </Card>
</div>
```

### 5. Never hardcode colors
```tsx
// ❌ Don't
<div style={{ color: "#10b981" }}>

// ✅ Do
<div style={{ color: "var(--c-green)" }}>
```

---

## Visual Regression Testing

Run visual comparison tests before merging:

```bash
npm run test:visual
```

This compares current screenshots against exploration reference images at:
- Stage 1 scorecard
- Stage 2 band picker
- Stage 3 Gantt
- Stage 4 sprint board
- Hub pipeline view
- Hub portfolio map

Tolerance: 5px variance allowed for dynamic content (user names, dates, scores).

---

## References

- **Exploration files:** `backend/data/samples/web/`
  - `shell.jsx` — Component library
  - `stage1.jsx` — Migration Assessment
  - `stage2.jsx` — Complexity Analysis
  - `stage3.jsx` — Delivery Timeline
  - `stage4.jsx` — Sprint Tracker
  - `hub.jsx` — Project hub (3 variants)
- **Design tokens:** `src/lib/design-tokens.ts`
- **Component library:** `src/components/rpa/`
- **Global styles:** `src/app/globals.css`
