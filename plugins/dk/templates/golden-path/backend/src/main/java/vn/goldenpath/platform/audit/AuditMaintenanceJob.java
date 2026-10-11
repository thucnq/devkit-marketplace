package vn.goldenpath.platform.audit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/** Creates upcoming monthly partitions and drops expired ones (retention in months). */
@Component
class AuditMaintenanceJob {
  private static final Logger log = LoggerFactory.getLogger(AuditMaintenanceJob.class);

  private final JdbcTemplate jdbc;
  private final int retentionMonths;

  AuditMaintenanceJob(
      JdbcTemplate jdbc, @Value("${app.audit.retention-months:3}") int retentionMonths) {
    this.jdbc = jdbc;
    this.retentionMonths = retentionMonths;
  }

  @EventListener(ApplicationReadyEvent.class)
  @Scheduled(cron = "0 15 2 * * *")
  void maintain() {
    jdbc.queryForList("select audit_maintain(?)", retentionMonths);
    log.info("audit partitions maintained, retention={} months", retentionMonths);
  }
}
