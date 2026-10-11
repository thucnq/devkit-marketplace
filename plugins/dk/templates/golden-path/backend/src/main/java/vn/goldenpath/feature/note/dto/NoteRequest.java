package vn.goldenpath.feature.note.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** version is required on update (optimistic locking), ignored on create. */
public record NoteRequest(
    @NotBlank @Size(max = 200) String title, @Size(max = 10_000) String content, Integer version) {}
