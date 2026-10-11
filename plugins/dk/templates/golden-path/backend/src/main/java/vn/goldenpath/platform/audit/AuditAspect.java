package vn.goldenpath.platform.audit;

import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;
import org.aspectj.lang.JoinPoint;
import org.aspectj.lang.annotation.AfterReturning;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

/** Runs inside the method's transaction (higher precedence than the transaction advisor). */
@Aspect
@Component
@Order(Ordered.LOWEST_PRECEDENCE)
class AuditAspect {

  private final AuditService audit;

  AuditAspect(AuditService audit) {
    this.audit = audit;
  }

  @AfterReturning(pointcut = "@annotation(audited)", returning = "result")
  void after(JoinPoint jp, Audited audited, Object result) {
    Object[] args = jp.getArgs();
    String id =
        Arrays.stream(args)
            .filter(UUID.class::isInstance)
            .map(Object::toString)
            .findFirst()
            .orElseGet(() -> idOf(result));
    List<Object> details = Arrays.stream(args).filter(a -> !(a instanceof UUID)).toList();
    audit.record(audited.action(), audited.entity(), id, details.isEmpty() ? null : details);
  }

  private static String idOf(Object result) {
    if (result == null) {
      return null;
    }
    for (String name : new String[] {"id", "getId"}) {
      try {
        Method m = result.getClass().getMethod(name);
        Object v = m.invoke(result);
        return v == null ? null : v.toString();
      } catch (ReflectiveOperationException ignored) {
        // try next accessor
      }
    }
    return null;
  }
}
