package vn.goldenpath.platform.security;

import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/** Local development only: one demo tenant with an admin and a user. */
@Component
@Profile("dev")
class DevDataSeeder implements ApplicationRunner {
  private static final Logger log = LoggerFactory.getLogger(DevDataSeeder.class);
  static final UUID DEMO_TENANT = UUID.fromString("00000000-0000-7000-8000-000000000001");

  private final JdbcTemplate jdbc;
  private final AppUserRepository users;
  private final PasswordEncoder encoder;

  DevDataSeeder(JdbcTemplate jdbc, AppUserRepository users, PasswordEncoder encoder) {
    this.jdbc = jdbc;
    this.users = users;
    this.encoder = encoder;
  }

  @Override
  @Transactional
  public void run(ApplicationArguments args) {
    if (users.findActiveByEmail("admin@demo.local").isPresent()) {
      return;
    }
    jdbc.update(
        "insert into tenant (id, name) values (?, ?) on conflict do nothing", DEMO_TENANT, "Demo");
    String pw = encoder.encode("Demo@12345");
    users.save(new AppUser(DEMO_TENANT, "admin@demo.local", "Quản trị Demo", pw, "ADMIN,USER"));
    users.save(new AppUser(DEMO_TENANT, "user@demo.local", "Người dùng Demo", pw, "USER"));
    log.info("dev seed: admin@demo.local / user@demo.local, password Demo@12345");
  }
}
