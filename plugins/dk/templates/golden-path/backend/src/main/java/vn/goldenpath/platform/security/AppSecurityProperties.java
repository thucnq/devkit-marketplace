package vn.goldenpath.platform.security;

import java.time.Duration;
import java.util.Base64;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/** app.security.* - jwtSecret is base64 of at least 32 random bytes (openssl rand -base64 48). */
@ConfigurationProperties("app.security")
public record AppSecurityProperties(
    String jwtSecret,
    @DefaultValue("15m") Duration accessTtl,
    @DefaultValue("7d") Duration refreshTtl,
    @DefaultValue("http://localhost:5173") String frontendUrl,
    @DefaultValue("true") boolean cookieSecure,
    @DefaultValue("app") String issuer) {

  public AppSecurityProperties {
    if (jwtSecret == null || Base64.getDecoder().decode(jwtSecret).length < 32) {
      throw new IllegalStateException("app.security.jwt-secret must be base64 of >= 32 bytes");
    }
  }

  public SecretKey jwtKey() {
    return new SecretKeySpec(Base64.getDecoder().decode(jwtSecret), "HmacSHA256");
  }
}
