import { supabase } from "../lib/supabase";

/** Sends a recovery link to the address entered by the user. The allow-listed
 * redirect URL must include this frontend route in the Supabase Auth settings. */
export async function requestPasswordReset(email) {
  const redirectTo = `${window.location.origin}/set-new-password`;
  const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), { redirectTo });
  if (error) throw error;
}

/** Updates a password only when Supabase has established a valid session from
 * the recovery link. No password or auth token is persisted by this service. */
export async function updateRecoveredPassword(password) {
  const { data, error: sessionError } = await supabase.auth.getSession();
  if (sessionError) throw sessionError;
  if (!data.session) throw new Error("This password reset link is invalid or has expired. Request a new link to continue.");

  const { error } = await supabase.auth.updateUser({ password });
  if (error) throw error;
}
