package vn.goldenpath.platform.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.http.HttpHeaders.AUTHORIZATION;
import static org.springframework.http.HttpHeaders.SET_COOKIE;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import jakarta.servlet.http.Cookie;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;
import vn.goldenpath.ApiTestBase;

/** Acceptance tests for docs/acceptance/auth.md. */
class AuthApiTest extends ApiTestBase {

  UUID tenant;
  AppUser user;

  @BeforeEach
  void setUp() {
    tenant = newTenant();
    user = newUser(tenant, "USER");
  }

  @Test
  @DisplayName(
      "AC-AUTH-01: Đăng nhập đúng → access token + cookie refresh HttpOnly/SameSite=Strict, có"
          + " audit")
  void loginSucceeds() throws Exception {
    MvcResult r =
        login(user.getEmail(), PASSWORD)
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.accessToken").isNotEmpty())
            .andExpect(jsonPath("$.user.email").value(user.getEmail()))
            .andReturn();
    String cookie = r.getResponse().getHeader(SET_COOKIE);
    assertThat(cookie)
        .contains("rt=")
        .contains("HttpOnly")
        .contains("SameSite=Strict")
        .contains("Path=/api/auth");
    assertThat(auditCount(tenant, "LOGIN", user.getId().toString())).isEqualTo(1);
  }

  @Test
  @DisplayName(
      "AC-AUTH-02: Sai mật khẩu → 401, không lộ email có tồn tại hay không, có audit LOGIN_FAILED")
  void wrongPasswordIsRejected() throws Exception {
    login(user.getEmail(), "wrong-password").andExpect(status().isUnauthorized());
    login("nobody@test.local", "wrong-password").andExpect(status().isUnauthorized());
    assertThat(auditCount(tenant, "LOGIN_FAILED", user.getId().toString())).isEqualTo(1);
  }

  @Test
  @DisplayName(
      "AC-AUTH-03: Sai 5 lần trong 15 phút → lần tiếp theo bị chặn 429 kể cả đúng mật khẩu")
  void bruteForceIsThrottled() throws Exception {
    for (int i = 0; i < 5; i++) {
      login(user.getEmail(), "wrong-" + i).andExpect(status().isUnauthorized());
    }
    login(user.getEmail(), PASSWORD).andExpect(status().isTooManyRequests());
  }

  @Test
  @DisplayName(
      "AC-AUTH-04: Refresh xoay vòng token: cookie mới khác cookie cũ, access token mới hợp lệ")
  void refreshRotates() throws Exception {
    String rt1 = refreshCookie(login(user.getEmail(), PASSWORD).andReturn());
    MvcResult r =
        mvc.perform(post("/api/auth/refresh").cookie(new Cookie("rt", rt1)))
            .andExpect(status().isOk())
            .andReturn();
    String rt2 = refreshCookie(r);
    assertThat(rt2).isNotBlank().isNotEqualTo(rt1);
    String access =
        com.jayway.jsonpath.JsonPath.read(r.getResponse().getContentAsString(), "$.accessToken");
    mvc.perform(get("/api/auth/me").header(AUTHORIZATION, "Bearer " + access))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.id").value(user.getId().toString()));
  }

  @Test
  @DisplayName(
      "AC-AUTH-05: Dùng lại refresh token cũ → 401 và thu hồi cả phiên (token mới cũng hết hiệu"
          + " lực)")
  void refreshReuseRevokesFamily() throws Exception {
    String rt1 = refreshCookie(login(user.getEmail(), PASSWORD).andReturn());
    String rt2 =
        refreshCookie(
            mvc.perform(post("/api/auth/refresh").cookie(new Cookie("rt", rt1))).andReturn());
    mvc.perform(post("/api/auth/refresh").cookie(new Cookie("rt", rt1)))
        .andExpect(status().isUnauthorized());
    mvc.perform(post("/api/auth/refresh").cookie(new Cookie("rt", rt2)))
        .andExpect(status().isUnauthorized());
  }

  @Test
  @DisplayName("AC-AUTH-06: Đăng xuất → cookie bị xóa, refresh token không dùng lại được")
  void logoutRevokes() throws Exception {
    String rt = refreshCookie(login(user.getEmail(), PASSWORD).andReturn());
    MvcResult r =
        mvc.perform(post("/api/auth/logout").cookie(new Cookie("rt", rt)))
            .andExpect(status().isNoContent())
            .andReturn();
    assertThat(r.getResponse().getHeader(SET_COOKIE)).contains("Max-Age=0");
    mvc.perform(post("/api/auth/refresh").cookie(new Cookie("rt", rt)))
        .andExpect(status().isUnauthorized());
  }

  private org.springframework.test.web.servlet.ResultActions login(String email, String password)
      throws Exception {
    return mvc.perform(
        post("/api/auth/login")
            .contentType(MediaType.APPLICATION_JSON)
            .content(json(Map.of("email", email, "password", password))));
  }

  private static String refreshCookie(MvcResult r) {
    String header = r.getResponse().getHeader(SET_COOKIE);
    assertThat(header).as("Set-Cookie").isNotNull();
    return header.substring(header.indexOf("rt=") + 3, header.indexOf(';'));
  }
}
