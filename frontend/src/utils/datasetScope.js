/** Build one explicit dataset scope without putting the overall sentinel in dataset_id. */
export function datasetScopeParams(datasetId, params = {}) {
  const { dataset_id: explicitId, scope: requestedScope, ...filters } = params;
  const selectedId = datasetId ?? explicitId;
  if (requestedScope === "all" || selectedId === "all") return { ...filters, scope: "all" };
  return selectedId == null || selectedId === "" ? filters : { ...filters, dataset_id: selectedId };
}

export function datasetScopeQuery(datasetId, params = {}) {
  return new URLSearchParams(datasetScopeParams(datasetId, params)).toString();
}
