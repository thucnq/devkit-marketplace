package vn.goldenpath.platform.web;

import jakarta.validation.ConstraintViolationException;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.OptimisticLockingFailureException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;
import vn.goldenpath.platform.security.TokenService;

/** RFC 9457 problem+json for every error. Never leaks stack traces, SQL or internal state. */
@RestControllerAdvice
class GlobalExceptionHandler extends ResponseEntityExceptionHandler {
  private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

  @ExceptionHandler(ApiException.class)
  ProblemDetail api(ApiException e) {
    return ProblemDetail.forStatusAndDetail(e.status(), e.getMessage());
  }

  @ExceptionHandler({
    AuthenticationException.class,
    TokenService.InvalidRefreshTokenException.class
  })
  ProblemDetail unauthorized(RuntimeException e) {
    return ProblemDetail.forStatusAndDetail(
        HttpStatus.UNAUTHORIZED,
        e instanceof AuthenticationException ? e.getMessage() : "Phiên đăng nhập đã hết hạn.");
  }

  @ExceptionHandler(AccessDeniedException.class)
  ProblemDetail forbidden(AccessDeniedException e) {
    return ProblemDetail.forStatusAndDetail(
        HttpStatus.FORBIDDEN, "Bạn không có quyền thực hiện thao tác này.");
  }

  @ExceptionHandler(OptimisticLockingFailureException.class)
  ProblemDetail conflict(OptimisticLockingFailureException e) {
    return ProblemDetail.forStatusAndDetail(
        HttpStatus.CONFLICT, "Dữ liệu đã được người khác cập nhật. Vui lòng tải lại.");
  }

  @ExceptionHandler(DataIntegrityViolationException.class)
  ProblemDetail integrity(DataIntegrityViolationException e) {
    log.warn("data integrity violation: {}", e.getMostSpecificCause().getClass().getSimpleName());
    return ProblemDetail.forStatusAndDetail(
        HttpStatus.CONFLICT, "Dữ liệu bị trùng hoặc vi phạm ràng buộc.");
  }

  @ExceptionHandler(ConstraintViolationException.class)
  ProblemDetail constraint(ConstraintViolationException e) {
    ProblemDetail pd =
        ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "Dữ liệu không hợp lệ.");
    pd.setProperty(
        "errors",
        e.getConstraintViolations().stream()
            .map(v -> Map.of("field", v.getPropertyPath().toString(), "message", v.getMessage()))
            .toList());
    return pd;
  }

  @Override
  protected ResponseEntity<Object> handleMethodArgumentNotValid(
      MethodArgumentNotValidException ex,
      HttpHeaders headers,
      HttpStatusCode status,
      WebRequest request) {
    ProblemDetail pd =
        ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "Dữ liệu không hợp lệ.");
    List<Map<String, String>> errors =
        ex.getBindingResult().getFieldErrors().stream()
            .map(
                f ->
                    Map.of("field", f.getField(), "message", String.valueOf(f.getDefaultMessage())))
            .toList();
    pd.setProperty("errors", errors);
    return ResponseEntity.badRequest().body(pd);
  }

  @ExceptionHandler(Exception.class)
  ProblemDetail unexpected(Exception e) {
    log.error("unhandled error", e);
    return ProblemDetail.forStatusAndDetail(
        HttpStatus.INTERNAL_SERVER_ERROR, "Đã có lỗi xảy ra. Vui lòng thử lại sau.");
  }
}
