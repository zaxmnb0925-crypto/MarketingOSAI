"use client";

import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { sessionFetch } from "@/lib/session-fetch";

import type {
  Brand,
  Degradation,
  GovernanceCase,
  GovernanceSnapshot,
  PendingAction,
  Recommendation,
  Remediation,
  Workspace,
} from "./_lib/contracts";

type MeResponse = {
  user: { email: string; full_name: string | null };
  workspaces: Workspace[];
};

type ActionForm = Record<string, string | boolean | number>;

const emptySnapshot: GovernanceSnapshot = {
  recommendation: [],
  active: null,
  effects: [],
  degradations: [],
  remediations: [],
  cases: [],
};

function dateTime(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-TW", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function shortId(value: string) {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function apiError(status: number, detail: unknown) {
  if (status === 409) return `狀態已變更，請重新整理後再操作。${detail ? `（${String(detail)}）` : ""}`;
  if (status === 403) return "你的 Workspace 角色沒有此操作權限。";
  if (status === 404) return "操作目標已不存在，請重新整理。";
  if (status === 422) return "輸入內容不符合治理契約，請檢查所有欄位。";
  return typeof detail === "string" ? detail : "治理操作失敗。";
}

function defaultForm(action: PendingAction): ActionForm {
  const values: ActionForm = { reason: "經人工審查後確認執行" };
  for (const [key, value] of Object.entries(action.defaults || {})) {
    values[key] = value === null ? "" : value;
  }
  return values;
}

