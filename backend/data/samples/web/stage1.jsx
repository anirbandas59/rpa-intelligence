/* ─────────────────────────────────────────────────────────────
   stage1.jsx — Migration Assessment, three directions
   Exports: S1Scorecard, S1Dimensions, S1Portfolio
   ───────────────────────────────────────────────────────────── */

const S1_DIMS = [
  { key: "technical_feasibility", label: "Technical feasibility", max: 40, color: "var(--c-blue)" },
  { key: "migration_effort",      label: "Migration effort",      max: 25, color: "var(--c-teal)" },
  { key: "platform_suitability",  label: "Platform suitability",  max: 20, color: "var(--primary)" },
  { key: "risk",                  label: "Risk (inverse)",        max: 15, color: "var(--c-amber)" },
];

const CONF_COLOR = { HIGH: "var(--c-green)", MEDIUM: "var(--c-amber)", LOW: "var(--c-red)" };

function FieldRow({ label, value, source, mono }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "9px 0", borderBottom: "1px solid var(--border)" }}>
      <span style={{ fontSize: 12.5, color: "var(--muted-fg)" }}>{label}</span>
      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 12.5, fontWeight: 500, fontFamily: mono ? "var(--mono)" : "inherit" }}>{value}</span>
        {source && <SourceBadge source={source} />}
      </span>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// A · Scorecard
// ══════════════════════════════════════════════════════════════
function S1Scorecard() {
  const uc = window.RPA_USECASES[0];
  const v = uc.s1;
  return (
    <AppShell activeStage="s1" useCase={uc}
      action={<><Pill color="var(--c-green)" style={{ height: 30 }}><Icon name="check" size={12} /> Complete · run #2</Pill>
        <Btn variant="subtle" size="sm" icon="history">Runs</Btn>
        <Btn size="sm" icon="play">Re-run</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "24px 28px", display: "grid", gridTemplateColumns: "340px 1fr", gap: 22 }}>
        {/* left: gauge + decision */}
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <Card style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, paddingTop: 26, paddingBottom: 22 }}>
            <Gauge value={v.score} band={v.band} size={170} />
            <PriorityBadge band={v.band} solid />
            <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12 }}>
              <span style={{ color: "var(--muted-fg)" }}>Confidence</span>
              <Pill color={CONF_COLOR[v.confidence]}>{v.confidence}</Pill>
            </div>
          </Card>
          <Card>
            <SectionLabel style={{ marginBottom: 6 }}>Inputs</SectionLabel>
            <FieldRow label="Use case" value={uc.name} source="manual" />
            <FieldRow label="Source platform" value={uc.platform} source="imported" />
            <FieldRow label="Install type" value={uc.install} source="manual" />
            <div style={{ paddingTop: 10 }}>
              <Btn variant="outline" size="sm" icon="link" style={{ width: "100%" }}>Backfill from Stage 2 (Sonnet)</Btn>
            </div>
          </Card>
        </div>

        {/* right: dimensions + analysis */}
        <div style={{ display: "flex", flexDirection: "column", gap: 18, minHeight: 0 }}>
          <Card>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
              <SectionLabel>Scoring dimensions</SectionLabel>
              <span style={{ fontSize: 11, color: "var(--muted-fg)", fontFamily: "var(--mono)" }}>weighted · Haiku 4.5</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "18px 28px" }}>
              {S1_DIMS.map((d) => <DimBar key={d.key} label={d.label} value={v.dims[d.key]} max={d.max} color={d.color} />)}
            </div>
          </Card>

          <Card style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <SectionLabel>AI analysis</SectionLabel>
              <Pill color="var(--primary)"><Icon name="spark" size={11} /> Generated</Pill>
            </div>
            <p style={{ fontSize: 13, lineHeight: 1.62, color: "var(--fg-2)", margin: 0 }}>{v.analysis}</p>
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11.5, fontWeight: 600, color: "var(--c-amber)", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                <Icon name="flag" size={13} /> Blockers ({v.blockers.length})
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {v.blockers.map((b) => (
                  <div key={b} style={{ display: "flex", gap: 9, alignItems: "flex-start", fontSize: 12.5, color: "var(--fg-2)",
                    padding: "9px 12px", borderRadius: 9, background: "color-mix(in oklab, var(--c-amber) 8%, transparent)",
                    border: "1px solid color-mix(in oklab, var(--c-amber) 20%, transparent)" }}>
                    <span style={{ width: 5, height: 5, borderRadius: 99, background: "var(--c-amber)", marginTop: 6, flexShrink: 0 }} />{b}
                  </div>
                ))}
              </div>
            </div>
            <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--muted-fg)" }}>Power Automate fit</div>
                <div style={{ fontSize: 12.5, color: "var(--fg-2)", marginTop: 2 }}>{v.fit}</div>
              </div>
              <Btn variant="ghost" size="sm" icon="edit">Override decision</Btn>
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

