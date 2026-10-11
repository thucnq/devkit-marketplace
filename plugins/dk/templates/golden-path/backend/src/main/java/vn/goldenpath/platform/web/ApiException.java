package vn.goldenpath.platform.web;

import org.springframework.http.HttpStatus;

/** A business error with a status and a user-facing (Vietnamese) message. */
public class ApiException extends RuntimeException {
  private final HttpStatus status;

  public ApiException(HttpStatus status, String userMessage) {
    super(userMessage);
    this.status = status;
  }

  public HttpStatus status() {
    return status;
  }
}
