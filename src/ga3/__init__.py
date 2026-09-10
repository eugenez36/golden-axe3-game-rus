"""ga3 -- ROM-hacking toolkit for Golden Axe III (Sega Mega Drive).

Targets the NEWGAME 2003 Russian translation. The package takes the cartridge
image apart into editable assets (``ga3 extract``), rebuilds it byte-for-byte
(``ga3 build``) and proves the result (``ga3 verify``). Every ROM offset lives
in ``rom_map.yml``; the code here only knows formats, never addresses.
"""

__version__ = "0.3.5"
