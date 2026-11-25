"""Asset handlers: one per segment type.

A handler knows how to turn a byte range of the ROM into editable files
(``extract``) and how to put those files back (``build``). It never knows an
address: offsets arrive with the ``Segment``. Passthrough types (code, data,
free, unknown) are copied out for browsing but taken from the base ROM on
build unless a local file overrides them. ``patch`` segments are generated
from ``ga3.patches`` and hook into code elsewhere.
"""

from __future__ import annotations

from .base import BuildError, Handler, Paths
from .header import HeaderHandler
from .nemesis_asset import FontArtHandler, NemesisHandler
from .palette_asset import PaletteHandler
from .patch_asset import PatchHandler
from .raw_asset import RawHandler
from .table_asset import TableHandler
from .text_asset import EmbeddedTextHandler, TextHandler
from .tiles_asset import TilesHandler

HANDLERS: dict[str, Handler] = {
    "header": HeaderHandler(),
    "nemesis": NemesisHandler(),
    "text": TextHandler(),
    "table": TableHandler(),
    "palette": PaletteHandler(),
    "tiles4bpp": TilesHandler(),
    "pcm": RawHandler(committed=True),
    "raw": RawHandler(committed=True),
    "code": RawHandler(committed=False),
    "data": RawHandler(committed=False),
    "unknown": RawHandler(committed=False),
    "free": RawHandler(committed=False, is_free=True),
    "patch": PatchHandler(),
}

_FONT = FontArtHandler()
_EMBEDDED_TEXT = EmbeddedTextHandler()


def handler_for(seg) -> Handler:
    if seg.type == "nemesis" and seg.get("format") == "font_art":
        return _FONT
    if seg.type in ("code", "data") and seg.get("strings") is not None:
        return _EMBEDDED_TEXT
    try:
        return HANDLERS[seg.type]
    except KeyError:
        raise BuildError(f"{seg}: no handler for type {seg.type!r}") from None


__all__ = ["HANDLERS", "BuildError", "Handler", "Paths", "handler_for"]
