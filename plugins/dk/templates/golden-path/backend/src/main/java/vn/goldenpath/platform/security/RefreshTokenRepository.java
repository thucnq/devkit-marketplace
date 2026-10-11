package vn.goldenpath.platform.security;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;

public interface RefreshTokenRepository extends JpaRepository<RefreshToken, UUID> {

  Optional<RefreshToken> findByTokenHash(byte[] tokenHash);

  @Modifying
  @Query(
      "update RefreshToken t set t.revokedAt = :now where t.familyId = :family and t.revokedAt is"
          + " null")
  int revokeFamily(UUID family, Instant now);

  @Modifying
  @Query("delete from RefreshToken t where t.expiresAt < :cutoff")
  int deleteExpired(Instant cutoff);
}
