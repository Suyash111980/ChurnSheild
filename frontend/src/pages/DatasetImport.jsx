import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, CheckCircle2, CloudUpload, FileSpreadsheet, FileText, RefreshCw, X } from "lucide-react";
import PageHeader from "../components/layout/PageHeader";
import DatasetDeleteDialog from "../components/datasets/DatasetDeleteDialog";
import { deleteDataset, previewDataset, reprocessDataset, retryDataset, uploadDataset } from "../services/datasetService";
import { deleteDatasetAndRefresh, datasetDeletionFeedback, submitDatasetRevision } from "../services/datasetServiceCore.js";
import { useDataset } from "../context/DatasetContext";
import { useAuth } from "../context/AuthContext";
import { usePageTransitionReady } from "../context/NavigationTransitionContext";

export default function DatasetImport({ mode = "default" }) {
  const { datasets, datasetId, selectDataset, refresh, loading: datasetsLoading, error: datasetsError } = useDataset();
  const { accountProfile } = useAuth();
  usePageTransitionReady(!datasetsLoading);
  const [file, setFile] = useState(null);
  const [name, setName] = useState(mode === "oulad" ? "OULAD prepared cohort" : "");
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [deleteState, setDeleteState] = useState({ busyId: null, message: "", error: "" });
  const [deleteTarget, setDeleteTarget] = useState(null);
  const busyRef = useRef(false);
  const fileInputRef = useRef(null);
  const deleteBusyRef = useRef(false);
  const isOulad = mode === "oulad";
  const canUpload = ["admin", "master_admin"].includes(accountProfile?.app_role);
  const previewCanProcess = Boolean(preview?.validation?.descriptive_compatible) && !preview?.validation?.errors?.length;
  function selectFile(nextFile) {
    if (!nextFile) return;
    const extension = nextFile.name.split(".").pop()?.toLowerCase();
    if (!["csv", "xlsx"].includes(extension)) {
      setError("Choose a CSV or XLSX file. Other file types are not supported.");
      return;
    }
    setFile(nextFile);
    setPreview(null);
    setResult(null);
    setError("");
  }
  function clearFile() {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }
  function formatFileSize(size) {
    if (!Number.isFinite(size) || size < 0) return "Size unavailable";
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(2)} MB`;
  }
  function formatUpdated(value) {
    if (!value) return "Time unavailable";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  }
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
  function requestDeleteDataset(item) {
    setDeleteState({ busyId: null, message: "", error: "" });
    setDeleteTarget(item);
  }
  async function removeDataset() {
    const item = deleteTarget;
    if (!item || deleteBusyRef.current) return;
    deleteBusyRef.current = true;
    try {
      const outcome = await deleteDatasetAndRefresh({
        dataset: item,
        selectedDatasetId: datasetId,
        deleteDataset,
        refresh,
        onDeleting: () => setDeleteState({ busyId: item.id, message: "", error: "" }),
      });
      const feedback = datasetDeletionFeedback(outcome);
      if (feedback) {
        setDeleteState({ busyId: null, ...feedback });
        setDeleteTarget(null);
      }
    } catch (reason) {
      setDeleteState({ busyId: null, message: "", error: reason.message || "Dataset could not be deleted." });
    } finally {
      deleteBusyRef.current = false;
    }
  }

  if (!canUpload) return <section className="panel"><h1>Administrator access required</h1><p>Dataset uploads are restricted to administrators.</p></section>;
  return <>
    <PageHeader eyebrow={isOulad ? "PLATFORM DATA" : "DATA WORKSPACE"} title={isOulad ? "Import prepared OULAD data" : "Add dataset"} subtitle={isOulad ? "Select the prepared OULAD feature CSV, validate its learner-course records, and process it in the Master Admin workspace." : "Upload a CSV or XLSX file, review validation, then process it for this account."} />
    <section className="panel dataset-upload-card" aria-labelledby="dataset-upload-heading">
      <div className="dataset-section-heading"><div><span className="dataset-step-label">DATASET INGESTION</span><h2 id="dataset-upload-heading">Upload a dataset</h2><p>Validate the file before processing it for this workspace.</p></div><span className="dataset-format-badge">CSV · XLSX</span></div>
      <label className="dataset-name-field"><span>Dataset name <small>Optional</small></span><input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} placeholder="Give this dataset a clear name" /></label>
      {isOulad && <p className="dataset-upload-note">Choose <code>ml/data/processed/oulad_learner_features.csv</code> from this checkout. Upload is scoped to the signed-in Master Admin workspace and is never automatic.</p>}
      <div className={`dataset-dropzone${dragActive ? " drag-active" : ""}${file ? " has-file" : ""}${busy ? " is-busy" : ""}`}
        onDragEnter={(event) => { event.preventDefault(); if (!busy) setDragActive(true); }}
        onDragOver={(event) => { event.preventDefault(); if (!busy) setDragActive(true); }}
        onDragLeave={(event) => { event.preventDefault(); if (!event.currentTarget.contains(event.relatedTarget)) setDragActive(false); }}
        onDrop={(event) => { event.preventDefault(); setDragActive(false); if (!busy) selectFile(event.dataTransfer.files?.[0]); }}>
        <input ref={fileInputRef} className="dataset-file-input" type="file" accept=".csv,.xlsx" aria-label="Choose a CSV or XLSX dataset file" tabIndex={-1} disabled={busy} onChange={(event) => selectFile(event.target.files?.[0])} />
        {!file ? <div className="dataset-drop-prompt"><span className="dataset-upload-icon"><CloudUpload size={27}/></span><strong>Drop your dataset here</strong><span>or choose a file from your device</span><button className="secondary-button dataset-choose-button" type="button" disabled={busy} onClick={() => fileInputRef.current?.click()}>Choose CSV / Excel file</button><small>Accepted formats: .csv and .xlsx</small></div> : <div className="dataset-selected-file"><span className="dataset-file-icon">{file.name.toLowerCase().endsWith(".xlsx") ? <FileSpreadsheet size={22}/> : <FileText size={22}/>}</span><div className="dataset-file-details"><strong title={file.name}>{file.name}</strong><span>{formatFileSize(file.size)} <i/> {file.name.toLowerCase().endsWith(".xlsx") ? "Excel workbook (.xlsx)" : "CSV file (.csv)"}</span></div><button className="dataset-remove-file" type="button" disabled={busy} onClick={clearFile} aria-label={`Remove ${file.name}`}><X size={17}/><span>Change file</span></button></div>}
      </div>
      <div className="dataset-upload-actions"><button className="secondary-button" type="button" disabled={!file || busy} onClick={inspect}>{busy ? <><RefreshCw size={15} className="dataset-spin"/>Checking…</> : "Preview & validate"}</button><button className="primary-button" type="button" disabled={!file || busy || !previewCanProcess} onClick={process}>{busy ? <><RefreshCw size={15} className="dataset-spin"/>Upload & process</> : <><CloudUpload size={16}/>Upload & process</>}</button></div>
      {error && <div className="dataset-feedback dataset-feedback-error" role="alert"><AlertCircle size={17}/><span>{error}</span></div>}
      {deleteState.message && <div className="dataset-feedback dataset-feedback-result" role="status">{deleteState.message}</div>}
      {deleteState.error && !deleteTarget && <div className="dataset-feedback dataset-feedback-error" role="alert">{deleteState.error}</div>}
      {preview && <section className="dataset-validation-result" aria-labelledby="dataset-validation-heading"><div className="dataset-section-heading"><div><h3 id="dataset-validation-heading">Validation result</h3><p>{preview.row_count} rows · {(preview.columns || []).length} columns detected</p></div><span className={`dataset-validation-badge ${previewCanProcess ? "valid" : "invalid"}`}>{previewCanProcess ? <CheckCircle2 size={15}/> : <AlertCircle size={15}/>}{previewCanProcess ? "Ready to process" : "Needs attention"}</span></div><div className="dataset-compatibility"><span className={preview.validation?.descriptive_compatible ? "compatible" : "incompatible"}>{preview.validation?.descriptive_compatible ? "Descriptive analytics compatible" : "Not compatible with descriptive analytics"}</span><span className={preview.validation?.prediction_compatible ? "compatible" : "incompatible"}>{preview.validation?.prediction_compatible ? "Prediction compatible" : "Not compatible with current predictive model"}</span></div>{preview.validation?.errors?.map((item) => <p className="dataset-validation-message error" role="alert" key={item.message}>{item.message}</p>)}{preview.validation?.warnings?.map((item) => <p className="dataset-validation-message" key={item.code}>{item.message}</p>)}<details className="dataset-preview-details"><summary>Preview detected columns and sample rows</summary><p className="dataset-column-list">{(preview.columns || []).join(" · ")}</p><pre>{JSON.stringify(preview.preview_rows, null, 2)}</pre></details></section>}
      {result && <div className="dataset-feedback dataset-feedback-result" role="status"><div><h3>{result.data?.status === "processed" ? "Processing complete" : result.data?.status === "failed" ? "Processing failed" : "Dataset status updated"}</h3><p>{result.data?.status} · {result.data?.row_count ?? 0} records</p>{result.data?.error_summary && <p>{result.data.error_summary}</p>}{result.validation?.prediction_state && <p>Prediction status: {result.validation.prediction_state} · persisted: {result.validation.predictions_persisted ?? 0}</p>}</div><div className="dataset-result-actions">{["processed", "failed"].includes(result.data?.status) && file && <button className="secondary-button" type="button" disabled={busy} onClick={retryOrReprocess}>{busy ? "Submitting…" : result.data.status === "failed" ? "Retry processing" : "Reprocess same dataset"}</button>}<Link className="text-button" to="/dashboard">Open dataset workspace</Link></div></div>}
    </section>
    <section className="panel dataset-list-card" aria-labelledby="available-datasets-heading">
      <div className="dataset-section-heading"><div><span className="dataset-step-label">WORKSPACE LIBRARY</span><h2 id="available-datasets-heading">Available datasets</h2><p>Owner-scoped datasets available in this workspace.</p></div><button className="secondary-button dataset-refresh-button" type="button" disabled={datasetsLoading} aria-busy={datasetsLoading} onClick={() => refresh().catch((reason) => setError(reason.message))}><RefreshCw size={15} className={datasetsLoading ? "dataset-spin" : ""}/>{datasetsLoading ? "Refreshing…" : "Refresh"}</button></div>
      {datasetsLoading ? <div className="dataset-list-state" role="status"><span className="dataset-state-spinner"/><strong>Loading datasets</strong><span>Retrieving your workspace metadata.</span></div> : datasetsError ? <div className="dataset-list-state error" role="alert"><AlertCircle size={22}/><strong>Dataset list unavailable</strong><span>The workspace may not be empty. Try refreshing the list.</span><button className="secondary-button" type="button" onClick={() => refresh().catch((reason) => setError(reason.message))}>Retry dataset list</button></div> : datasets.length === 0 ? <div className="dataset-list-state"><span className="dataset-empty-icon"><FileSpreadsheet size={21}/></span><strong>No datasets yet</strong><span>Uploaded datasets for this workspace will appear here.</span></div> : <div className="dataset-list">{datasets.map((item) => <article className={`dataset-row${datasetId === item.id ? " selected" : ""}`} key={item.id}>
        <span className="dataset-row-icon"><FileSpreadsheet size={19}/></span><div className="dataset-row-main"><div className="dataset-row-title"><strong>{item.dataset_name || item.filename || "Untitled dataset"}</strong>{datasetId === item.id && <span className="dataset-pill selected-pill">Selected</span>}{item.status === "processed" && <span className="dataset-pill processed-pill">Processed</span>}{item.prediction_compatible && <span className="dataset-pill compatible-pill">Prediction compatible</span>}</div><span className="dataset-filename" title={item.filename}>{item.filename || "Filename unavailable"}</span><div className="dataset-row-meta"><span>{item.row_count != null && Number.isFinite(Number(item.row_count)) ? `${Number(item.row_count).toLocaleString()} rows` : "Row count unavailable"}</span><i/><span>Updated {formatUpdated(item.updated_at || item.uploaded_at)}</span></div>{item.error_summary && <span className="dataset-row-error" role="alert">{item.error_summary}</span>}</div><span className={`dataset-pill status-pill status-${String(item.status || "unknown").toLowerCase()}`}>{item.status || "Unknown status"}</span><div className="dataset-row-actions">{datasetId === item.id ? <span className="dataset-selected-control"><CheckCircle2 size={15}/>Selected</span> : <button type="button" className="secondary-button" onClick={() => selectDataset(item.id)}>Select</button>}{item.status === "processed" && file && <button type="button" className="secondary-button" disabled={busy || !previewCanProcess} onClick={() => processExisting(item)}>Reprocess</button>}{item.status === "failed" && file && <button type="button" className="secondary-button" disabled={busy || !previewCanProcess} onClick={() => processExisting(item)}>Retry processing</button>}<button type="button" className="secondary-button dataset-delete-button" disabled={busy || Boolean(deleteState.busyId) || item.status === "processing"} onClick={() => requestDeleteDataset(item)} aria-label={`Delete dataset ${item.dataset_name}`}>{deleteState.busyId === item.id ? "Deleting…" : "Delete dataset"}</button></div>
      </article>)}</div>}
    </section>
    <DatasetDeleteDialog
      dataset={deleteTarget}
      pending={Boolean(deleteState.busyId)}
      error={deleteState.error}
      onCancel={() => { if (!deleteState.busyId) setDeleteTarget(null); }}
      onConfirm={removeDataset}
    />
  </>;
}
