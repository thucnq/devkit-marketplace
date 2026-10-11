package vn.goldenpath.platform.security;

import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface AppUserRepository extends JpaRepository<AppUser, UUID> {

  @Query("select u from AppUser u where lower(u.email) = lower(:email) and u.active = true")
  Optional<AppUser> findActiveByEmail(String email);
}
