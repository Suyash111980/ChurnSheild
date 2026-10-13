import test from "node:test";
import assert from "node:assert/strict";
import { getAvatarDetails } from "../src/utils/userAvatar.js";

test("uses the account profile name first and normalizes whitespace", () => {
  assert.deepEqual(getAvatarDetails({ email: "parth@example.com" }, { full_name: "  Parth   Nagarkar " }), { initials: "PN", label: "Parth Nagarkar" });
});

test("uses first and last name fields from Supabase metadata", () => {
  assert.deepEqual(getAvatarDetails({ user_metadata: { first_name: "Rahul", last_name: "Sharma" } }), { initials: "RS", label: "Rahul Sharma" });
});

test("uses the first and last words from a full name", () => {
  assert.equal(getAvatarDetails({ user_metadata: { full_name: "Ava Marie Thompson" } }).initials, "AT");
});

test("uses a complete metadata name when the profile only has one name part", () => {
  assert.deepEqual(getAvatarDetails({ user_metadata: { full_name: "Parth Nagarkar" } }, { first_name: "Parth" }), { initials: "PN", label: "Parth Nagarkar" });
});

test("uses a single initial for a one-word name", () => {
  assert.deepEqual(getAvatarDetails({ user_metadata: { name: "  Priya " } }), { initials: "P", label: "Priya" });
});

test("falls back to the email initial, then U", () => {
  assert.deepEqual(getAvatarDetails({ email: "  learner@example.com " }), { initials: "L", label: "learner@example.com" });
  assert.deepEqual(getAvatarDetails(null, null), { initials: "U", label: "User" });
});

test("prefers profile name over metadata and auth-context name", () => {
  assert.equal(getAvatarDetails({ name: "Context Person", user_metadata: { full_name: "Metadata Person" } }, { first_name: "Profile", last_name: "Person" }).initials, "PP");
});
