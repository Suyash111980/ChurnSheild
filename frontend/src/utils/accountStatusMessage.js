export function accountStatusMessage({ approvalStatus, profileErrorStatus, profileErrorDetail }) {
  if (approvalStatus === "pending") {
    return {
      heading: "Account awaiting approval",
      description: "Your account is pending. Admin workspace requests are reviewed by a Master Admin. If you did not request an Admin workspace, contact an administrator for next steps.",
    };
  }
  if (approvalStatus === "denied") {
    return {
      heading: "Account access denied",
      description: "A Master Admin denied this account's request. Contact your ChurnShield administrator if you believe this is a mistake.",
    };
  }
  if (profileErrorStatus === 403 && /recognized role/i.test(profileErrorDetail || "")) {
    return {
      heading: "Account role not recognized",
      description: "This account does not have a supported ChurnShield role. Access remains blocked; contact your administrator to review the account.",
    };
  }
  if (profileErrorStatus === 403) {
    return {
      heading: "Account access is blocked",
      description: "The account profile could not be authorized. Contact your administrator to review your account access.",
    };
  }
  if (profileErrorStatus === 401) {
    return {
      heading: "Your session needs to be renewed",
      description: "ChurnShield could not authenticate the saved session. Sign out, sign in again, and retry the account check.",
    };
  }
  if (profileErrorStatus === 404) {
    return {
      heading: "Account status endpoint unavailable",
      description: "The API did not find the account-status route. Check that the frontend and backend are running compatible versions, then retry.",
    };
  }
  if (profileErrorStatus === 503) {
    return {
      heading: "Account service unavailable",
      description: "ChurnShield reached the API, but its authentication or profile service is not ready. This is not an approval decision. Retry later or contact your administrator.",
    };
  }
  if (Number.isInteger(profileErrorStatus) && profileErrorStatus >= 500) {
    return {
      heading: "ChurnShield service error",
      description: "The account-status API returned a server error. Your approval status has not been determined; retry later or contact your administrator.",
    };
  }
  if (profileErrorStatus === null || profileErrorStatus === undefined) {
    return {
      heading: "Cannot reach the account-status API",
      description: "No HTTP response was received. Check that the backend is running at the configured API URL and that its CORS allowlist includes this frontend origin.",
    };
  }
  return {
    heading: "Approval status could not be checked",
    description: "The API returned an unexpected response. This is not an approval decision; retry or contact your administrator.",
  };
}
