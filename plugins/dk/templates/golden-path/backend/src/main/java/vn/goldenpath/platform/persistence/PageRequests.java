package vn.goldenpath.platform.persistence;

import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;

/** Bounded pagination: page ≥ 0, 1 ≤ size ≤ 100. */
public final class PageRequests {
  public static final int MAX_SIZE = 100;

  private PageRequests() {}

  public static PageRequest of(int page, int size, Sort sort) {
    return PageRequest.of(Math.max(page, 0), Math.min(Math.max(size, 1), MAX_SIZE), sort);
  }
}
