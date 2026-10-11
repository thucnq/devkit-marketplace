export type FieldError = { field: string; message: string }

/** RFC 9457 problem+json from the backend, normalised. */
export class ApiError extends Error {
  readonly status: number
  readonly detail: string
  readonly errors: FieldError[]

  constructor(status: number, detail: string, errors: FieldError[] = []) {
    super(detail)
    this.status = status
    this.detail = detail
    this.errors = errors
  }

  static async from(res: Response): Promise<ApiError> {
    try {
      const body = (await res.json()) as { detail?: string; errors?: FieldError[] }
      return new ApiError(res.status, body.detail ?? res.statusText, body.errors ?? [])
    } catch {
      return new ApiError(res.status, res.statusText || 'Lỗi không xác định')
    }
  }
}
