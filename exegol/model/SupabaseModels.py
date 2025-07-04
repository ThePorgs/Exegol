import datetime
from typing import Optional

from pydantic import BaseModel


class SupabaseImage(BaseModel):
    """Supabase public Images Schema."""

    # Digests
    digest: str
    repo_digest: str

    # Columns
    tag: str
    arch: str
    build_date: datetime.datetime
    disk_size: float
    download_size: Optional[float]
    repository: str
    version: str
    license: Optional[str]