// ══════════════════════════════════════════════════════════════
// B · Dimension breakdown + override panel
// ══════════════════════════════════════════════════════════════
function RadialDim({ label, value, max, color, size = 92 }) {
  const r = (size - 9) / 2, C = 2 * Math.PI * r, pct = value / max;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      <div style={{ position: "relative", width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--track)" strokeWidth={9} />
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={9} strokeLinecap="round"
            strokeDasharray={`${C * pct} ${C}`} style={{ filter: `drop-shadow(0 0 5px color-mix(in oklab, ${color} 55%, transparent))` }} />
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
          <span style={{ fontFamily: "var(--mono)", fontSize: 19, fontWeight: 700 }}>{value}</span>
          <span style={{ fontSize: 9.5, color: "var(--muted-fg)" }}>/ {max}</span>
        </div>
      </div>
      <span style={{ fontSize: 11.5, color: "var(--fg-2)", textAlign: "center", maxWidth: 110 }}>{label}</span>
    </div>
  );
}

function S1Dimensions() {
  const uc = window.RPA_USECASES[0];
  const v = uc.s1;
  return (
    <AppShell activeStage="s1" useCase={uc}
      action={<><Btn variant="subtle" size="sm" icon="history">Run #2 · history</Btn><Btn size="sm" icon="play">Re-run</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "24px 28px", display: "flex", flexDirection: "column", gap: 18 }}>
        {/* hero strip */}
        <Card pad={22} style={{ display: "flex", alignItems: "center", gap: 30, background: "linear-gradient(100deg, color-mix(in oklab, var(--primary) 10%, var(--surface)), var(--surface) 70%)" }}>
          <div>
            <div style={{ fontSize: 11.5, color: "var(--muted-fg)", marginBottom: 4 }}>Migration score</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
              <span style={{ fontFamily: "var(--mono)", fontSize: 58, fontWeight: 700, lineHeight: 1, color: window.RPA_BANDS[v.band].color }}>{v.score}</span>
              <span style={{ fontSize: 16, color: "var(--muted-fg)" }}>/ 100</span>
            </div>
          </div>
          <div style={{ height: 56, width: 1, background: "var(--border)" }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            <PriorityBadge band={v.band} solid />
            <div style={{ fontSize: 12, color: "var(--muted-fg)" }}>Band {window.RPA_BANDS[v.band].range} · <span style={{ color: CONF_COLOR[v.confidence] }}>{v.confidence}</span> confidence</div>
          </div>
          <div style={{ flex: 1 }} />
          {/* stacked contribution bar */}
          <div style={{ width: 280 }}>
            <div style={{ fontSize: 10.5, color: "var(--muted-fg)", marginBottom: 7 }}>CONTRIBUTION TO SCORE</div>
            <div style={{ display: "flex", height: 14, borderRadius: 99, overflow: "hidden", gap: 2 }}>
              {S1_DIMS.map((d) => (
                <div key={d.key} title={`${d.label}: ${v.dims[d.key]}`} style={{ width: `${(v.dims[d.key] / v.score) * 100}%`, background: d.color }} />
              ))}
            </div>
            <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
              {S1_DIMS.map((d) => (
                <span key={d.key} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 10.5, color: "var(--muted-fg)" }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: d.color }} />{d.label.split(" ")[0]}
                </span>
              ))}
            </div>
          </div>
        </Card>

        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 18, flex: 1, minHeight: 0 }}>
          <Card style={{ display: "flex", flexDirection: "column" }}>
            <SectionLabel style={{ marginBottom: 18 }}>Dimension breakdown</SectionLabel>
            <div style={{ display: "flex", justifyContent: "space-around" }}>
              {S1_DIMS.map((d) => <RadialDim key={d.key} label={d.label} value={v.dims[d.key]} max={d.max} color={d.color} />)}
            </div>
            <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)", flex: 1 }}>
              <SectionLabel style={{ marginBottom: 8 }}>AI analysis</SectionLabel>
              <p style={{ fontSize: 12.5, lineHeight: 1.6, color: "var(--fg-2)", margin: 0 }}>{v.analysis}</p>
            </div>
          </Card>

          {/* override panel */}
          <Card style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <SectionLabel>Manual override</SectionLabel>
              <Icon name="edit" size={14} style={{ color: "var(--muted-fg)" }} />
            </div>
            <p style={{ fontSize: 11.5, color: "var(--muted-fg)", margin: "0 0 14px", lineHeight: 1.5 }}>
              Adjust any dimension or set the decision directly. Overrides are tracked as a new run with a required reason.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
              {S1_DIMS.map((d) => (
                <div key={d.key}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, marginBottom: 5 }}>
                    <span style={{ color: "var(--fg-2)" }}>{d.label}</span>
                    <span style={{ fontFamily: "var(--mono)", color: "var(--fg)" }}>{v.dims[d.key]}</span>
                  </div>
                  <div style={{ position: "relative", height: 6, borderRadius: 99, background: "var(--track)" }}>
                    <div style={{ width: `${(v.dims[d.key] / d.max) * 100}%`, height: "100%", borderRadius: 99, background: d.color }} />
                    <div style={{ position: "absolute", left: `${(v.dims[d.key] / d.max) * 100}%`, top: "50%", transform: "translate(-50%,-50%)",
                      width: 14, height: 14, borderRadius: 99, background: "var(--fg)", border: `3px solid ${d.color}`, cursor: "grab" }} />
                  </div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11.5, color: "var(--fg-2)", marginBottom: 6 }}>Decision</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {Object.keys(window.RPA_BANDS).map((b) => (
                  <span key={b} style={{ opacity: b === v.band ? 1 : 0.45, cursor: "pointer" }}><PriorityBadge band={b} solid={b === v.band} /></span>
                ))}
              </div>
            </div>
            <div style={{ flex: 1 }} />
            <div style={{ marginTop: 14, display: "flex", gap: 8 }}>
              <Btn variant="outline" size="sm" style={{ flex: 1 }}>Reset to AI</Btn>
              <Btn size="sm" icon="check" style={{ flex: 1 }}>Save override</Btn>
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

