import type { ApiErrorCode, ErrorReason } from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: ApiErrorCode,
    message: string,
    readonly retryAfter: number | null = null,
    readonly reason: ErrorReason | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
