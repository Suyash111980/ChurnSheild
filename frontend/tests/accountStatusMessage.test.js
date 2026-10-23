import test from "node:test";
import assert from "node:assert/strict";
import { accountStatusMessage } from "../src/utils/accountStatusMessage.js";

test("pending and denied accounts get approval-specific guidance", () => {
  assert.equal(accountStatusMessage({ approvalStatus: "pending" }).heading, "Account awaiting approval");
  assert.equal(accountStatusMessage({ approvalStatus: "denied" }).heading, "Account access denied");
});

test("a forbidden profile lookup explains unsupported role instead of service outage", () => {
  const message = accountStatusMessage({ profileErrorStatus: 403, profileErrorDetail: "The ChurnShield profile has no recognized role." });
  assert.equal(message.heading, "Account role not recognized");
  assert.match(message.description, /supported ChurnShield role/);
  assert.notEqual(message.heading, "Approval status unavailable");
});

test("other forbidden profile lookups are shown as blocked access, not an outage", () => {
  assert.equal(accountStatusMessage({ profileErrorStatus: 403, profileErrorDetail: "A valid ChurnShield profile is required." }).heading, "Account access is blocked");
});

test("session errors ask the user to sign in again", () => {
  assert.equal(accountStatusMessage({ profileErrorStatus: 401 }).heading, "Your session needs to be renewed");
});

test("missing API routes are distinguished from approval decisions", () => {
  assert.equal(accountStatusMessage({ profileErrorStatus: 404 }).heading, "Account status endpoint unavailable");
});

test("backend configuration or upstream outages are distinguished from pending approval", () => {
  const message = accountStatusMessage({ profileErrorStatus: 503 });
  assert.equal(message.heading, "Account service unavailable");
  assert.match(message.description, /not an approval decision/i);
});

test("server errors are shown separately from network and CORS failures", () => {
  assert.equal(accountStatusMessage({ profileErrorStatus: 500 }).heading, "ChurnShield service error");
  const network = accountStatusMessage({ profileErrorStatus: null });
  assert.equal(network.heading, "Cannot reach the account-status API");
  assert.match(network.description, /CORS allowlist/i);
});

test("unexpected status codes do not masquerade as account approval states", () => {
  assert.equal(accountStatusMessage({ profileErrorStatus: 418 }).heading, "Approval status could not be checked");
});
