from dataclasses import dataclass


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(slots=True)
class PaginationParams:
    page: int
    page_size: int
    offset: int


def parse_pagination_params(
    page_raw: str | int | None,
    page_size_raw: str | int | None,
    *,
    default_page: int = DEFAULT_PAGE,
    default_page_size: int = DEFAULT_PAGE_SIZE,
    max_page_size: int = MAX_PAGE_SIZE,
) -> PaginationParams:
    try:
        page = int(page_raw or default_page)
    except Exception:
        page = default_page

    try:
        page_size = int(page_size_raw or default_page_size)
    except Exception:
        page_size = default_page_size

    if page < 1:
        page = 1

    if page_size < 1:
        page_size = default_page_size

    if page_size > max_page_size:
        page_size = max_page_size

    return PaginationParams(
        page=page,
        page_size=page_size,
        offset=(page - 1) * page_size,
    )


def build_pagination_context(
    *,
    page: int,
    page_size: int,
    total: int,
) -> dict:
    total_pages = max(1, (total + page_size - 1) // page_size)

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else 1,
        "next_page": page + 1 if page < total_pages else total_pages,
    }