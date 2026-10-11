package vn.goldenpath.platform.tenant;

import java.util.UUID;
import java.util.function.Supplier;

/**
 * Current tenant for this thread. Set by {@link TenantFilter} for HTTP requests; use {@link #runAs}
 * in jobs. Must be set BEFORE a transaction starts (the DB session variable is applied when the
 * connection is checked out).
 */
public final class TenantContext {
  private static final ThreadLocal<UUID> CURRENT = new ThreadLocal<>();

  private TenantContext() {}

  public static UUID get() {
    return CURRENT.get();
  }

  public static UUID require() {
    UUID t = CURRENT.get();
    if (t == null) {
      throw new IllegalStateException("No tenant in context");
    }
    return t;
  }

  public static void runAs(UUID tenantId, Runnable work) {
    callAs(
        tenantId,
        () -> {
          work.run();
          return null;
        });
  }

  public static <T> T callAs(UUID tenantId, Supplier<T> work) {
    UUID previous = CURRENT.get();
    CURRENT.set(tenantId);
    try {
      return work.get();
    } finally {
      if (previous == null) {
        CURRENT.remove();
      } else {
        CURRENT.set(previous);
      }
    }
  }

  static void set(UUID tenantId) {
    CURRENT.set(tenantId);
  }

  static void clear() {
    CURRENT.remove();
  }
}
