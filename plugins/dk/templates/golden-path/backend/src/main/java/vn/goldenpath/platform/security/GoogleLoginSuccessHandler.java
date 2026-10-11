package vn.goldenpath.platform.security;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import java.io.IOException;
import java.util.Map;
import java.util.Optional;
import org.springframework.http.HttpHeaders;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.stereotype.Component;
import vn.goldenpath.platform.audit.AuditService;
import vn.goldenpath.platform.tenant.TenantContext;

/**
 * Google SSO: only users already provisioned in a tenant may sign in (no auto sign-up). On success
 * we set the refresh cookie and send the browser to the SPA, which calls /api/auth/refresh.
 */
@Component
class GoogleLoginSuccessHandler implements AuthenticationSuccessHandler {

  private final AppUserRepository users;
  private final TokenService tokens;
  private final AuditService audit;
  private final AppSecurityProperties props;

  GoogleLoginSuccessHandler(
      AppUserRepository users,
      TokenService tokens,
      AuditService audit,
      AppSecurityProperties props) {
    this.users = users;
    this.tokens = tokens;
    this.audit = audit;
    this.props = props;
  }

  @Override
  public void onAuthenticationSuccess(
      HttpServletRequest request, HttpServletResponse response, Authentication authentication)
      throws IOException {
    HttpSession session = request.getSession(false);
    if (session != null) {
      session.invalidate(); // the session only carried OAuth state; the API stays stateless
    }
    Optional<AppUser> user = Optional.empty();
    if (authentication.getPrincipal() instanceof OidcUser oidc
        && Boolean.TRUE.equals(oidc.getEmailVerified())
        && oidc.getEmail() != null) {
      user = users.findActiveByEmail(oidc.getEmail());
    }
    if (user.isEmpty()) {
      response.sendRedirect(props.frontendUrl() + "/login?error=sso_not_invited");
      return;
    }
    AppUser u = user.get();
    TokenService.Issued issued =
        TenantContext.callAs(
            u.getTenantId(),
            () -> {
              audit.record("LOGIN", "user", u.getId().toString(), Map.of("method", "google"));
              return tokens.issue(u);
            });
    response.addHeader(HttpHeaders.SET_COOKIE, tokens.refreshCookie(issued.refreshToken()));
    response.sendRedirect(props.frontendUrl() + "/auth/callback");
  }
}
