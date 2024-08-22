import json
import os

from termcolor import cprint

from simulator import recombineItems, pprintRecombinatorOutcomes, ValuableMod
from utils import parseItem


def getUntilEOF():
    lines = []
    while True:
        try:
            lines.append(input())
        except EOFError:
            break
    return lines


if __name__ == '__main__':
    valuable_mods = [
        ValuableMod('X% increased Physical Damage|+X to Accuracy Rating', 4),
        ValuableMod('X% increased Physical Damage', 3),
        ValuableMod('Socketed Gems are supported by Level X Multistrike — Unscalable Value|X% increased Attack Speed', 2),
        ValuableMod('X% increased Physical Damage|Hits with this Weapon have Culling Strike against Bleeding Enemies — Unscalable Value', 1),
        ValuableMod('+X% to Damage over Time Multiplier for Bleeding from Hits with this Weapon', 2),
        ValuableMod('Adds X to X Physical Damage', 2),
        ValuableMod('X% increased Attack Speed', 4),
        ValuableMod('+X% to Damage over Time Multiplier', 2),
        ValuableMod('Socketed Gems are Supported by Level X Brutality — Unscalable Value|X% increased Physical Damage', 1),
        ValuableMod('Socketed Gems are Supported by Level X Melee Physical Damage — Unscalable Value|X% increased Physical Damage', 1),
        ValuableMod('Socketed Gems are Supported by Level X Ruthless — Unscalable Value|X% increased Physical Damage', 1)
    ]
    
    existing_json_files = sorted(os.listdir('data/json'))
    if existing_json_files:
        max_count_fname = existing_json_files[-1]
        max_count = int(max_count_fname.split('.')[0])
    else:
        max_count = 0

    while True:
        # Get user data
        cprint('Left Input (Alt+Ctrl+C -> Ctrl+V -> Ctrl+D):', 'green')
        input1 = getUntilEOF()
        cprint('-----------------------------------------------------------------------------', 'blue')
        cprint('Right Input (Alt+Ctrl+C -> Ctrl+V -> Ctrl+D):', 'blue')
        input2 = getUntilEOF()

        item1 = parseItem(input1, 'REPL')
        item2 = parseItem(input2, 'REPL')
        
        output_to_percent = recombineItems(item1, item2, valuable_mods)
        pprintRecombinatorOutcomes(
            output_to_percent,
            (
                item1.getValuableCount(valuable_mods),
                item2.getValuableCount(valuable_mods),
            ),
            compression_level=3
        )
        
        cprint('-----------------------------------------------------------------------------', 'yellow')
        cprint('Output (Alt+Ctrl+C -> Ctrl+V -> Ctrl+D):', 'yellow')
        output = getUntilEOF()
        cprint('-----------------------------------------------------------------------------', 'red')

        # Store in JSON file (for now)
        storage_fname = f'data/json/{str(max_count+1).zfill(5)}.json'
        with open(storage_fname, 'w') as f:
            json.dump({'input1': input1, 'input2': input2, 'output': output}, f, indent=2)
        
        max_count += 1
        