export default function GovernancePage() {
  const router = useRouter();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [workspaceId, setWorkspaceId] = useState("");
  const [brands, setBrands] = useState<Brand[]>([]);
  const [brandId, setBrandId] = useState("");
  const [snapshot, setSnapshot] = useState<GovernanceSnapshot>(emptySnapshot);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [action, setAction] = useState<PendingAction | null>(null);
  const [form, setForm] = useState<ActionForm>({});
  const [submitting, setSubmitting] = useState(false);
  const snapshotRequestId = useRef(0);

  const resetGovernanceScope = useCallback(() => {
    snapshotRequestId.current += 1;
    setBrands([]);
    setBrandId("");
    setSnapshot(emptySnapshot);
    setRefreshing(false);
    setMessage("");
    setError("");
    setAction(null);
    setForm({});
    setSubmitting(false);
  }, []);

  const changeWorkspace = (nextWorkspaceId: string) => {
    resetGovernanceScope();
    setWorkspaceId(nextWorkspaceId);
  };

  const workspace = me?.workspaces.find((item) => item.id === workspaceId) || null;
  const brand = brands.find((item) => item.id === brandId) || null;
  const canWrite = Boolean(workspace && workspace.role !== "viewer");

  const apiBase = useMemo(() => {
    if (!workspaceId || !brandId) return "";
    return `/api/workspaces/${workspaceId}/brands/${brandId}/quality-policy`;
  }, [brandId, workspaceId]);

  const governanceFetch = useCallback(async <T,>(path: string): Promise<T> => {
    const response = await sessionFetch(`${apiBase}/${path}`, { cache: "no-store" });
    if (response.status === 401) {
      router.replace("/login?next=/governance");
      throw new Error("登入狀態已失效。");
    }
    const data = await response.json();
    if (!response.ok) throw new Error(apiError(response.status, data?.detail));
    return data as T;
  }, [apiBase, router]);

  const loadSnapshot = useCallback(async () => {
    const requestId = snapshotRequestId.current + 1;
    snapshotRequestId.current = requestId;

    if (!apiBase) {
      setSnapshot(emptySnapshot);
      setRefreshing(false);
      return;
    }

    setRefreshing(true);
    setError("");

    try {
      const [recommendation, active, effects, degradations, remediations, cases] =
        await Promise.all([
          governanceFetch<GovernanceSnapshot["recommendation"]>("recommendations"),
          governanceFetch<GovernanceSnapshot["active"]>("activations/active"),
          governanceFetch<GovernanceSnapshot["effects"]>("effects"),
          governanceFetch<GovernanceSnapshot["degradations"]>("degradation-recommendations"),
          governanceFetch<GovernanceSnapshot["remediations"]>("remediations"),
          governanceFetch<GovernanceSnapshot["cases"]>("governance-cases"),
        ]);

      if (requestId !== snapshotRequestId.current) return;

      setSnapshot({ recommendation, active, effects, degradations, remediations, cases });
    } catch (caught) {
      if (requestId !== snapshotRequestId.current) return;

      setSnapshot(emptySnapshot);
      setError(caught instanceof Error ? caught.message : "治理狀態載入失敗。");
    } finally {
      if (requestId === snapshotRequestId.current) {
        setRefreshing(false);
      }
    }
  }, [apiBase, governanceFetch]);

  useEffect(() => {
    async function boot() {
      try {
        const response = await sessionFetch("/api/auth/me", { cache: "no-store" });
        if (response.status === 401) {
          router.replace("/login?next=/governance");
          return;
        }
        if (!response.ok) throw new Error();
        const data: MeResponse = await response.json();
        setMe(data);
        setWorkspaceId(data.workspaces[0]?.id || "");
      } catch {
        setError("目前無法載入帳號與 Workspace。");
      } finally {
        setLoading(false);
      }
    }
    void boot();
  }, [router]);

  useEffect(() => {
    let cancelled = false;

    resetGovernanceScope();

    if (!workspaceId) {
      return () => {
        cancelled = true;
      };
    }

    async function loadBrands() {
      try {
        const response = await sessionFetch(`/api/workspaces/${workspaceId}/brands`, { cache: "no-store" });

        if (response.status === 401) {
          router.replace("/login?next=/governance");
          return;
        }

        const data = await response.json();

        if (!response.ok) {
          throw new Error(apiError(response.status, data?.detail));
        }

        if (cancelled) return;

        setBrands(data);
        setBrandId(data[0]?.id || "");
      } catch (caught) {
        if (cancelled) return;

        setBrands([]);
        setBrandId("");
        setSnapshot(emptySnapshot);
        setAction(null);
        setForm({});
        setError(caught instanceof Error ? caught.message : "品牌清單載入失敗。");
      }
    }

    void loadBrands();

    return () => {
      cancelled = true;
    };
  }, [resetGovernanceScope, router, workspaceId]);

  useEffect(() => {
    void loadSnapshot();
  }, [loadSnapshot]);

  function openAction(next: PendingAction) {
    setAction(next);
    setForm(defaultForm(next));
    setMessage("");
    setError("");
  }

  function field(name: string, fallback = "") {
    const value = form[name];
    return typeof value === "string" ? value : fallback;
  }

  async function submitAction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!action || !apiBase || !canWrite) return;
    setSubmitting(true);
    setError("");
    setMessage("");

    let path = "";
    let payload: Record<string, unknown> = {};
    const reason = field("reason").trim();

    try {
      if (!reason) throw new Error("請填寫人工操作理由。");
      switch (action.kind) {
        case "recommendation-decision":
          path = `recommendations/${action.subjectId}/decision`;
          payload = { status: field("status"), reason };
          break;
        case "activation":
          path = `recommendations/${action.subjectId}/activate`;
          payload = {
            mode: field("mode"),
            expected_active_activation_id: field("expected_active_activation_id") || null,
            idempotency_key: field("idempotency_key"),
            effective_at: new Date(field("effective_at")).toISOString(),
            expires_at: field("expires_at") ? new Date(field("expires_at")).toISOString() : null,
            reason,
          };
          break;
        case "activation-rollback":
          path = `activations/${action.subjectId}/rollback`;
          payload = {
            target_activation_id: field("target_activation_id"),
            expected_active_activation_id: field("expected_active_activation_id"),
            idempotency_key: field("idempotency_key"),
            effective_at: new Date(field("effective_at")).toISOString(),
            expires_at: field("expires_at") ? new Date(field("expires_at")).toISOString() : null,
            reason,
          };
          break;
        case "degradation-review":
          path = `degradation-recommendations/${action.subjectId}/review`;
          payload = { status: field("status"), reason };
          break;
        case "remediation-proposal":
          path = "remediations";
          payload = {
            degradation_recommendation_id: action.subjectId,
            source_activation_id: field("source_activation_id"),
            target_activation_id: field("target_activation_id"),
            expected_policy_version: Number(field("expected_policy_version")),
            idempotency_key: field("idempotency_key"),
            observation_window_count: Number(field("observation_window_count")),
            recovery_threshold: Number(field("recovery_threshold")),
            reason,
          };
          break;
        case "remediation-decision":
          path = `remediations/${action.subjectId}/decision`;
          payload = { approve: form.approve === true, reason };
          break;
        case "remediation-execution":
          path = `remediations/${action.subjectId}/execution-confirmation`;
          payload = { result_activation_id: field("result_activation_id"), reason };
          break;
        case "remediation-closure":
          path = `remediations/${action.subjectId}/closure`;
          payload = {
            observed_window_count: Number(field("observed_window_count")),
            observed_quality_score: Number(field("observed_quality_score")),
            human_confirms_recovery: form.human_confirms_recovery === true,
            reason,
          };
          break;
        case "case-open":
          path = "governance-cases";
          payload = {
            remediation_id: action.subjectId,
            expected_policy_version: Number(field("expected_policy_version")),
            idempotency_key: field("idempotency_key"),
            reason,
          };
          break;
        case "case-closure":
          path = `governance-cases/${action.subjectId}/closure`;
          payload = {
            decision: field("decision"),
            expected_manifest_sha256: field("expected_manifest_sha256"),
            human_confirms_closure: form.human_confirms_closure === true,
            reason,
          };
          break;
      }

      const response = await sessionFetch(`${apiBase}/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(apiError(response.status, data?.detail));
      setAction(null);
      setMessage(`${action.title}已完成，治理狀態已重新整理。`);
      await loadSnapshot();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "治理操作失敗。");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <main className="governance-loading">正在載入治理工作台…</main>;
  if (!me) return <main className="governance-loading">{error || "無法載入治理工作台。"}</main>;

  const pendingCount =
    snapshot.recommendation.filter((item) => item.status === "candidate").length +
    snapshot.degradations.filter((item) => item.status === "pending_review").length +
    snapshot.remediations.filter((item) => ["proposed", "approved", "observation"].includes(item.status)).length +
    snapshot.cases.filter((item) => item.status === "open").length;

  return (
    <main className="governance-shell">
      <aside className="sidebar">
        <div>
          <div className="sidebar-brand"><span className="brand-mark small">M</span><strong>MarketingOS</strong></div>
          <nav className="sidebar-nav">
            <a className="nav-item" href="/dashboard">總覽</a>
            <a className="nav-item" href="/brands">品牌管理</a>
            <a className="nav-item" href="/create">AI 創作</a>
            <a className="nav-item" href="/history">內容歷史</a>
            <a className="nav-item active" href="/governance">品質治理</a>
          </nav>
        </div>
        <a className="logout-button governance-back" href="/dashboard">返回 Dashboard</a>
      </aside>

      <section className="governance-main">
        <header className="governance-header">
          <div>
            <div className="eyebrow">P5 · HUMAN GOVERNANCE</div>
            <h1>AI 品質治理工作台</h1>
            <p>所有政策變更、修復與結案都需要人工確認，系統不會自動執行。</p>
          </div>
          <button className="secondary-button" disabled={refreshing || !brandId} onClick={() => void loadSnapshot()}>
            {refreshing ? "重新整理中…" : "重新整理"}
          </button>
        </header>

        <section className="governance-scope" aria-label="治理範圍">
          <label>Workspace
            <select value={workspaceId} onChange={(event) => changeWorkspace(event.target.value)}>
              {me.workspaces.map((item) => <option value={item.id} key={item.id}>{item.name} · {item.role}</option>)}
            </select>
          </label>
          <label>品牌
            <select value={brandId} onChange={(event) => setBrandId(event.target.value)}>
              {brands.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
            </select>
          </label>
          <div className={`governance-permission ${canWrite ? "write" : "read"}`}>
            {canWrite ? "可執行人工治理操作" : "唯讀權限"}
          </div>
        </section>

        {message ? <div className="governance-notice success" role="status">{message}</div> : null}
        {error ? <div className="governance-notice error" role="alert">{error}</div> : null}
        {!brandId ? <div className="governance-notice">此 Workspace 尚未建立品牌。</div> : null}

        <section className="governance-metrics">
          <article><span>待人工處理</span><strong>{pendingCount}</strong></article>
          <article><span>目前政策</span><strong>{snapshot.active ? `v${snapshot.active.policy_version}` : "未啟用"}</strong></article>
          <article><span>觀察狀態</span><strong>{snapshot.effects[0]?.state || "尚無資料"}</strong></article>
          <article><span>治理案件</span><strong>{snapshot.cases.length}</strong></article>
        </section>

        <section className="governance-grid">
          <GovernanceSection title="政策建議" eyebrow="RECOMMENDATIONS" empty="目前沒有政策建議。">
            {snapshot.recommendation.map((item) => (
              <RecommendationCard key={item.id} item={item} active={snapshot.active} canWrite={canWrite} openAction={openAction} />
            ))}
          </GovernanceSection>

          <GovernanceSection title="效果觀察與降級" eyebrow="OBSERVATION" empty="目前沒有觀察資料。">
            {snapshot.effects.map((item) => (
              <article className="governance-row" key={item.id}>
                <div><Status value={item.state} /><strong>品質差異 {item.quality_delta}</strong><small>{dateTime(item.window_started_at)} → {dateTime(item.window_ended_at)}</small></div>
                <dl><div><dt>基準</dt><dd>{item.baseline_quality_score}</dd></div><div><dt>觀察</dt><dd>{item.observed_quality_score}</dd></div><div><dt>信心</dt><dd>{item.confidence_score}%</dd></div></dl>
              </article>
            ))}
            {snapshot.degradations.map((item) => (
              <DegradationCard key={item.id} item={item} active={snapshot.active} canWrite={canWrite} openAction={openAction} />
            ))}
          </GovernanceSection>

          <GovernanceSection title="人工修復" eyebrow="REMEDIATION" empty="目前沒有修復流程。">
            {snapshot.remediations.map((item) => (
              <RemediationCard key={item.id} item={item} active={snapshot.active} canWrite={canWrite} openAction={openAction} />
            ))}
          </GovernanceSection>

          <GovernanceSection title="治理證據與結案" eyebrow="EVIDENCE" empty="目前沒有治理案件。">
            {snapshot.cases.map((item) => (
              <CaseCard key={item.id} item={item} canWrite={canWrite} openAction={openAction} />
            ))}
          </GovernanceSection>
        </section>
      </section>

      {action ? (
        <ActionDialog action={action} form={form} setForm={setForm} submitting={submitting} close={() => setAction(null)} submit={submitAction} />
      ) : null}
    </main>
  );
}

function GovernanceSection({ title, eyebrow, empty, children }: { title: string; eyebrow: string; empty: string; children: ReactNode }) {
  const items = Array.isArray(children) ? children.flat().filter(Boolean) : children;
  return <section className="governance-panel"><header><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2></div></header><div className="governance-list">{Array.isArray(items) && items.length === 0 ? <p className="governance-empty">{empty}</p> : items}</div></section>;
}

function Status({ value }: { value: string }) { return <span className={`governance-status status-${value}`}>{value}</span>; }

function RecommendationCard({ item, active, canWrite, openAction }: { item: Recommendation; active: GovernanceSnapshot["active"]; canWrite: boolean; openAction: (action: PendingAction) => void }) {
  return <article className="governance-row"><div><Status value={item.status} /><strong>政策建議 v{item.version}</strong><small>{item.recommendation_reason} · 信心 {item.confidence_score}%</small></div><dl><div><dt>最低品質</dt><dd>{item.minimum_quality_score}</dd></div><div><dt>最小樣本</dt><dd>{item.minimum_cohort_size}</dd></div><div><dt>建立時間</dt><dd>{dateTime(item.created_at)}</dd></div></dl>{canWrite && item.status === "candidate" ? <div className="governance-actions"><button onClick={() => openAction({ kind: "recommendation-decision", title: "審核政策建議", subjectId: item.id, subjectLabel: `政策 v${item.version}`, defaults: { status: "approved" } })}>人工審核</button></div> : null}{canWrite && item.status === "approved" && !item.activation_performed ? <div className="governance-actions"><button onClick={() => openAction({ kind: "activation", title: "啟用已批准政策", subjectId: item.id, subjectLabel: `政策 v${item.version}`, defaults: { mode: "shadow", expected_active_activation_id: active?.id || "", idempotency_key: crypto.randomUUID(), effective_at: new Date().toISOString().slice(0, 16), expires_at: "" } })}>人工啟用</button></div> : null}</article>;
}

function DegradationCard({ item, active, canWrite, openAction }: { item: Degradation; active: GovernanceSnapshot["active"]; canWrite: boolean; openAction: (action: PendingAction) => void }) {
  return <article className="governance-row warning"><div><Status value={item.status} /><strong>降級建議：{item.action}</strong><small>{item.reason} · 信心 {item.confidence_score}%</small></div>{canWrite && item.status === "pending_review" ? <div className="governance-actions"><button onClick={() => openAction({ kind: "degradation-review", title: "審查降級建議", subjectId: item.id, subjectLabel: shortId(item.id), defaults: { status: "accepted" } })}>人工審查</button>{item.action === "rollback" && active ? <button onClick={() => openAction({ kind: "remediation-proposal", title: "提出人工修復", subjectId: item.id, subjectLabel: shortId(item.id), defaults: { source_activation_id: active.id, target_activation_id: "", expected_policy_version: active.policy_version, idempotency_key: crypto.randomUUID(), observation_window_count: 3, recovery_threshold: active.minimum_quality_score } })}>建立修復提案</button> : null}</div> : null}</article>;
}

function RemediationCard({ item, active, canWrite, openAction }: { item: Remediation; active: GovernanceSnapshot["active"]; canWrite: boolean; openAction: (action: PendingAction) => void }) {
  return <article className="governance-row"><div><Status value={item.status} /><strong>修復 {shortId(item.id)}</strong><small>政策 v{item.expected_policy_version} · 觀察 {item.observation_window_count} 個視窗 · 門檻 {item.recovery_threshold}</small></div><dl><div><dt>來源</dt><dd title={item.source_activation_id}>{shortId(item.source_activation_id)}</dd></div><div><dt>目標</dt><dd title={item.target_activation_id}>{shortId(item.target_activation_id)}</dd></div></dl>{canWrite ? <div className="governance-actions">{item.status === "proposed" ? <button onClick={() => openAction({ kind: "remediation-decision", title: "審核修復提案", subjectId: item.id, subjectLabel: shortId(item.id), defaults: { approve: true } })}>人工批准／拒絕</button> : null}{item.status === "approved" && active?.id === item.source_activation_id ? <button onClick={() => openAction({ kind: "activation-rollback", title: "執行受控政策回復", subjectId: active.id, subjectLabel: `修復 ${shortId(item.id)}`, defaults: { target_activation_id: item.target_activation_id, expected_active_activation_id: active.id, idempotency_key: crypto.randomUUID(), effective_at: new Date().toISOString().slice(0, 16), expires_at: "" } })}>執行受控回復</button> : null}{item.status === "approved" ? <button onClick={() => openAction({ kind: "remediation-execution", title: "確認修復執行結果", subjectId: item.id, subjectLabel: shortId(item.id), defaults: { result_activation_id: active?.id || "" } })}>確認執行結果</button> : null}{item.status === "observation" ? <button onClick={() => openAction({ kind: "remediation-closure", title: "確認修復恢復", subjectId: item.id, subjectLabel: shortId(item.id), defaults: { observed_window_count: item.observation_window_count, observed_quality_score: item.recovery_threshold, human_confirms_recovery: false } })}>人工確認恢復</button> : null}{item.status === "recovered" ? <button onClick={() => openAction({ kind: "case-open", title: "建立治理證據案件", subjectId: item.id, subjectLabel: shortId(item.id), defaults: { expected_policy_version: item.expected_policy_version, idempotency_key: crypto.randomUUID() } })}>建立治理案件</button> : null}</div> : null}</article>;
}

function CaseCard({ item, canWrite, openAction }: { item: GovernanceCase; canWrite: boolean; openAction: (action: PendingAction) => void }) {
  return <article className="governance-row"><div><Status value={item.status} /><strong>治理案件 {shortId(item.id)}</strong><small>證據 {item.evidence_item_count} 筆 · manifest {shortId(item.evidence_manifest_sha256)}</small></div><dl><div><dt>政策版本</dt><dd>v{item.policy_version}</dd></div><div><dt>建立時間</dt><dd>{dateTime(item.created_at)}</dd></div><div><dt>結案時間</dt><dd>{dateTime(item.closed_at)}</dd></div></dl>{canWrite && item.status === "open" ? <div className="governance-actions"><button onClick={() => openAction({ kind: "case-closure", title: "人工結案", subjectId: item.id, subjectLabel: shortId(item.id), defaults: { decision: "close", expected_manifest_sha256: item.evidence_manifest_sha256, human_confirms_closure: false } })}>審查並結案</button></div> : null}</article>;
}

function ActionDialog({ action, form, setForm, submitting, close, submit }: { action: PendingAction; form: ActionForm; setForm: (value: ActionForm) => void; submitting: boolean; close: () => void; submit: (event: FormEvent<HTMLFormElement>) => void }) {
  const update = (name: string, value: string | boolean) => setForm({ ...form, [name]: value });
  const textField = (name: string, label: string, type = "text") => <label>{label}<input name={name} type={type} value={String(form[name] ?? "")} onChange={(event) => update(name, event.target.value)} required /></label>;
  return <div className="governance-dialog-backdrop" role="presentation"><section className="governance-dialog" role="dialog" aria-modal="true" aria-labelledby="governance-action-title"><header><div><div className="eyebrow">EXPLICIT HUMAN ACTION</div><h2 id="governance-action-title">{action.title}</h2><p>{action.subjectLabel}</p></div><button aria-label="關閉" className="dialog-close" onClick={close}>×</button></header><form onSubmit={submit}><div className="governance-form-grid">{action.kind === "recommendation-decision" ? <label>決定<select value={String(form.status)} onChange={(event) => update("status", event.target.value)}><option value="approved">批准</option><option value="rejected">拒絕</option></select></label> : null}{action.kind === "activation" ? <>{<label>模式<select value={String(form.mode)} onChange={(event) => update("mode", event.target.value)}><option value="shadow">Shadow</option><option value="enforced">Enforced</option></select></label>}{textField("expected_active_activation_id", "目前 Activation ID（首次可留空）")}{textField("idempotency_key", "Idempotency key")}{textField("effective_at", "生效時間", "datetime-local")}{textField("expires_at", "到期時間（選填）", "datetime-local")}</> : null}{action.kind === "activation-rollback" ? <>{textField("target_activation_id", "回復目標 Activation ID")}{textField("expected_active_activation_id", "目前 Active Activation ID")}{textField("idempotency_key", "Idempotency key")}{textField("effective_at", "生效時間", "datetime-local")}{textField("expires_at", "到期時間（選填）", "datetime-local")}</> : null}{action.kind === "degradation-review" ? <label>決定<select value={String(form.status)} onChange={(event) => update("status", event.target.value)}><option value="accepted">接受</option><option value="dismissed">駁回</option></select></label> : null}{action.kind === "remediation-proposal" ? <>{textField("source_activation_id", "來源 Activation ID")}{textField("target_activation_id", "回復目標 Activation ID")}{textField("expected_policy_version", "預期政策版本", "number")}{textField("idempotency_key", "Idempotency key")}{textField("observation_window_count", "觀察視窗數", "number")}{textField("recovery_threshold", "恢復品質門檻", "number")}</> : null}{action.kind === "remediation-decision" ? <label className="governance-check"><input type="checkbox" checked={form.approve === true} onChange={(event) => update("approve", event.target.checked)} />批准此人工修復提案（取消勾選代表拒絕）</label> : null}{action.kind === "remediation-execution" ? textField("result_activation_id", "實際結果 Activation ID") : null}{action.kind === "remediation-closure" ? <>{textField("observed_window_count", "已觀察視窗數", "number")}{textField("observed_quality_score", "觀察品質分數", "number")}<label className="governance-check"><input type="checkbox" checked={form.human_confirms_recovery === true} onChange={(event) => update("human_confirms_recovery", event.target.checked)} required />我已人工確認品質恢復</label></> : null}{action.kind === "case-open" ? <>{textField("expected_policy_version", "預期政策版本", "number")}{textField("idempotency_key", "Idempotency key")}</> : null}{action.kind === "case-closure" ? <><label>結案決定<select value={String(form.decision)} onChange={(event) => update("decision", event.target.value)}><option value="close">結案</option><option value="reject">拒絕結案</option><option value="void">作廢</option></select></label>{textField("expected_manifest_sha256", "預期 Evidence Manifest SHA-256")}<label className="governance-check"><input type="checkbox" checked={form.human_confirms_closure === true} onChange={(event) => update("human_confirms_closure", event.target.checked)} required />我已人工核對證據並確認結案</label></> : null}<label className="full">人工操作理由<textarea value={String(form.reason ?? "")} onChange={(event) => update("reason", event.target.value)} minLength={1} maxLength={300} required /></label></div><div className="dialog-actions"><button type="button" onClick={close} disabled={submitting}>取消</button><button className="danger-confirm" type="submit" disabled={submitting}>{submitting ? "送出中…" : "確認人工操作"}</button></div></form></section></div>;
}
