package vn.goldenpath;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.UUID;
import java.util.function.Supplier;
import org.junit.jupiter.api.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import vn.goldenpath.platform.id.Ids;
import vn.goldenpath.platform.security.AppUser;
import vn.goldenpath.platform.security.AppUserRepository;
import vn.goldenpath.platform.security.TokenService;
import vn.goldenpath.platform.tenant.TenantContext;

/**
 * Base for acceptance tests at the HTTP boundary: real Postgres 17 (Testcontainers, shared across
 * test classes), real Flyway migrations, app connected as app_rw so RLS is exercised.
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Tag("api")
public abstract class ApiTestBase {
  protected static final String PASSWORD = "Test@12345";

  static final PostgreSQLContainer<?> PG = new PostgreSQLContainer<>("postgres:17-alpine");

  static {
    PG.start();
  }

  @DynamicPropertySource
  static void database(DynamicPropertyRegistry r) {
    r.add("spring.datasource.url", PG::getJdbcUrl);
    r.add("spring.datasource.username", () -> "app_rw");
    r.add("spring.datasource.password", () -> "app_rw_test");
    r.add("spring.flyway.url", PG::getJdbcUrl);
    r.add("spring.flyway.user", PG::getUsername);
    r.add("spring.flyway.password", PG::getPassword);
    r.add("spring.flyway.placeholders.app_rw_password", () -> "app_rw_test");
  }

  @Autowired protected MockMvc mvc;
  @Autowired protected ObjectMapper objectMapper;
  @Autowired protected JdbcTemplate jdbc;
  @Autowired protected TokenService tokens;
  @Autowired protected AppUserRepository users;
  @Autowired protected PasswordEncoder passwordEncoder;

  protected UUID newTenant() {
    UUID id = Ids.newId();
    jdbc.update("insert into tenant (id, name) values (?, ?)", id, "Tenant " + id);
    return id;
  }

  protected AppUser newUser(UUID tenant, String roles) {
    return users.save(
        new AppUser(
            tenant,
            "u" + Ids.newId() + "@test.local",
            "Nguyễn Văn Kiểm Thử",
            passwordEncoder.encode(PASSWORD),
            roles));
  }

  protected String bearer(AppUser user) {
    return "Bearer " + tokens.accessToken(user);
  }

  protected String json(Object value) throws Exception {
    return objectMapper.writeValueAsString(value);
  }

  protected <T> T inTenant(UUID tenant, Supplier<T> work) {
    return TenantContext.callAs(tenant, work);
  }

  /** Audit rows are tenant-scoped by RLS too, so they must be read inside the tenant. */
  protected long auditCount(UUID tenant, String action, String entityId) {
    return inTenant(
        tenant,
        () ->
            jdbc.queryForObject(
                "select count(*) from audit_event where action = ? and (cast(? as varchar) is null"
                    + " or entity_id = ?)",
                Long.class,
                action,
                entityId,
                entityId));
  }
}
