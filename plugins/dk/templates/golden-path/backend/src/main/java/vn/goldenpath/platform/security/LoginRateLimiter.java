package vn.goldenpath.platform.security;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/** 5 failed logins per (ip, email) per 15 minutes. In-memory: fine for a single instance. */
@Component
public class LoginRateLimiter {
  static final int MAX_FAILURES = 5;
  static final Duration WINDOW = Duration.ofMinutes(15);

  private final Map<String, Deque<Instant>> failures = new ConcurrentHashMap<>();

  public boolean isBlocked(String ip, String email) {
    Deque<Instant> q = failures.get(key(ip, email));
    if (q == null) {
      return false;
    }
    synchronized (q) {
      prune(q, Instant.now());
      return q.size() >= MAX_FAILURES;
    }
  }

  public void recordFailure(String ip, String email) {
    Deque<Instant> q = failures.computeIfAbsent(key(ip, email), k -> new ArrayDeque<>());
    synchronized (q) {
      q.addLast(Instant.now());
    }
  }

  public void reset(String ip, String email) {
    failures.remove(key(ip, email));
  }

  @Scheduled(fixedDelay = 900_000)
  void cleanup() {
    Instant now = Instant.now();
    failures
        .entrySet()
        .removeIf(
            e -> {
              synchronized (e.getValue()) {
                prune(e.getValue(), now);
                return e.getValue().isEmpty();
              }
            });
  }

  private static void prune(Deque<Instant> q, Instant now) {
    while (!q.isEmpty() && q.peekFirst().isBefore(now.minus(WINDOW))) {
      q.pollFirst();
    }
  }

  private static String key(String ip, String email) {
    return ip + "|" + (email == null ? "" : email.trim().toLowerCase());
  }
}
