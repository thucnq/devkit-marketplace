package vn.goldenpath.platform.pii;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonSerializer;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.SerializerProvider;
import com.fasterxml.jackson.databind.introspect.Annotated;
import com.fasterxml.jackson.databind.introspect.JacksonAnnotationIntrospector;
import com.fasterxml.jackson.databind.json.JsonMapper;
import java.io.IOException;

/**
 * Serialises objects for logs and audit with every {@link Pii} value masked. API responses use
 * Spring's normal ObjectMapper and are NOT masked.
 */
public final class PiiMasker {

  private static final ObjectMapper MAPPER =
      JsonMapper.builder()
          .findAndAddModules()
          .disable(SerializationFeature.FAIL_ON_EMPTY_BEANS)
          .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS)
          .annotationIntrospector(
              new JacksonAnnotationIntrospector() {
                @Override
                public Object findSerializer(Annotated a) {
                  return a.hasAnnotation(Pii.class)
                      ? MaskSerializer.class
                      : super.findSerializer(a);
                }
              })
          .build();

  private PiiMasker() {}

  /** "Nguyễn Văn A" → "N***A", "a@b.com" → "a***m", short values → "***". */
  public static String mask(String value) {
    if (value == null) {
      return null;
    }
    String v = value.strip();
    return v.length() <= 4 ? "***" : v.charAt(0) + "***" + v.charAt(v.length() - 1);
  }

  public static String toJson(Object value) {
    try {
      return MAPPER.writeValueAsString(value);
    } catch (JsonProcessingException e) {
      return "\"<unserialisable " + value.getClass().getSimpleName() + ">\"";
    }
  }

  /** Use in toString() of records/classes holding personal data. */
  public static String describe(Object value) {
    return value.getClass().getSimpleName() + toJson(value);
  }

  public static final class MaskSerializer extends JsonSerializer<Object> {
    @Override
    public void serialize(Object value, JsonGenerator gen, SerializerProvider serializers)
        throws IOException {
      gen.writeString(mask(String.valueOf(value)));
    }
  }
}
