export async function logoutAndRedirect(logout, navigate) {
  await logout();
  navigate("/login", { replace: true });
}