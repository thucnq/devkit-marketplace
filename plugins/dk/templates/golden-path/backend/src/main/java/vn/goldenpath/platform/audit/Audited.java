package vn.goldenpath.platform.audit;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Records an audit event after the annotated (transactional, public) service method returns. The
 * entity id is the first UUID argument, else the {@code id()} / {@code getId()} of the result;
 * details are the non-UUID arguments, PII-masked.
 */
@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.METHOD)
public @interface Audited {
  String action();

  String entity();
}
