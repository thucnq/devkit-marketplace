package vn.goldenpath.feature.note;

import java.util.Objects;
import java.util.UUID;
import org.springframework.data.domain.Sort;
import org.springframework.orm.ObjectOptimisticLockingFailureException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import vn.goldenpath.feature.note.dto.NoteRequest;
import vn.goldenpath.feature.note.dto.NoteResponse;
import vn.goldenpath.platform.audit.Audited;
import vn.goldenpath.platform.persistence.PageRequests;
import vn.goldenpath.platform.persistence.PageResponse;
import vn.goldenpath.platform.security.CurrentUser;
import vn.goldenpath.platform.web.NotFoundException;

@Service
public class NoteService {

  private final NoteRepository notes;

  NoteService(NoteRepository notes) {
    this.notes = notes;
  }

  @Transactional(readOnly = true)
  public PageResponse<NoteResponse> list(int page, int size) {
    return PageResponse.of(
        notes.findAllBy(PageRequests.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"))),
        NoteService::toResponse);
  }

  @Transactional(readOnly = true)
  public NoteResponse get(UUID id) {
    return toResponse(find(id));
  }

  @Transactional
  @Audited(action = "NOTE_CREATE", entity = "note")
  public NoteResponse create(NoteRequest req) {
    Note note = notes.save(new Note(req.title(), req.content(), CurrentUser.get().id()));
    notes.flush(); // populate version/timestamps before mapping
    return toResponse(note);
  }

  @Transactional
  @Audited(action = "NOTE_UPDATE", entity = "note")
  public NoteResponse update(UUID id, NoteRequest req) {
    Note note = find(id);
    if (req.version() == null || !Objects.equals(req.version(), note.getVersion())) {
      throw new ObjectOptimisticLockingFailureException(Note.class, id);
    }
    note.update(req.title(), req.content());
    notes.flush();
    return toResponse(note);
  }

  @Transactional
  @Audited(action = "NOTE_DELETE", entity = "note")
  public void delete(UUID id) {
    Note note = find(id);
    CurrentUser me = CurrentUser.get();
    if (!me.hasRole("ADMIN") && !note.getOwnerId().equals(me.id())) {
      throw new AccessDeniedException("not owner");
    }
    notes.delete(note);
  }

  private Note find(UUID id) {
    return notes.findById(id).orElseThrow(() -> new NotFoundException("ghi chú", id));
  }

  private static NoteResponse toResponse(Note n) {
    return new NoteResponse(
        n.getId(),
        n.getTitle(),
        n.getContent(),
        n.getOwnerId(),
        n.getCreatedAt(),
        n.getUpdatedAt(),
        n.getVersion());
  }
}
