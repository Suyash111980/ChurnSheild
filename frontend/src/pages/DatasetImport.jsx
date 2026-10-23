import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import { deleteDataset, previewDataset, reprocessDataset, retryDataset, uploadDataset } from "../services/datasetService";
import { submitDatasetRevision } from "../services/datasetServiceCore.js";
import { useDataset } from "../context/DatasetContext";
import { useAuth } from "../context/AuthContext";

export default function DatasetImport({ mode = "default" }) {
  const { datasets, datasetId, selectDataset, refresh, loading: datasetsLoading, error: datasetsError } = useDataset();
  const { accountProfile } = useAuth();
  const [file, setFile] = useState(null);
  const [name, setName] = useState(mode === "oulad" ? "OULAD prepared cohort" : "");
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [deleteState, setDeleteState] = useState({ busyId: null, message: "", error: "" });
  const busyRef = useRef(false);
  const isOulad = mode === "oulad";
  const canUpload = ["admin", "master_admin"].includes(accountProfile?.app_role);
  const previewCanProcess = Boolean(preview?.validation?.descriptive_compatible) && !preview?.validation?.errors?.length;
  const predictionReady = Boolean(preview?.validation?.prediction_compatible);
  function makeFormData() {
    const body = new FormData();
    body.append("file", file);
    return body;
  }
  async function inspect() {
    if (!file || busyRef.current) return;
    busyRef.current = true;
    setBusy(true); setError(""); setResult(null);
    try { setPreview(await previewDataset(makeFormData())); }
    catch (reason) { setError(reason.message); setPreview(null); }
    finally { busyRef.current = false; setBusy(false); }
  }
  async function process() {
    if (!file || !preview || preview.validation?.errors?.length || busyRef.current) return;
    busyRef.current = true;
    setBusy(true); setError("");
    try {
      const body = makeFormData(); body.append("dataset_name", name);
      const uploaded = await uploadDataset(body);
      setResult(uploaded);
      if (uploaded.data?.id) selectDataset(uploaded.data.id);
      await refresh(uploaded.data?.id);
    }
    catch (reason) { setError(reason.message); }
    finally { busyRef.current = false; setBusy(false); }
  }
  async function retryOrReprocess() {
    if (!file || !result?.data?.id || busyRef.current) return;
    busyRef.current = true;
    setBusy(true); setError("");
    try {
      await submitDatasetRevision({
        datasetId: result.data.id,
        status: result.data.status,
        file,
        retryDataset,
        reprocessDataset,
        refresh,
        onResponse: setResult,
        onRefreshError: (reason) => setError(reason.message),
      });
    }
    catch (reason) { setError(reason.message); }
    finally { busyRef.current = false; setBusy(false); }
  }
  async function processExisting(item) {
    if (!file || !preview || preview.validation?.errors?.length || busyRef.current) return;
    if (!window.confirm(`Reprocess “${item.dataset_name}” with ${file.name}? If learner-course keys are unchanged, existing learner IDs are reused. Changed membership is saved as a new dataset so prior results remain available.`)) return;
    busyRef.current = true;
    setBusy(true); setError("");
    try {
      const revised = await submitDatasetRevision({
        datasetId: item.id,
        status: item.status,
        file,
        retryDataset,
        reprocessDataset,
        refresh,
        onResponse: setResult,
        onRefreshError: (reason) => setError(reason.message),
      });
      selectDataset(revised?.data?.id || item.id);
    } catch (reason) { setError(reason.message); }
    finally { busyRef.current = false; setBusy(false); }
  }
  async function removeDataset(item) {
    if (!window.confirm(`Delete dataset “${item.dataset_name}”? Its saved learner records, predictions, explanations, and recommendations will be permanently removed together.`)) return;
    setDeleteState({ busyId: item.id, message: "", error: "" });
    try {
      await deleteDataset(item.id);
      await refresh(datasetId === item.id ? undefined : datasetId);
      setDeleteState({ busyId: null, message: `Dataset “${item.dataset_name}” and its dependent records were deleted.`, error: "" });
    } catch (reason) {
      setDeleteState({ busyId: null, message: "", error: reason.message || "Dataset could not be deleted." });
    }
  }
  if (!canUpload) return <section className="panel"><h1>Administrator access required</h1><p>Dataset uploads are restricted to administrators.</p></section>;
  return <>
    <PageHeader eyebrow={isOulad ? "PLATFORM DATA" : "DATA WORKSPACE"} title={isOulad ? "Import prepared OULAD data" : "Add dataset"} subtitle={isOulad ? "Select the prepared OULAD feature CSV, validate its learner-course records, and process it in the Master Admin workspace." : "Upload a CSV or XLSX file, review validation, then process it for this account."} />
    <section className="panel">
      <label>Dataset name <input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} placeholder="Optional display name" /></label>
      {isOulad && <p className="form-subtitle">Choose <code>ml/data/processed/oulad_learner_features.csv</code> from this checkout. Upload is scoped to the signed-in Master Admin workspace and is never automatic.</p>}
      <label>CSV or XLSX file <input type="file" accept=".csv,.xlsx" disabled={busy} onChange={(event) => { setFile(event.target.files?.[0] || null); setPreview(null); setResult(null); }} /></label>
      <div className="heading-actions"><button className="secondary-button" disabled={!file || busy} onClick={inspect}>{busy ? "Checking…" : "Preview and validate"}</button><button className="primary-button" disabled={!file || busy || !previewCanProcess} onClick={process}>{busy ? "Processing…" : predictionReady ? "Upload and predict" : "Import descriptive-only"}</button></div>
      {error && <p role="alert">{error}</p>}
      {deleteState.message && <p role="status">{deleteState.message}</p>}
      {deleteState.error && <p role="alert">{deleteState.error}</p>}
      {preview && <div className="dataset-validation">
        <h2>Validation</h2>
        <p><strong>File:</strong> {preview.filename} · {file?.type || file?.name?.split(".").pop()?.toUpperCase() || "Unknown format"}</p>
        <p><strong>Size and shape:</strong> {Math.ceil((preview.file_size_bytes || file?.size || 0) / 1024).toLocaleString()} KB · {preview.row_count} rows · {preview.columns?.length || 0} columns</p>
        <p><strong>Rows:</strong> {preview.validation?.rows_retained ?? 0} retained · {preview.validation?.rows_rejected ?? 0} rejected · {preview.validation?.rows_skipped ?? 0} skipped · {preview.validation?.rows_with_recoverable_missing_values ?? 0} need saved-model imputation</p>
        <p><strong>Compatibility:</strong> {preview.validation?.descriptive_compatible ? "Descriptive ready" : "Not compatible with descriptive analytics"} · {predictionReady ? "ML prediction ready" : "Descriptive-only; no predictions will be generated"}</p>
        {Boolean(preview.validation?.missing_prediction_columns?.length) && <p role="alert"><strong>Missing required model features:</strong> {preview.validation.missing_prediction_columns.join(", ")}</p>}
        {preview.validation?.errors?.map((item, index) => <p role="alert" key={`${item.code}-${item.column || index}`}>{item.message}</p>)}
        {preview.validation?.warnings?.map((item, index) => <p key={`${item.code}-${index}`}>{item.message}{item.columns?.length ? `: ${item.columns.join(", ")}` : ""}</p>)}
        {Boolean(Object.values(preview.validation?.missing_value_counts || {}).some(Number)) && <div><h3>Missing values</h3><ul>{Object.entries(preview.validation.missing_value_counts).filter(([, count]) => count > 0).map(([column, count]) => <li key={column}>{column}: {count}</li>)}</ul><p>Recoverable feature values are handled by the model’s saved training-fitted preprocessing pipeline. Missing learner keys or absent required feature columns prevent predictions.</p></div>}
        {preview.validation?.invalid_values?.length > 0 && <div><h3>Invalid values</h3><ul>{preview.validation.invalid_values.map((item, index) => <li key={`${item.code}-${item.column || index}`}>{item.message}</li>)}</ul></div>}
        {preview.validation?.data_types && <details><summary>Detected column types</summary><pre>{JSON.stringify(preview.validation.data_types, null, 2)}</pre></details>}
        {preview.preview_rows?.length > 0 && <details><summary>Preview first {preview.preview_rows.length} rows</summary><pre>{JSON.stringify(preview.preview_rows, null, 2)}</pre></details>}
      </div>}
      {result && <div role="status">
        <h2>{result.data?.status === "failed" ? "Processing failed" : result.validation?.prediction_state === "available" ? "Predictions saved" : result.data?.status === "processed" ? "Learner data saved; predictions unavailable" : "Dataset status updated"}</h2>
        <p>{result.data?.status} · {result.data?.row_count ?? 0} learner records</p>
        {result.validation?.processing_state && <p><strong>Workflow state:</strong> {result.validation.processing_state}{result.validation.failed_stage ? ` · stopped during ${result.validation.failed_stage}` : ""}</p>}
        {result.validation?.source_revision_created && <p>This source content differs from, or could not be verified against, the prior revision. It was saved as a new dataset so the previous dataset and results remain intact.</p>}
        {result.data?.error_summary && <p>{result.data.error_summary}</p>}
        {result.validation?.prediction_state && <p><strong>Prediction status:</strong> {result.validation.prediction_state} · {result.validation.predictions_persisted ?? 0} saved of {result.data?.row_count ?? 0} rows</p>}
        {result.validation?.prediction_state && <p><strong>Prediction rows skipped:</strong> {result.validation.prediction_rows_skipped ?? 0} · <strong>Rows handled by saved preprocessing:</strong> {result.validation.rows_cleaned_by_model_pipeline ?? 0}</p>}
        {result.validation?.prediction_message && <p role="alert">{result.validation.prediction_message}</p>}
        {result.validation?.prediction_error && <p role="alert">{result.validation.prediction_error}</p>}
        {result.validation?.explanations_state && <p>Explanations: {result.validation.explanations_state} · {result.validation.explanations_persisted ?? 0} saved</p>}
        {result.validation?.recommendations_state && <p>Recommendations: {result.validation.recommendations_state} · {result.validation.recommendations_persisted ?? 0} saved</p>}
        {["processed", "failed"].includes(result.data?.status) && file && <button className="secondary-button" disabled={busy} onClick={retryOrReprocess}>{busy ? "Submitting…" : result.data.status === "failed" ? "Retry processing" : "Reprocess same dataset"}</button>} <Link to="/dashboard">Open dataset workspace</Link>
      </div>}
    </section>
    <section className="panel">
      <div className="panel-heading"><div><h2>Available datasets</h2><p>Owner-scoped records returned by the dataset API.</p></div><button className="secondary-button" type="button" onClick={() => refresh().catch((reason) => setError(reason.message))}>Refresh</button></div>
      {datasetsLoading ? <p role="status">Loading dataset records…</p> : datasetsError ? <div role="alert"><p>Dataset records are unavailable. The workspace may not be empty.</p><button className="secondary-button" type="button" onClick={() => refresh().catch((reason) => setError(reason.message))}>Retry dataset list</button></div> : datasets.length === 0 ? <p>No datasets have been returned for this workspace.</p> : <div className="action-list">{datasets.map((item) => <article className="action-row" key={item.id}>
        <div className="action-copy"><strong>{item.dataset_name}</strong><span>{item.filename} · {item.row_count ?? "Unknown"} rows · updated {item.updated_at || item.uploaded_at || "time unavailable"}</span>{item.error_summary && <span role="alert">{item.error_summary}</span>}</div>
        <span className="action-status">{item.status} · {item.prediction_compatible ? "prediction compatible" : "no prediction compatibility"}</span>
        {datasetId === item.id ? <span className="status-badge status-active">Selected</span> : <button type="button" className="secondary-button" onClick={() => selectDataset(item.id)}>Select</button>}
        {item.status === "processed" && file && <button type="button" className="secondary-button" disabled={busy || !previewCanProcess} onClick={() => processExisting(item)}>Reprocess with selected file</button>}
        {item.status === "failed" && file && <button type="button" className="secondary-button" disabled={busy || !previewCanProcess} onClick={() => processExisting(item)}>Retry with selected file</button>}
        <button type="button" className="secondary-button" disabled={busy || Boolean(deleteState.busyId) || item.status === "processing"} onClick={() => removeDataset(item)} aria-label={`Delete dataset ${item.dataset_name}`}>{deleteState.busyId === item.id ? "Deleting…" : "Delete dataset"}</button>
      </article>)}</div>}
    </section>
  </>;
}
