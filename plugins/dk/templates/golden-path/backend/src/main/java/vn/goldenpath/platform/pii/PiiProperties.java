package vn.goldenpath.platform.pii;

import java.util.Base64;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** app.pii.key / app.pii.hash-key: base64 of 32 random bytes each (openssl rand -base64 32). */
@ConfigurationProperties("app.pii")
public record PiiProperties(String key, String hashKey) {
  public PiiProperties {
    require("app.pii.key", key);
    require("app.pii.hash-key", hashKey);
  }

  private static void require(String name, String value) {
    if (value == null || Base64.getDecoder().decode(value).length != 32) {
      throw new IllegalStateException(name + " must be base64 of exactly 32 bytes");
    }
  }
}
