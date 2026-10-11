package vn.goldenpath.platform.tenant;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.util.UUID;
import javax.sql.DataSource;
import org.springframework.jdbc.datasource.DelegatingDataSource;

/**
 * Sets the Postgres session variable app.tenant_id on every connection checkout. RLS policies read
 * it; an empty value matches no rows, so code that forgets the tenant fails safe.
 */
public class TenantAwareDataSource extends DelegatingDataSource {

  public TenantAwareDataSource(DataSource target) {
    super(target);
  }

  @Override
  public Connection getConnection() throws SQLException {
    return apply(super.getConnection());
  }

  @Override
  public Connection getConnection(String username, String password) throws SQLException {
    return apply(super.getConnection(username, password));
  }

  private static Connection apply(Connection c) throws SQLException {
    UUID tenant = TenantContext.get();
    try (PreparedStatement ps =
        c.prepareStatement("select set_config('app.tenant_id', ?, false)")) {
      ps.setString(1, tenant == null ? "" : tenant.toString());
      ps.execute();
    } catch (SQLException e) {
      c.close();
      throw e;
    }
    return c;
  }
}
