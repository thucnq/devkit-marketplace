package vn.goldenpath.feature.note;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.http.HttpHeaders.AUTHORIZATION;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.jayway.jsonpath.JsonPath;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import vn.goldenpath.ApiTestBase;
import vn.goldenpath.platform.security.AppUser;

/** Acceptance tests for docs/acceptance/note.md. One test per AC id. */
class NoteApiTest extends ApiTestBase {

  UUID tenantA;
  UUID tenantB;
  AppUser alice;
  AppUser bob;
  AppUser mallory;

  @BeforeEach
  void setUp() {
    tenantA = newTenant();
    tenantB = newTenant();
    alice = newUser(tenantA, "USER");
    bob = newUser(tenantA, "USER");
    mallory = newUser(tenantB, "USER");
  }

  @Test
  @DisplayName("AC-NOTE-01: Tạo ghi chú → 201, chủ sở hữu là người tạo, có bản ghi audit")
  void createNote() throws Exception {
    String body =
        mvc.perform(
                post("/api/notes")
                    .header(AUTHORIZATION, bearer(alice))
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(json(Map.of("title", "Họp khách hàng", "content", "Chốt phạm vi"))))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.title").value("Họp khách hàng"))
            .andExpect(jsonPath("$.ownerId").value(alice.getId().toString()))
            .andExpect(jsonPath("$.version").value(0))
            .andReturn()
            .getResponse()
            .getContentAsString();
    String id = JsonPath.read(body, "$.id");
    assertThat(auditCount(tenantA, "NOTE_CREATE", id)).isEqualTo(1);
  }

  @Test
  @DisplayName("AC-NOTE-02: Danh sách phân trang, chỉ chứa ghi chú của tenant mình")
  void listIsPaginatedAndTenantScoped() throws Exception {
    createNote(alice, "A1");
    createNote(alice, "A2");
    createNote(bob, "A3");
    createNote(mallory, "B1");
    mvc.perform(get("/api/notes").param("size", "2").header(AUTHORIZATION, bearer(alice)))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.items.length()").value(2))
        .andExpect(jsonPath("$.total").value(3))
        .andExpect(jsonPath("$.size").value(2));
    mvc.perform(get("/api/notes").param("size", "5000").header(AUTHORIZATION, bearer(alice)))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.size").value(100));
  }

  @Test
  @DisplayName("AC-NOTE-03: Cập nhật với version cũ → 409, dữ liệu không đổi")
  void staleUpdateConflicts() throws Exception {
    String id = createNote(alice, "Bản đầu");
    mvc.perform(
            put("/api/notes/" + id)
                .header(AUTHORIZATION, bearer(alice))
                .contentType(MediaType.APPLICATION_JSON)
                .content(json(Map.of("title", "Bản hai", "version", 0))))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.version").value(1));
    mvc.perform(
            put("/api/notes/" + id)
                .header(AUTHORIZATION, bearer(bob))
                .contentType(MediaType.APPLICATION_JSON)
                .content(json(Map.of("title", "Ghi đè", "version", 0))))
        .andExpect(status().isConflict());
    mvc.perform(get("/api/notes/" + id).header(AUTHORIZATION, bearer(alice)))
        .andExpect(jsonPath("$.title").value("Bản hai"));
  }

  @Test
  @DisplayName("AC-NOTE-04: Chỉ chủ sở hữu hoặc ADMIN được xóa; người khác → 403")
  void onlyOwnerOrAdminDeletes() throws Exception {
    String id = createNote(alice, "Của Alice");
    mvc.perform(delete("/api/notes/" + id).header(AUTHORIZATION, bearer(bob)))
        .andExpect(status().isForbidden());
    mvc.perform(delete("/api/notes/" + id).header(AUTHORIZATION, bearer(alice)))
        .andExpect(status().isNoContent());
    assertThat(auditCount(tenantA, "NOTE_DELETE", id)).isEqualTo(1);
    AppUser admin = newUser(tenantA, "ADMIN");
    String other = createNote(bob, "Của Bob");
    mvc.perform(delete("/api/notes/" + other).header(AUTHORIZATION, bearer(admin)))
        .andExpect(status().isNoContent());
  }

  @Test
  @DisplayName("AC-NOTE-05: Không có token → 401")
  void requiresAuthentication() throws Exception {
    mvc.perform(get("/api/notes")).andExpect(status().isUnauthorized());
  }

  @Test
  @DisplayName("AC-NOTE-TENANT: Người dùng tenant khác không đọc/sửa/xóa được (404)")
  void otherTenantSeesNothing() throws Exception {
    String id = createNote(alice, "Bí mật tenant A");
    mvc.perform(get("/api/notes/" + id).header(AUTHORIZATION, bearer(mallory)))
        .andExpect(status().isNotFound());
    mvc.perform(
            put("/api/notes/" + id)
                .header(AUTHORIZATION, bearer(mallory))
                .contentType(MediaType.APPLICATION_JSON)
                .content(json(Map.of("title", "x", "version", 0))))
        .andExpect(status().isNotFound());
    mvc.perform(delete("/api/notes/" + id).header(AUTHORIZATION, bearer(mallory)))
        .andExpect(status().isNotFound());
  }

  @Test
  @DisplayName("AC-NOTE-VALIDATION: Tiêu đề rỗng hoặc > 200 ký tự → 400 kèm lỗi theo trường")
  void validatesInput() throws Exception {
    Map<String, Object> tooLong = new HashMap<>();
    tooLong.put("title", "x".repeat(201));
    tooLong.put("content", "<script>alert(1)</script>");
    mvc.perform(
            post("/api/notes")
                .header(AUTHORIZATION, bearer(alice))
                .contentType(MediaType.APPLICATION_JSON)
                .content(json(tooLong)))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.errors[0].field").value("title"));
    mvc.perform(
            post("/api/notes")
                .header(AUTHORIZATION, bearer(alice))
                .contentType(MediaType.APPLICATION_JSON)
                .content(json(Map.of("title", "  "))))
        .andExpect(status().isBadRequest());
  }

  private String createNote(AppUser user, String title) throws Exception {
    String body =
        mvc.perform(
                post("/api/notes")
                    .header(AUTHORIZATION, bearer(user))
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(json(Map.of("title", title))))
            .andExpect(status().isCreated())
            .andReturn()
            .getResponse()
            .getContentAsString();
    return JsonPath.read(body, "$.id");
  }
}
