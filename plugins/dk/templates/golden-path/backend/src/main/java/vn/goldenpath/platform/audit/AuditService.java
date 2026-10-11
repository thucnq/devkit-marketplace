package vn.goldenpath.platform.audit;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;
import vn.goldenpath.platform.id.Ids;
import vn.goldenpath.platform.pii.PiiMasker;
import vn.goldenpath.platform.security.CurrentUser;
import vn.goldenpath.platform.tenant.TenantContext;

/**
 * Append-only audit trail. Joins the caller's transaction (JdbcTemplate shares the JPA connection),
 * so a rolled-back change leaves no audit row. Details are PII-masked JSON.
 */
@Service
public class AuditService {

  private final JdbcTemplate jdbc;

  public AuditService(JdbcTemplate jdbc) {
    this.jdbc = jdbc;
  }

  public void record(String action, String entityType, String entityId, Object details) {
    jdbc.update(
        "insert into audit_event (id, tenant_id, actor_id, action, entity_type, entity_id, details,"
            + " ip, created_at) values (?, ?, ?, ?, ?, ?, cast(? as jsonb), ?, ?)",
        Ids.newId(),
        TenantContext.get(),
        CurrentUser.idOrNull(),
        action,
        entityType,
        entityId,
        details == null ? null : PiiMasker.toJson(details),
        clientIp(),
        Timestamp.from(Instant.now()));
  }

  public void record(String action, String entityType, UUID entityId, Object details) {
    record(action, entityType, entityId == null ? null : entityId.toString(), details);
  }

  private static String clientIp() {
    if (RequestContextHolder.getRequestAttributes() instanceof ServletRequestAttributes attrs) {
      return attrs.getRequest().getRemoteAddr();
    }
    return null;
  }
}
