import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import { previewDataset, reprocessDataset, retryDataset, uploadDataset } from "../services/datasetService";
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
  const busyRef = useRef(false);
  const isOulad = mode === "oulad";
  const canUpload = ["admin", "master_admin"].includes(accountProfile?.app_role);
  const previewCanProcess = Boolean(preview?.validation?.descriptive_compatible) && !preview?.validation?.errors?.length;
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
    if (!window.confirm(`Submit ${file.name} to replace the data in “${item.dataset_name}”? Verify that this is the correct source file for this dataset.`)) return;
    busyRef.current = true;
    setBusy(true); setError("");
    try {
      await submitDatasetRevision({
        datasetId: item.id,
        status: item.status,
        file,
        retryDataset,
        reprocessDataset,
        refresh,
        onResponse: setResult,
        onRefreshError: (reason) => setError(reason.message),
      });
      selectDataset(item.id);
    } catch (reason) { setError(reason.message); }
    finally { busyRef.current = false; setBusy(false); }
  }
  if (!canUpload) return <section className="panel"><h1>Administrator access required</h1><p>Dataset uploads are restricted to administrators.</p></section>;
  return <>
    <PageHeader eyebrow={isOulad ? "PLATFORM DATA" : "DATA WORKSPACE"} title={isOulad ? "Import prepared OULAD data" : "Add dataset"} subtitle={isOulad ? "Select the prepared OULAD feature CSV, validate its learner-course records, and process it in the Master Admin workspace." : "Upload a CSV or XLSX file, review validation, then process it for this account."} />
    <section className="panel">
      <label>Dataset name <input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} placeholder="Optional display name" /></label>
      {isOulad && <p className="form-subtitle">Choose <code>ml/data/processed/oulad_learner_features.csv</code> from this checkout. Upload is scoped to the signed-in Master Admin workspace and is never automatic.</p>}
      <label>CSV or XLSX file <input type="file" accept=".csv,.xlsx" disabled={busy} onChange={(event) => { setFile(event.target.files?.[0] || null); setPreview(null); setResult(null); }} /></label>
      <div className="heading-actions"><button className="secondary-button" disabled={!file || busy} onClick={inspect}>{busy ? "Checking…" : "Preview and validate"}</button><button className="primary-button" disabled={!file || busy || !previewCanProcess} onClick={process}>{busy ? "Processing…" : "Upload and process"}</button></div>
      {error && <p role="alert">{error}</p>}
      {preview && <div><h2>Validation</h2><p>{preview.validation?.descriptive_compatible ? "Descriptive analytics compatible" : "Not compatible with descriptive analytics"} · {preview.validation?.prediction_compatible ? "Predictive model compatible" : "Not compatible with current predictive model"}</p><p>{preview.row_count} rows · columns: {(preview.columns || []).join(", ")}</p>{preview.validation?.errors?.map((item) => <p role="alert" key={item.message}>{item.message}</p>)}{preview.validation?.warnings?.map((item) => <p key={item.code}>{item.message}</p>)}<pre>{JSON.stringify(preview.preview_rows, null, 2)}</pre></div>}
      {result && <div role="status"><h2>{result.data?.status === "processed" ? "Processing complete" : result.data?.status === "failed" ? "Processing failed" : "Dataset status updated"}</h2><p>{result.data?.status} · {result.data?.row_count ?? 0} records</p>{result.data?.error_summary && <p>{result.data.error_summary}</p>}{result.validation?.prediction_state && <p>Prediction status: {result.validation.prediction_state} · persisted: {result.validation.predictions_persisted ?? 0}</p>}{["processed", "failed"].includes(result.data?.status) && file && <button className="secondary-button" disabled={busy} onClick={retryOrReprocess}>{busy ? "Submitting…" : result.data.status === "failed" ? "Retry processing" : "Reprocess same dataset"}</button>} <Link to="/dashboard">Open dataset workspace</Link></div>}
    </section>
    <section className="panel">
      <div className="panel-heading"><div><h2>Available datasets</h2><p>Owner-scoped records returned by the dataset API.</p></div><button className="secondary-button" type="button" onClick={() => refresh().catch((reason) => setError(reason.message))}>Refresh</button></div>
      {datasetsLoading ? <p role="status">Loading dataset records…</p> : datasetsError ? <div role="alert"><p>Dataset records are unavailable. The workspace may not be empty.</p><button className="secondary-button" type="button" onClick={() => refresh().catch((reason) => setError(reason.message))}>Retry dataset list</button></div> : datasets.length === 0 ? <p>No datasets have been returned for this workspace.</p> : <div className="action-list">{datasets.map((item) => <article className="action-row" key={item.id}>
        <div className="action-copy"><strong>{item.dataset_name}</strong><span>{item.filename} · {item.row_count ?? "Unknown"} rows · updated {item.updated_at || item.uploaded_at || "time unavailable"}</span>{item.error_summary && <span role="alert">{item.error_summary}</span>}</div>
        <span className="action-status">{item.status} · {item.prediction_compatible ? "prediction compatible" : "no prediction compatibility"}</span>
        {datasetId === item.id ? <span className="status-badge status-active">Selected</span> : <button type="button" className="secondary-button" onClick={() => selectDataset(item.id)}>Select</button>}
        {item.status === "processed" && file && <button type="button" className="secondary-button" disabled={busy || !previewCanProcess} onClick={() => processExisting(item)}>Reprocess with selected file</button>}
        {item.status === "failed" && file && <button type="button" className="secondary-button" disabled={busy || !previewCanProcess} onClick={() => processExisting(item)}>Retry with selected file</button>}
      </article>)}</div>}
    </section>
  </>;
}
