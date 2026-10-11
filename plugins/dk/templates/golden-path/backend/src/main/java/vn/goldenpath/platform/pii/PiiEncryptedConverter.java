package vn.goldenpath.platform.pii;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;
import java.nio.charset.StandardCharsets;

/**
 * Usage: {@code @Pii @Convert(converter = PiiEncryptedConverter.class) private String cccd;} on a
 * bytea column.
 */
@Converter
public class PiiEncryptedConverter implements AttributeConverter<String, byte[]> {

  @Override
  public byte[] convertToDatabaseColumn(String attribute) {
    return attribute == null
        ? null
        : PiiCrypto.get().encrypt(attribute.getBytes(StandardCharsets.UTF_8));
  }

  @Override
  public String convertToEntityAttribute(byte[] dbData) {
    return dbData == null
        ? null
        : new String(PiiCrypto.get().decrypt(dbData), StandardCharsets.UTF_8);
  }
}
