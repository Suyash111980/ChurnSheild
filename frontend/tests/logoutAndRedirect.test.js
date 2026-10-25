import test from "node:test";
import assert from "node:assert/strict";
import { logoutAndRedirect } from "../src/utils/logoutAndRedirect.js";

test("sidebar logout signs out before replacing the route with login", async () => {
  const calls = [];
  await logoutAndRedirect(
    async () => calls.push("session cleared"),
    (...args) => calls.push(["navigate", ...args]),
  );
  assert.deepEqual(calls, ["session cleared", ["navigate", "/login", { replace: true }]]);
});

test("sidebar logout does not redirect when authentication sign-out fails", async () => {
  const calls = [];
  await assert.rejects(
    logoutAndRedirect(
      async () => { calls.push("sign-out"); throw new Error("sign-out failed"); },
      (...args) => calls.push(["navigate", ...args]),
    ),
    /sign-out failed/,
  );
  assert.deepEqual(calls, ["sign-out"]);
});
