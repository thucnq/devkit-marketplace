package vn.goldenpath.feature.note;

import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import vn.goldenpath.feature.note.dto.NoteRequest;
import vn.goldenpath.feature.note.dto.NoteResponse;
import vn.goldenpath.platform.persistence.PageResponse;

@RestController
@RequestMapping("/api/notes")
@PreAuthorize("hasAnyRole('USER', 'ADMIN')")
class NoteController {

  private final NoteService service;

  NoteController(NoteService service) {
    this.service = service;
  }

  @GetMapping
  PageResponse<NoteResponse> list(
      @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "20") int size) {
    return service.list(page, size);
  }

  @GetMapping("/{id}")
  NoteResponse get(@PathVariable UUID id) {
    return service.get(id);
  }

  @PostMapping
  @ResponseStatus(HttpStatus.CREATED)
  NoteResponse create(@Valid @RequestBody NoteRequest req) {
    return service.create(req);
  }

  @PutMapping("/{id}")
  NoteResponse update(@PathVariable UUID id, @Valid @RequestBody NoteRequest req) {
    return service.update(id, req);
  }

  @DeleteMapping("/{id}")
  @ResponseStatus(HttpStatus.NO_CONTENT)
  void delete(@PathVariable UUID id) {
    service.delete(id);
  }
}
