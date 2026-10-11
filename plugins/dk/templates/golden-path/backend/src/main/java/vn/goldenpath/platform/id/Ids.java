package vn.goldenpath.platform.id;

import java.security.SecureRandom;
import java.util.UUID;

/** Time-ordered UUIDv7 ids (RFC 9562): index-friendly, safe to expose, generated in the app. */
public final class Ids {
  private static final SecureRandom RNG = new SecureRandom();

  private Ids() {}

  public static UUID newId() {
    long ms = System.currentTimeMillis();
    long msb = (ms << 16) | (0x7L << 12) | (RNG.nextInt() & 0xFFFL);
    long lsb = (RNG.nextLong() & 0x3FFFFFFFFFFFFFFFL) | 0x8000000000000000L;
    return new UUID(msb, lsb);
  }
}
