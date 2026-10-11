package vn.goldenpath.platform.pii;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.SecureRandom;
import java.util.Base64;
import javax.crypto.Cipher;
import javax.crypto.Mac;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.stereotype.Component;

/**
 * AES-256-GCM for sensitive personal data at rest, HMAC-SHA256 for exact-match lookups. Layout of a
 * ciphertext: [version=1][12-byte IV][ciphertext+tag]. Static access exists because JPA converters
 * are instantiated outside Spring.
 */
@Component
public class PiiCrypto {
  private static final byte VERSION = 1;
  private static final int IV_LEN = 12;
  private static final SecureRandom RNG = new SecureRandom();
  private static volatile PiiCrypto instance;

  private final SecretKey key;
  private final SecretKey hashKey;

  public PiiCrypto(PiiProperties props) {
    this.key = new SecretKeySpec(Base64.getDecoder().decode(props.key()), "AES");
    this.hashKey = new SecretKeySpec(Base64.getDecoder().decode(props.hashKey()), "HmacSHA256");
    instance = this;
  }

  public static PiiCrypto get() {
    PiiCrypto c = instance;
    if (c == null) {
      throw new IllegalStateException("PiiCrypto not initialised");
    }
    return c;
  }

  public byte[] encrypt(byte[] plain) {
    try {
      byte[] iv = new byte[IV_LEN];
      RNG.nextBytes(iv);
      Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
      cipher.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(128, iv));
      byte[] ct = cipher.doFinal(plain);
      return ByteBuffer.allocate(1 + IV_LEN + ct.length).put(VERSION).put(iv).put(ct).array();
    } catch (GeneralSecurityException e) {
      throw new IllegalStateException("encryption failed", e);
    }
  }

  public byte[] decrypt(byte[] blob) {
    try {
      ByteBuffer buf = ByteBuffer.wrap(blob);
      if (buf.get() != VERSION) {
        throw new IllegalStateException("unknown ciphertext version");
      }
      byte[] iv = new byte[IV_LEN];
      buf.get(iv);
      byte[] ct = new byte[buf.remaining()];
      buf.get(ct);
      Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
      cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, iv));
      return cipher.doFinal(ct);
    } catch (GeneralSecurityException e) {
      throw new IllegalStateException("decryption failed", e);
    }
  }

  public String encryptString(String plain) {
    return plain == null
        ? null
        : Base64.getEncoder().encodeToString(encrypt(plain.getBytes(StandardCharsets.UTF_8)));
  }

  /** Deterministic keyed hash of a normalised value, for WHERE col_hash = ? lookups. */
  public byte[] hash(String value) {
    try {
      Mac mac = Mac.getInstance("HmacSHA256");
      mac.init(hashKey);
      return mac.doFinal(value.strip().toLowerCase().getBytes(StandardCharsets.UTF_8));
    } catch (GeneralSecurityException e) {
      throw new IllegalStateException("hash failed", e);
    }
  }
}
