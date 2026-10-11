package vn.goldenpath.platform.pii;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import vn.goldenpath.platform.id.Ids;

/**
 * Stores uploaded files that contain personal data (ID scans, biometric images) encrypted at rest
 * on the local volume. Files are small (≤ 10 MB) so whole-file AES-GCM is fine. Back the directory
 * up with the database.
 */
@Component
public class EncryptedFileStore {
  public static final long MAX_BYTES = 10L * 1024 * 1024;

  private final Path root;
  private final PiiCrypto crypto;

  public EncryptedFileStore(@Value("${app.files.dir:./data/files}") String dir, PiiCrypto crypto) {
    this.root = Path.of(dir).toAbsolutePath().normalize();
    this.crypto = crypto;
  }

  public UUID store(InputStream in) {
    try {
      byte[] data = in.readNBytes((int) MAX_BYTES + 1);
      if (data.length > MAX_BYTES) {
        throw new IllegalArgumentException("File exceeds " + MAX_BYTES + " bytes");
      }
      UUID id = Ids.newId();
      Files.createDirectories(root);
      Files.write(path(id), crypto.encrypt(data));
      return id;
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    }
  }

  public byte[] read(UUID id) {
    try {
      return crypto.decrypt(Files.readAllBytes(path(id)));
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    }
  }

  public void delete(UUID id) {
    try {
      Files.deleteIfExists(path(id));
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    }
  }

  private Path path(UUID id) {
    return root.resolve(id + ".bin");
  }
}