// ══════════════════════════════════════════════════════════════
// C · Portfolio parallel scoring (bulk Haiku)
// ══════════════════════════════════════════════════════════════
function S1Portfolio() {
  const uc = window.RPA_USECASES[0];
  const scored = window.RPA_USECASES;
  return (
    <AppShell activeStage="s1" useCase={uc} breadcrumb={["RPA Migration Project", "Stage 1 · Batch scoring"]}
      action={<><Btn variant="subtle" size="sm" icon="upload">Import Excel</Btn><Btn size="sm" icon="zap">Score all (Haiku)</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "24px 28px", display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h2 style={{ fontSize: 19, fontWeight: 700, margin: 0 }}>Parallel assessment</h2>
            <p style={{ fontSize: 12.5, color: "var(--muted-fg)", margin: "4px 0 0" }}>Haiku scores every use case concurrently across the four dimensions.</p>
          </div>
          <Card pad={0} style={{ display: "flex", alignItems: "center" }}>
            {[["4", "complete", "var(--c-green)"], ["1", "scoring", "var(--primary)"], ["1", "queued", "var(--muted-fg)"]].map(([n, l, c], i) => (
              <div key={l} style={{ padding: "10px 18px", borderLeft: i ? "1px solid var(--border)" : "none", textAlign: "center" }}>
                <div style={{ fontFamily: "var(--mono)", fontSize: 20, fontWeight: 700, color: c }}>{n}</div>
                <div style={{ fontSize: 10.5, color: "var(--muted-fg)" }}>{l}</div>
              </div>
            ))}
          </Card>
        </div>

        <Card pad={0} style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: "2.1fr repeat(4, 1fr) 1fr 1.1fr", padding: "11px 18px", fontSize: 10,
            fontWeight: 700, letterSpacing: 0.5, color: "var(--muted-fg)", textTransform: "uppercase", borderBottom: "1px solid var(--border)" }}>
            <span>Use case</span>
            {S1_DIMS.map((d) => <span key={d.key} style={{ textAlign: "center" }}>{d.label.split(" ")[0].slice(0, 5)}</span>)}
            <span style={{ textAlign: "center" }}>Score</span>
            <span style={{ textAlign: "right" }}>Decision</span>
          </div>
          {scored.map((u, idx) => {
            const v = u.s1;
            const running = u.readiness.s1 === "running";
            return (
              <div key={u.id} className="rpa-card-hover" style={{ display: "grid", gridTemplateColumns: "2.1fr repeat(4, 1fr) 1fr 1.1fr",
                padding: "13px 18px", alignItems: "center", borderBottom: idx < scored.length - 1 ? "1px solid var(--border)" : "none",
                background: idx === 0 ? "color-mix(in oklab, var(--primary) 6%, transparent)" : "transparent" }}>
                <div style={{ minWidth: 0, paddingRight: 10 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{u.name}</div>
                  <div style={{ fontSize: 10.5, color: "var(--muted-fg)" }}>{u.platform}</div>
                </div>
                {running ? (
                  <div style={{ gridColumn: "2 / 7", display: "flex", alignItems: "center", gap: 10, color: "var(--primary)", fontSize: 12 }}>
                    <StatusDot status="running" size={8} /> Scoring across 4 dimensions…
                    <div style={{ flex: 1, height: 4, borderRadius: 99, background: "var(--track)", overflow: "hidden", maxWidth: 240 }}>
                      <div style={{ width: "62%", height: "100%", background: "var(--primary)" }} />
                    </div>
                  </div>
                ) : v ? (
                  <>
                    {S1_DIMS.map((d) => (
                      <div key={d.key} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                        <span style={{ fontFamily: "var(--mono)", fontSize: 11.5, color: "var(--fg-2)" }}>{v.dims[d.key]}</span>
                        <div style={{ width: 34, height: 4, borderRadius: 99, background: "var(--track)", overflow: "hidden" }}>
                          <div style={{ width: `${(v.dims[d.key] / d.max) * 100}%`, height: "100%", background: d.color }} />
                        </div>
                      </div>
                    ))}
                    <div style={{ textAlign: "center", fontFamily: "var(--mono)", fontSize: 16, fontWeight: 700, color: window.RPA_BANDS[v.band].color }}>{v.score}</div>
                  </>
                ) : (
                  <div style={{ gridColumn: "2 / 7", fontSize: 12, color: "var(--muted-fg)" }}>Queued — awaiting score</div>
                )}
                <div style={{ textAlign: "right", display: "flex", justifyContent: "flex-end" }}>
                  {v ? <PriorityBadge band={v.band} /> : <span style={{ fontSize: 11, color: "var(--muted-fg)" }}>—</span>}
                </div>
              </div>
            );
          })}
        </Card>

        {/* follow-up callout */}
        <Card style={{ display: "flex", alignItems: "center", gap: 14, background: "color-mix(in oklab, var(--primary) 7%, var(--surface))" }}>
          <span style={{ width: 36, height: 36, borderRadius: 10, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
            background: "color-mix(in oklab, var(--primary) 16%, transparent)", color: "var(--primary)" }}><Icon name="spark" size={18} /></span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12.5, fontWeight: 600 }}>3 follow-up questions generated for low-confidence cases</div>
            <div style={{ fontSize: 11.5, color: "var(--muted-fg)" }}>Insurance Claims Triage (LOW) &amp; Employee Onboarding (MEDIUM) — a second Haiku pass flagged gaps to resolve.</div>
          </div>
          <Btn variant="subtle" size="sm" iconR="arrowR">Review questions</Btn>
        </Card>
      </div>
    </AppShell>
  );
}

Object.assign(window, { S1Scorecard, S1Dimensions, S1Portfolio });
