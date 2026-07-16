function tryParseJson(value: string): unknown | null {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return null;
  }
}

function extractNestedMessage(payload: unknown): string | null {
  if (!payload) return null;
  if (typeof payload === 'string') return payload.trim() || null;
  if (Array.isArray(payload)) {
    const parts = payload
      .map((item) => extractNestedMessage(item))
      .filter((item): item is string => Boolean(item));
    return parts.join('; ') || null;
  }
  if (typeof payload === 'object') {
    const record = payload as Record<string, unknown>;
    for (const key of ['detail', 'message', 'error', 'errors']) {
      if (key in record) {
        const nested = extractNestedMessage(record[key]);
        if (nested) return nested;
      }
    }

    const loc = Array.isArray(record.loc) ? record.loc.join('.') : null;
    const message = typeof record.msg === 'string' ? record.msg : null;
    if (loc && message) {
      return `${loc}: ${message}`;
    }
    if (message) return message;
  }
  return null;
}

export async function readApiError(response: Response, fallbackMessage: string): Promise<string> {
  const rawText = await response.text().catch(() => '');
  if (!rawText.trim()) {
    return `${fallbackMessage} (${response.status})`;
  }

  const parsed = tryParseJson(rawText);
  const parsedMessage = extractNestedMessage(parsed);
  if (parsedMessage) {
    return parsedMessage;
  }

  const trimmed = rawText.trim();
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    return `${fallbackMessage} (${response.status})`;
  }
  return trimmed;
}

export function buildApiError(response: Response, fallbackMessage: string): Promise<Error> {
  return readApiError(response, fallbackMessage).then((message) => new Error(message));
}
