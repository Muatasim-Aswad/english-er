from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def begin_write(session: AsyncSession) -> None:
    """Acquire SQLite's write reservation before reading a revision precondition."""
    await session.execute(text("BEGIN IMMEDIATE"))
