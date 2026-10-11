package vn.goldenpath.feature.note.dto;

import java.time.Instant;
import java.util.UUID;

public record NoteResponse(
    UUID id,
    String title,
    String content,
    UUID ownerId,
    Instant createdAt,
    Instant updatedAt,
    int version) {}
