package vn.goldenpath.platform.security;

import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

/** The authenticated caller, read from the access token. Never trust ids from request bodies. */
public record CurrentUser(UUID id, UUID tenantId, Set<String> roles) {

  public static CurrentUser get() {
    Authentication auth = SecurityContextHolder.getContext().getAuthentication();
    if (auth instanceof JwtAuthenticationToken token) {
      Jwt jwt = token.getToken();
      List<String> roles = jwt.getClaimAsStringList("roles");
      return new CurrentUser(
          UUID.fromString(jwt.getSubject()),
          UUID.fromString(jwt.getClaimAsString("tid")),
          roles == null ? Set.of() : Set.copyOf(roles));
    }
    throw new IllegalStateException("No authenticated user");
  }

  public static UUID idOrNull() {
    Authentication auth = SecurityContextHolder.getContext().getAuthentication();
    return auth instanceof JwtAuthenticationToken t
        ? UUID.fromString(t.getToken().getSubject())
        : null;
  }

  public boolean hasRole(String role) {
    return roles.contains(role);
  }
}
