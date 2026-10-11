package vn.goldenpath.platform.persistence;

import jakarta.persistence.Column;
import jakarta.persistence.MappedSuperclass;
import jakarta.persistence.PrePersist;
import java.util.UUID;
import vn.goldenpath.platform.tenant.TenantContext;

/**
 * Entity owned by a tenant. tenant_id is set from the request's tenant on insert and never changes;
 * Postgres RLS enforces isolation on every query.
 */
@MappedSuperclass
public abstract class TenantEntity extends BaseEntity {

  @Column(name = "tenant_id", nullable = false, updatable = false)
  private UUID tenantId;

  @PrePersist
  void assignTenant() {
    if (tenantId == null) {
      tenantId = TenantContext.require();
    }
  }

  public UUID getTenantId() {
    return tenantId;
  }
}
