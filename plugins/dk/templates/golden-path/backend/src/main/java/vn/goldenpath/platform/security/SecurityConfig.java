package vn.goldenpath.platform.security;

import com.nimbusds.jose.jwk.source.ImmutableSecret;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.oauth2.server.resource.authentication.JwtGrantedAuthoritiesConverter;
import org.springframework.security.oauth2.server.resource.web.authentication.BearerTokenAuthenticationFilter;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.HttpStatusEntryPoint;
import vn.goldenpath.platform.tenant.TenantFilter;

/**
 * Stateless API secured by our own HS256 access tokens. Default deny: anything not in PUBLIC_PATHS
 * needs a valid token, and endpoints add @PreAuthorize for roles.
 */
@Configuration
@EnableMethodSecurity
public class SecurityConfig {

  public static final String[] PUBLIC_PATHS = {
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/actuator/health/**",
    "/v3/api-docs/**",
    "/swagger-ui/**",
    "/oauth2/**",
    "/login/oauth2/**",
    "/error"
  };

  @Bean
  SecurityFilterChain api(
      HttpSecurity http,
      GoogleLoginSuccessHandler googleSuccess,
      AppSecurityProperties props,
      ObjectProvider<ClientRegistrationRepository> oauthClients)
      throws Exception {
    http.csrf(c -> c.disable()) // no cookie-authenticated endpoints except SameSite=Strict refresh
        .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .authorizeHttpRequests(
            a -> a.requestMatchers(PUBLIC_PATHS).permitAll().anyRequest().authenticated())
        .oauth2ResourceServer(o -> o.jwt(j -> j.jwtAuthenticationConverter(jwtAuthConverter())))
        .exceptionHandling(
            e -> e.authenticationEntryPoint(new HttpStatusEntryPoint(HttpStatus.UNAUTHORIZED)))
        .addFilterAfter(new TenantFilter(), BearerTokenAuthenticationFilter.class);
    if (oauthClients.getIfAvailable() != null) {
      http.oauth2Login(
          o ->
              o.successHandler(googleSuccess)
                  .failureHandler(
                      (req, res, ex) ->
                          res.sendRedirect(props.frontendUrl() + "/login?error=sso_failed")));
    }
    return http.build();
  }

  @Bean
  PasswordEncoder passwordEncoder() {
    return PasswordEncoderFactories.createDelegatingPasswordEncoder();
  }

  @Bean
  JwtEncoder jwtEncoder(AppSecurityProperties props) {
    return new NimbusJwtEncoder(new ImmutableSecret<>(props.jwtKey()));
  }

  @Bean
  JwtDecoder jwtDecoder(AppSecurityProperties props) {
    NimbusJwtDecoder decoder =
        NimbusJwtDecoder.withSecretKey(props.jwtKey()).macAlgorithm(MacAlgorithm.HS256).build();
    decoder.setJwtValidator(JwtValidators.createDefaultWithIssuer(props.issuer()));
    return decoder;
  }

  private static JwtAuthenticationConverter jwtAuthConverter() {
    JwtGrantedAuthoritiesConverter roles = new JwtGrantedAuthoritiesConverter();
    roles.setAuthoritiesClaimName("roles");
    roles.setAuthorityPrefix("ROLE_");
    JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
    converter.setJwtGrantedAuthoritiesConverter(roles);
    return converter;
  }
}
