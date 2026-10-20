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
  return {
    heading: "Approval status unavailable",
    description: "We could not verify your account approval. Sign in again or contact your administrator for help.",
  };
}
