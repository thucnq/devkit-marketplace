package vn.goldenpath.platform.security;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;
import vn.goldenpath.platform.persistence.BaseEntity;
import vn.goldenpath.platform.pii.Pii;

/** Login identity. Global table (no RLS) because login happens before the tenant is known. */
@Entity
@Table(name = "app_user")
public class AppUser extends BaseEntity {

  @Column(name = "tenant_id", nullable = false, updatable = false)
  private UUID tenantId;

  @Pii
  @Column(nullable = false)
  private String email;

  @Pii
  @Column(name = "full_name", nullable = false)
  private String fullName;

  @Column(name = "password_hash")
  private String passwordHash;

  @Column(nullable = false)
  private String roles;

  @Column(nullable = false)
  private boolean active = true;

  protected AppUser() {}

  public AppUser(UUID tenantId, String email, String fullName, String passwordHash, String roles) {
    this.tenantId = tenantId;
    this.email = email.trim().toLowerCase();
    this.fullName = fullName;
    this.passwordHash = passwordHash;
    this.roles = roles;
  }

  public UUID getTenantId() {
    return tenantId;
  }

  public String getEmail() {
    return email;
  }

  public String getFullName() {
    return fullName;
  }

  public String getPasswordHash() {
    return passwordHash;
  }

  public List<String> roleList() {
    return Arrays.stream(roles.split(",")).map(String::trim).filter(r -> !r.isEmpty()).toList();
  }

  public boolean isActive() {
    return active;
  }
}
