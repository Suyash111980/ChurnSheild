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

test("non-authorization profile errors retain the retry/contact guidance", () => {
  assert.equal(accountStatusMessage({ profileErrorStatus: 503 }).heading, "Approval status unavailable");
});
