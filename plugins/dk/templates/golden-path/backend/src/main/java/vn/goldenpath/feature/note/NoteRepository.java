package vn.goldenpath.feature.note;

import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

/** No tenant filter needed in queries: Postgres RLS scopes every statement to the tenant. */
interface NoteRepository extends JpaRepository<Note, UUID> {
  Page<Note> findAllBy(Pageable pageable);
}
