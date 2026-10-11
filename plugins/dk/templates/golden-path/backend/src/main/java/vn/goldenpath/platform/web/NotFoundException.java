package vn.goldenpath.platform.web;

import org.springframework.http.HttpStatus;

/** 404 — also used for other tenants' resources, so existence is never leaked. */
public class NotFoundException extends ApiException {
  public NotFoundException(String entity, Object id) {
    super(HttpStatus.NOT_FOUND, "Không tìm thấy " + entity + " " + id);
  }
}
