export const prettyJsonFromValue = (
  value: unknown,
  fallback = "{}",
): string => {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return fallback;
  }
};

export const prettyJsonFromString = (
  value: string | null | undefined,
): string | null => {
  if (!value) return null;
  try {
    return prettyJsonFromValue(JSON.parse(value), value);
  } catch {
    return value;
  }
};

