from math import ceil


def normalize_page(value, default=1):
    try:
        page = int(value)
        return page if page > 0 else default
    except Exception:
        return default


def normalize_page_size(value, default=25, min_value=10, max_value=100):
    try:
        size = int(value)
        if size < min_value:
            return min_value
        if size > max_value:
            return max_value
        return size
    except Exception:
        return default


def page_meta(total: int, page: int, page_size: int) -> dict:
    total = max(0, int(total or 0))
    page_size = max(1, int(page_size or 1))
    total_pages = max(1, ceil(total / page_size)) if total else 1

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * page_size

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "offset": offset,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else 1,
        "next_page": page + 1 if page < total_pages else total_pages,
        "from_item": (offset + 1) if total > 0 else 0,
        "to_item": min(offset + page_size, total) if total > 0 else 0,
    }