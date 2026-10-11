package vn.goldenpath.platform.security;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Base64;
import java.util.UUID;
import org.springframework.http.ResponseCookie;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import vn.goldenpath.platform.id.Ids;

/**
 * Issues short-lived access JWTs and rotating refresh tokens (stored hashed, with reuse detection:
 * presenting a revoked token revokes its whole family).
 */
@Service
public class TokenService {
  public static final String REFRESH_COOKIE = "rt";
  private static final SecureRandom RNG = new SecureRandom();

  private final JwtEncoder encoder;
  private final RefreshTokenRepository refreshTokens;
  private final AppUserRepository users;
  private final AppSecurityProperties props;

  public TokenService(
      JwtEncoder encoder,
      RefreshTokenRepository refreshTokens,
      AppUserRepository users,
      AppSecurityProperties props) {
    this.encoder = encoder;
    this.refreshTokens = refreshTokens;
    this.users = users;
    this.props = props;
  }

  public record Issued(String accessToken, long expiresIn, String refreshToken, AppUser user) {}

  @Transactional
  public Issued issue(AppUser user) {
    return issue(user, Ids.newId());
  }

  /**
   * Rotates a refresh token; throws when it is unknown, expired, or reused (reuse revokes the
   * family).
   */
  @Transactional(noRollbackFor = InvalidRefreshTokenException.class)
  public Issued refresh(String rawRefreshToken) {
    Instant now = Instant.now();
    RefreshToken current =
        refreshTokens
            .findByTokenHash(hash(rawRefreshToken))
            .orElseThrow(InvalidRefreshTokenException::new);
    if (current.isRevoked()) {
      refreshTokens.revokeFamily(current.getFamilyId(), now); // reuse → kill the session
      throw new InvalidRefreshTokenException();
    }
    if (!current.isUsable(now)) {
      throw new InvalidRefreshTokenException();
    }
    AppUser user =
        users
            .findById(current.getUserId())
            .filter(AppUser::isActive)
            .orElseThrow(InvalidRefreshTokenException::new);
    current.revoke(now);
    return issue(user, current.getFamilyId());
  }

  @Transactional
  public void revoke(String rawRefreshToken) {
    refreshTokens
        .findByTokenHash(hash(rawRefreshToken))
        .ifPresent(t -> refreshTokens.revokeFamily(t.getFamilyId(), Instant.now()));
  }

  public String accessToken(AppUser user) {
    Instant now = Instant.now();
    JwtClaimsSet claims =
        JwtClaimsSet.builder()
            .issuer(props.issuer())
            .subject(user.getId().toString())
            .issuedAt(now)
            .expiresAt(now.plus(props.accessTtl()))
            .claim("tid", user.getTenantId().toString())
            .claim("roles", user.roleList())
            .build();
    JwsHeader header = JwsHeader.with(MacAlgorithm.HS256).build();
    return encoder.encode(JwtEncoderParameters.from(header, claims)).getTokenValue();
  }

  public String refreshCookie(String rawRefreshToken) {
    return ResponseCookie.from(REFRESH_COOKIE, rawRefreshToken == null ? "" : rawRefreshToken)
        .httpOnly(true)
        .secure(props.cookieSecure())
        .sameSite("Strict")
        .path("/api/auth")
        .maxAge(rawRefreshToken == null ? java.time.Duration.ZERO : props.refreshTtl())
        .build()
        .toString();
  }

  @Scheduled(cron = "0 30 3 * * *")
  @Transactional
  public void purgeExpired() {
    refreshTokens.deleteExpired(Instant.now().minus(1, ChronoUnit.DAYS));
  }

  private Issued issue(AppUser user, UUID family) {
    byte[] raw = new byte[32];
    RNG.nextBytes(raw);
    String rawToken = Base64.getUrlEncoder().withoutPadding().encodeToString(raw);
    refreshTokens.save(
        new RefreshToken(
            user.getId(), family, hash(rawToken), Instant.now().plus(props.refreshTtl())));
    return new Issued(accessToken(user), props.accessTtl().toSeconds(), rawToken, user);
  }

  static byte[] hash(String raw) {
    try {
      return MessageDigest.getInstance("SHA-256").digest(raw.getBytes(StandardCharsets.UTF_8));
    } catch (NoSuchAlgorithmException e) {
      throw new IllegalStateException(e);
    }
  }

  public static class InvalidRefreshTokenException extends RuntimeException {
    public InvalidRefreshTokenException() {
      super("Invalid refresh token");
    }
  }
}
