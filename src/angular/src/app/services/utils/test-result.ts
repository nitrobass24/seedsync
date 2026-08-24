import { HttpErrorResponse } from '@angular/common/http';

export interface TestResult {
  readonly success: boolean;
  readonly message: string;
}

/** Failure result carrying the server's `{error}` body text when parsable, else `fallback`. */
export function failureFromHttpError(err: HttpErrorResponse, fallback: string): TestResult {
  try {
    const body = typeof err.error === 'string' ? JSON.parse(err.error) : err.error;
    return { success: false, message: body?.error || fallback };
  } catch {
    return { success: false, message: fallback };
  }
}
