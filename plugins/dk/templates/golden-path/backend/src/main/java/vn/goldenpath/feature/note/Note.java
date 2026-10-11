package vn.goldenpath.feature.note;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import java.util.UUID;
import vn.goldenpath.platform.persistence.TenantEntity;

/** Reference feature: copy this package's shape for new features, then delete it. */
@Entity
@Table(name = "note")
public class Note extends TenantEntity {

  @Column(nullable = false, length = 200)
  private String title;

  @Column(columnDefinition = "text")
  private String content;

  @Column(name = "owner_id", nullable = false, updatable = false)
  private UUID ownerId;

  protected Note() {}

  Note(String title, String content, UUID ownerId) {
    this.title = title;
    this.content = content;
    this.ownerId = ownerId;
  }

  void update(String title, String content) {
    this.title = title;
    this.content = content;
  }

  public String getTitle() {
    return title;
  }

  public String getContent() {
    return content;
  }

  public UUID getOwnerId() {
    return ownerId;
  }
}
