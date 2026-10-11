package vn.goldenpath.platform.pii;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/** Marks personal data. Masked by {@link PiiMasker} in logs, audit details and descriptions. */
@Retention(RetentionPolicy.RUNTIME)
@Target({
  ElementType.FIELD,
  ElementType.METHOD,
  ElementType.RECORD_COMPONENT,
  ElementType.PARAMETER
})
public @interface Pii {}
