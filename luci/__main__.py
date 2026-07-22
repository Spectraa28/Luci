"""Entrypoints — installed as the `luci` command:

  luci                       chat in the terminal (default)
  luci dashboard             browser cockpit → localhost:7777
  luci voice                 talk to it (needs [voice] extra)
  luci telegram              phone gateway (needs TELEGRAM_BOT_TOKEN)
  luci brief                 morning briefing
  luci skill install <url>   install a community skill
"""

from __future__ import annotations

import sys


def main() -> None:
    args = sys.argv[1:]
    if not args:
        from luci.gateway.cli import main as cli_main
        cli_main()
    elif args[0] == "dashboard":
        from luci.ops.dashboard import main as dash_main
        dash_main()
    elif args[0] == "voice":
        from luci.gateway.voice import main as voice_main
        voice_main()
    elif args[0] == "telegram":
        from luci.gateway.telegram import main as tg_main
        tg_main()
    elif args[0] == "brief":
        from luci.ops.brief import main as brief_main
        brief_main()
    elif args[0] == "skill" and len(args) >= 3 and args[1] == "install":
        from luci.memory.procedural.installer import install
        install(args[2])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
