const MASTER_ADMIN_PATHS = new Set(["/master-admin", "/master-admin/oulad", "/admin/users"]);

export function roleRedirect(appRole, pathname) {
  if (appRole === "master_admin") {
    return MASTER_ADMIN_PATHS.has(pathname) ? null : "/admin/users";
  }
  if (pathname === "/master-admin" || pathname.startsWith("/master-admin/")) {
    return "/dashboard";
  }
  return null;
}

export function datasetListState({ loading, error, datasets }) {
  if (loading) return "loading";
  if (error) return "error";
  return datasets.length ? "ready" : "empty";
}
