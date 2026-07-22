"""
CLI gateway - default 'luci' command 

A tight REPL: type a message , get a reply , watch tool calls inline.
"""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown

console =  Console()

def _observer(kind: str , ev:dict) -> None:
    if kind == "gate":
        icon = "🔍" if ev.get("decision") == "retrieve" else "⏭"
        console.print(f"  {icon} memory gate: {ev.get('decision')} — {ev.get('reason', '')}", style="dim")
    elif kind == "tool":
        console.print(f"  🔧 {ev['tool']}({ev['args']}) → {str(ev['output'])[:120]}", style="dim cyan")
    elif kind == "consolidation":
        console.print(f"  💾 consolidated → {ev['new_facts']} new facts", style="dim green")
        
def main() -> None:
    from luci.app import luci
    
    luci = luci()
    console.print("\n[bold]luci[/bold] - your local second brain . Type [dim]exit[/dim] to quit. \n")
    
    while True:
        try:
            user_input = console.input("[bold green]you[/bold green] , ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nBye")
        
        
        if not user_input:
            continue
        if user_input.lower() in ("exit","quit","q"):
            console.print("Bye")
            break
        
        result = luci.respond(user_input,observer=_observer,source="cli")
        console.print(f"\n [bold blue]luci[/bold blue] > ",end="")
        console.print(Markdown(result.reply))
        console.print()
    