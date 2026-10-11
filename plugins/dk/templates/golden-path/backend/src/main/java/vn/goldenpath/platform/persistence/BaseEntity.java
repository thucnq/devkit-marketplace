package vn.goldenpath.platform.persistence;

import jakarta.persistence.Column;
import jakarta.persistence.Id;
import jakarta.persistence.MappedSuperclass;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Version;
import java.time.Instant;
import java.util.UUID;
import vn.goldenpath.platform.id.Ids;
import vn.goldenpath.platform.security.CurrentUser;

/** Id (UUIDv7), optimistic lock and who/when columns for every entity. */
@MappedSuperclass
public abstract class BaseEntity {

  @Id private UUID id = Ids.newId();

  @Version private Integer version;

  @Column(name = "created_at", nullable = false, updatable = false)
  private Instant createdAt;

  @Column(name = "updated_at", nullable = false)
  private Instant updatedAt;

  @Column(name = "created_by", updatable = false)
  private UUID createdBy;

  @Column(name = "updated_by")
  private UUID updatedBy;

  @PrePersist
  void onCreate() {
    Instant now = Instant.now();
    createdAt = now;
    updatedAt = now;
    createdBy = CurrentUser.idOrNull();
    updatedBy = createdBy;
  }

  @PreUpdate
  void onUpdate() {
    updatedAt = Instant.now();
    updatedBy = CurrentUser.idOrNull();
  }

  public UUID getId() {
    return id;
  }

  public Integer getVersion() {
    return version;
  }

  public Instant getCreatedAt() {
    return createdAt;
  }

  public Instant getUpdatedAt() {
    return updatedAt;
  }

  public UUID getCreatedBy() {
    return createdBy;
  }

  public UUID getUpdatedBy() {
    return updatedBy;
  }
}
