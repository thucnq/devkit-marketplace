package vn.goldenpath.platform.security;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import vn.goldenpath.platform.audit.AuditService;
import vn.goldenpath.platform.pii.Pii;
import vn.goldenpath.platform.pii.PiiMasker;
import vn.goldenpath.platform.tenant.TenantContext;
import vn.goldenpath.platform.web.ApiException;

@RestController
@RequestMapping("/api/auth")
class AuthController {

  record LoginRequest(
      @Pii @NotBlank @Email @Size(max = 320) String email,
      @NotBlank @Size(max = 200) String password) {}

  record UserView(UUID id, UUID tenantId, String email, String fullName, List<String> roles) {
    static UserView of(AppUser u) {
      return new UserView(u.getId(), u.getTenantId(), u.getEmail(), u.getFullName(), u.roleList());
    }
  }

  record TokenResponse(String accessToken, long expiresIn, UserView user) {}

  private final AppUserRepository users;
  private final PasswordEncoder passwordEncoder;
  private final TokenService tokens;
  private final LoginRateLimiter limiter;
  private final AuditService audit;
  private final String dummyHash;

  AuthController(
      AppUserRepository users,
      PasswordEncoder passwordEncoder,
      TokenService tokens,
      LoginRateLimiter limiter,
      AuditService audit) {
    this.users = users;
    this.passwordEncoder = passwordEncoder;
    this.tokens = tokens;
    this.limiter = limiter;
    this.audit = audit;
    this.dummyHash = passwordEncoder.encode("timing-equaliser");
  }

  @PostMapping("/login")
  ResponseEntity<TokenResponse> login(
      @Valid @RequestBody LoginRequest req, HttpServletRequest http) {
    String ip = http.getRemoteAddr();
    if (limiter.isBlocked(ip, req.email())) {
      throw new ApiException(
          HttpStatus.TOO_MANY_REQUESTS, "Đăng nhập sai quá nhiều lần, thử lại sau 15 phút.");
    }
    Optional<AppUser> found = users.findActiveByEmail(req.email());
    String hash = found.map(AppUser::getPasswordHash).orElse(null);
    boolean ok =
        passwordEncoder.matches(req.password(), hash != null ? hash : dummyHash) && hash != null;
    UUID tenant = found.map(AppUser::getTenantId).orElse(null);
    if (!ok) {
      limiter.recordFailure(ip, req.email());
      TenantContext.runAs(
          tenant,
          () ->
              audit.record(
                  "LOGIN_FAILED",
                  "user",
                  found.map(u -> u.getId().toString()).orElse(null),
                  Map.of("email", PiiMasker.mask(req.email()), "ip", ip)));
      throw new BadCredentialsException("Email hoặc mật khẩu không đúng.");
    }
    limiter.reset(ip, req.email());
    AppUser user = found.get();
    TokenService.Issued issued =
        TenantContext.callAs(
            tenant,
            () -> {
              audit.record("LOGIN", "user", user.getId().toString(), Map.of("ip", ip));
              return tokens.issue(user);
            });
    return withCookie(issued);
  }

  @PostMapping("/refresh")
  ResponseEntity<TokenResponse> refresh(
      @CookieValue(name = TokenService.REFRESH_COOKIE, required = false) String rt) {
    if (rt == null || rt.isBlank()) {
      throw new TokenService.InvalidRefreshTokenException();
    }
    return withCookie(tokens.refresh(rt));
  }

  @PostMapping("/logout")
  ResponseEntity<Void> logout(
      @CookieValue(name = TokenService.REFRESH_COOKIE, required = false) String rt) {
    if (rt != null && !rt.isBlank()) {
      tokens.revoke(rt);
    }
    return ResponseEntity.noContent()
        .header(HttpHeaders.SET_COOKIE, tokens.refreshCookie(null))
        .build();
  }

  @GetMapping("/me")
  UserView me() {
    return users
        .findById(CurrentUser.get().id())
        .map(UserView::of)
        .orElseThrow(() -> new BadCredentialsException("User no longer exists"));
  }

  private ResponseEntity<TokenResponse> withCookie(TokenService.Issued issued) {
    return ResponseEntity.ok()
        .header(HttpHeaders.SET_COOKIE, tokens.refreshCookie(issued.refreshToken()))
        .body(
            new TokenResponse(
                issued.accessToken(), issued.expiresIn(), UserView.of(issued.user())));
  }
}
