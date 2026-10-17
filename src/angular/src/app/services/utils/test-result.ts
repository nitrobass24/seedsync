import { HttpErrorResponse } from '@angular/common/http';

export interface TestResult {
  readonly success: boolean;
  readonly message: string;
}

/** The server's JSON error body (`{error, ...}`), or null when absent or unparsable. */
export function errorBodyFromHttpError(err: HttpErrorResponse): Record<string, unknown> | null {
  try {
    const body: unknown = typeof err.error === 'string' ? JSON.parse(err.error) : err.error;
    return body !== null && typeof body === 'object' ? (body as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

/** Failure result carrying the server's `{error}` body text when parsable, else `fallback`. */
export function failureFromHttpError(err: HttpErrorResponse, fallback: string): TestResult {
  const error = errorBodyFromHttpError(err)?.['error'];
  return { success: false, message: typeof error === 'string' && error ? error : fallback };
}
