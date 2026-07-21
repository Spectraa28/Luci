"""
the LOOP - Observe --> reason --> act --> repeat.

Every agent framework is ultimately this while-loop:
         
         while not done:
            response = llm(message, tools)
            if response asks for tools:
                results = run(tool_calls)
                message += results
            else:
                done
"""

from __future__ import annotations

from dataclasses import dataclass , field
from typing import Any , Callable


from google import genai
from google.genai import types



from Luci.tools.registry import ToolRegistry

LoopEvent = dict[str,Any]
Observer = Callable[[str,LoopEvent],None]

@dataclass
class LoopResult:
    reply: str
    tool_call: list[LoopEvent] = field(default_factory=list)
    iteration: int = 0
    
def run_loop(
    client:genai.Client,
    model:str,
    system:str,
    messages:list[types.Content],
    tools:ToolRegistry,
    max_iteration:int=10,
    max_tokens:int = 2048,
    observer: Observer| None=None,
    stream:bool = False,
) -> LoopResult:
    notify = observer or (lambda kind, ev: None)
    result = LoopResult(reply="")
    
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=tools.gemini_schemas(),
        max_output_tokens=max_tokens
    )
    
    for iterations in range(1,max_iteration+1):
        result.iteration = iterations
        
        # --- calling the model -----
        if stream:
            collected_parts: list[types.Part] = []
            with client.models.generate_content_stream(
                model=model,
                contents=messages,
                config=config
            ) as s:
                for chunk in s :
                    for part in (chunk.candidates[0].content_parts or []):
                        if part.text:
                            notify("text", {"delta": part.text})
                        collected_parts.append(part)
            response_parts = collected_parts
            finish_reason = "STOP"
        else:
            response = client.models.generate_content(
                model=model,
                contents=messages,
                config=config
            )
            response_parts = response.candidates[0].content_parts or []
            finish_reason = str(response.canditates[0].finish_reason)
        
        notify("llm",{"iteration":iterations,"finish_reason":finish_reason})
        
        messages.append(types.ModelContent(parts=response_parts))
        
        tool_calls = [p for p in response_parts if p.function_call]
        if not tool_calls: 
            result.reply = "".join(p.text for p in response_parts if p.text)
            return result

        result_parts: list[types.Part] = []
        for part in tool_calls:
            fc = part.function_call
            args = dict(fc.args  or {})
            output = tools.execute(fc.name,args)
            
            event = {"tool": fc.name, "args": args,"output":  output}
            result.tool_call.append(event)
            notify("tool",event)
            
            result_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        id=fc.id,
                        name=fc.name,
                        response={"result":output},
                    )
                )
            )
        
        messages.append(types.UserContent(parts=result_parts))
    
    result.reply = "(I hit my iteration limit before finishing -  try breaking the request into smaller steps)"
    return result