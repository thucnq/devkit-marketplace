package vn.goldenpath.platform;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import org.junit.jupiter.api.Test;
import vn.goldenpath.platform.id.Ids;
import vn.goldenpath.platform.pii.Pii;
import vn.goldenpath.platform.pii.PiiCrypto;
import vn.goldenpath.platform.pii.PiiMasker;
import vn.goldenpath.platform.pii.PiiProperties;

class PiiMaskingTest {

  record Customer(@Pii String fullName, @Pii String phone, String city) {}

  static PiiCrypto crypto() {
    String k =
        Base64.getEncoder()
            .encodeToString("0123456789abcdef0123456789abcdef".getBytes(StandardCharsets.UTF_8));
    return new PiiCrypto(new PiiProperties(k, k));
  }

  @Test
  void piiFieldsAreMaskedForLogsAndAudit() {
    String json = PiiMasker.toJson(new Customer("Nguyễn Văn An", "0912345678", "Hà Nội"));
    assertThat(json)
        .doesNotContain("Nguyễn Văn An")
        .doesNotContain("0912345678")
        .contains("Hà Nội");
    assertThat(json).contains("N***n").contains("0***8");
  }

  @Test
  void encryptionRoundTripsAndUsesRandomIv() {
    PiiCrypto c = crypto();
    byte[] a = c.encrypt("079123456789".getBytes(StandardCharsets.UTF_8));
    byte[] b = c.encrypt("079123456789".getBytes(StandardCharsets.UTF_8));
    assertThat(a).isNotEqualTo(b);
    assertThat(new String(c.decrypt(a), StandardCharsets.UTF_8)).isEqualTo("079123456789");
  }

  @Test
  void tamperedCiphertextIsRejected() {
    PiiCrypto c = crypto();
    byte[] a = c.encrypt("secret".getBytes(StandardCharsets.UTF_8));
    a[a.length - 1] ^= 1;
    assertThatThrownBy(() -> c.decrypt(a)).isInstanceOf(IllegalStateException.class);
  }

  @Test
  void lookupHashIsDeterministicAndNormalised() {
    PiiCrypto c = crypto();
    assertThat(c.hash(" A@B.com ")).isEqualTo(c.hash("a@b.com"));
  }

  @Test
  void idsAreTimeOrderedVersion7() {
    var first = Ids.newId();
    var second = Ids.newId();
    assertThat(first.version()).isEqualTo(7);
    assertThat(first.getMostSignificantBits() >>> 16)
        .isLessThanOrEqualTo(second.getMostSignificantBits() >>> 16);
  }
}
