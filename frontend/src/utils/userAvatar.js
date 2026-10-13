const clean = (value) => typeof value === "string" ? value.trim().replace(/\s+/g, " ") : "";

function nameFromSource(source) {
  if (!source || typeof source !== "object") return "";

  const firstName = clean(source.first_name);
  const lastName = clean(source.last_name);
  if (firstName && lastName) return `${firstName} ${lastName}`;

  return clean(source.full_name) || clean(source.name) || clean(source.display_name);
}

function singleNameFromSource(source) {
  return clean(source?.first_name) || clean(source?.last_name);
}

export function getAvatarDetails(user, accountProfile) {
  const metadata = user?.user_metadata ?? user?.metadata;
  const profileSources = [accountProfile, user?.profile];
  const contextSources = [user];
  const nameSources = [...profileSources, metadata, ...contextSources];
  const completeName = nameSources.map(nameFromSource).find(Boolean);
  const name = completeName || nameSources.map(singleNameFromSource).find(Boolean) || "";
  const email = clean(user?.email);
  const label = name || email || "User";
  const words = label.split(" ").filter(Boolean);
  const initials = name
    ? words.length > 1
      ? `${words[0][0]}${words[words.length - 1][0]}`
      : words[0]?.[0]
    : email[0] || "U";

  return { initials: (initials || "U").toLocaleUpperCase(), label };
}
