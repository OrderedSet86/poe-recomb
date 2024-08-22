import json
import re
import traceback

from termcolor import colored, cprint

from poe_types import *


global_compiled_re = {}


def validateAndReturn(string, regex):
    global global_compiled_re
    
    if regex not in global_compiled_re:
        global_compiled_re[regex] = re.compile(regex)
    fxn = global_compiled_re[regex]
    matches = fxn.findall(string)
    return matches


def validateAndReturnString(string, regex, default=''):
    matches = validateAndReturn(string, regex)
    if matches == []:
        return default
    else:
        return matches[0]


def grabLinesUntilSeparator(lines, index_start, separator):
    assert index_start < len(lines)
    
    captured = []
    for i in range(index_start, len(lines)):
        curr = lines[i]
        if lines[i] == separator:
            break
        else:
            captured.append(curr)
    else:
        i += 1 # Allow for detection of hitting len(lines)
    return captured, i


def parseItem(lines, file_from):
    separator = '--------'
    separator_indices = [i for i, x in enumerate(lines) if x == separator]
    name = ''
    
    try:
        iclass = validateAndReturn(lines[0], r'Item Class: (.*)')[0]
        rarity = validateAndReturn(lines[1], r'Rarity: (.*)')[0]

        if lines[3] == separator:
            # Sometimes there are items with no name, only base plus modifier title
            # eg. "Padded Vest of the Lynx" or "Healthy Copper Plate of the Cloud"
            # It's a bit difficult to figure out the base name in this case, might have to use a dict of known bases
            name = ''
            base = lines[2]
            separator_index = 3
        else:
            name = lines[2]
            base = lines[3]
            separator_index = 4
        
        assert lines[separator_index] == separator

        # Can either be traits or requirements first, have to check
        if lines[separator_index + 1] != 'Requirements:':
            # Traits
            # Critical Strike Chance: 5.00%
            # Attacks per Second: 1.20
            # Weapon Range: 1.1 metres
            # Elemental Damage: 30-50 (augmented)
            trait_lines, separator_index = grabLinesUntilSeparator(lines, separator_index + 1, separator)
            trait_dict = {}
            for raw_trait in trait_lines:
                parts = raw_trait.split(':')
                if len(parts) == 1:
                    # Sometimes the Item Class is here again for some reason.
                    #   In this case it is still traits, but the first line should be ignored
                    continue
                
                trait = parts[0]
                value = validateAndReturn(':'.join(parts[1:]), '[\d\.\-]+%?')[0]

                if '-' in value and value[0] != '-':
                    # Value is a range, eg. "Elemental Damage: 30-50 (augmented)"
                    # For now just average two values
                    lrparts = value.split('-')
                    if len(lrparts) != 2:
                        raise NotImplementedError(f'Unable to parse {raw_trait}')
                    else:
                        left, right = lrparts
                        value = str((float(right) + float(left))/2)
                
                if value.endswith('%'):
                    value = float(value[:-1]) / 100
                else:
                    value = float(value)
                trait_dict[trait] = value
            
            req_index = separator_index + 1
        else:
            trait_dict = {}
            req_index = separator_index + 1

        # Requirements
        assert lines[req_index] == 'Requirements:'
        # Get next lines until separator, then populate known fields
        req_lines, separator_index = grabLinesUntilSeparator(lines, req_index + 1, separator)
        req_obj = PoEReq(0, 0, 0, 0)
        for raw_req in req_lines:
            req, value = raw_req.split(':')
            value = value.split('(')[0]
            setattr(req_obj, req.lower(), int(value))

        # Everything else that's not a modifier
        socket_obj = PoESocket('')
        ilvl = 0
        old_separator_index = separator_index
        while separator_index != separator_indices[-1]:
            old_separator_index = separator_index
            group_lines, separator_index = grabLinesUntilSeparator(lines, separator_index + 1, separator)
            if group_lines[0].startswith('Sockets'):
                sockets = validateAndReturn(group_lines[0], r'Sockets: (.*)')[0].strip(' ')
                socket_obj = PoESocket(sockets)
            elif group_lines[0].startswith('Item Level'):
                ilvl = validateAndReturn(group_lines[0], r'Item Level: (.*)')[0]
                ilvl = int(ilvl)
            elif group_lines[0].startswith('{'):
                # We are on modifiers already
                separator_index = old_separator_index
                break

        # Modifiers
        leftover = False
        final_mods = []
        while separator_index < len(lines):
            modifier_lines, separator_index = grabLinesUntilSeparator(lines, separator_index + 1, separator)

            if not modifier_lines[0].startswith('{'):
                # Some items have final stuff tacked on like "Synthesized Item"
                leftover = True
                break
            
            # Every line that starts with "{" is a modifier start
            # So group lines by modifier
            buffer = []
            modifier_groups = []
            for idx, ml in enumerate(modifier_lines):
                if ml.startswith('{') and len(buffer) > 0:
                    modifier_groups.append(buffer)
                    buffer = []
                buffer.append(ml)
            else:
                modifier_groups.append(buffer)

            for mg in modifier_groups:
                # Some mg examples
                # https://regex101.com/r/kaeAMj/1
                # ['{ Suffix Modifier "of the Apt" (Tier: 1) }', '32% reduced Attribute Requirements', '(Attributes are Strength, Dexterity, and Intelligence)']
                # ['{ Prefix Modifier "Urchin\'s" (Tier: 1) — Life, Defences, Armour }', '+41(33-48) to Armour', '+25(24-28) to maximum Life']
                # ['{ Implicit Modifier — Critical }', '21(20-30)% increased Global Critical Strike Chance (implicit)']
                # ['{ Master Crafted Suffix Modifier "of the Order" — Elemental, Fire, Chaos, Resistance }', '+12(11-12)% to Fire and Chaos Resistances (crafted)']
                # ['{ Eater of Worlds Implicit Modifier (Perfect) — Elemental, Cold, Ailment }', '50(48-50)% reduced Freeze Duration on you (implicit)', 'Eater of Worlds Item']
                
                mod_type = mg[0]
                title = validateAndReturn(mod_type, r'\"(.*)\"') # eg "of the Apt"
                if title:
                    title = title[0]
                else:
                    title = ''
                
                tier = validateAndReturn(mod_type, r'\(Tier: (.*)\)') # eg (Tier: 1)
                if tier:
                    tier = int(tier[0])
                else:
                    tier = 0

                tags = validateAndReturn(mod_type, r'— (.*) }') # eg Elemental, Cold, Ailment
                if tags:
                    tags = tags[0].split(', ')

                category = validateAndReturn(mod_type, r'{ (.*?) [\"\(—\}]')[0] # eg Eater of Worlds Implicit Modifier, Master Crafted Suffix Modifier

                # Effects
                effects = []
                for i, effect_raw_line in enumerate(mg):
                    if i == 0:
                        continue
                    
                    if effect_raw_line.startswith('('):
                        effects[-1].comment_lines.append(effect_raw_line)
                        continue
                    
                    quantity_matches = validateAndReturn(effect_raw_line, r'([\d\.]+)(\([\d\-\.].*?\))?')
                    if len(quantity_matches) == 0:
                        # Some non number modification like "Hits have Culling Strike"
                        effects.append(PoEEffect([], [], effect_raw_line, []))
                    else:
                        # Some number modification like "Adds 20(20-26) to 47(40-47) Physical Damage"
                        # For description, replace number data with X, so output is "Adds X to X Physical Damage"
                        # https://regex101.com/r/05b4zw/1
                        output_description = []
                        last_idx = 0
                        for match in quantity_matches:
                            full_match = ''.join(match)
                            start_index = effect_raw_line.index(full_match)
                            end_index = start_index + len(full_match)
                            if start_index > last_idx:
                                output_description.append(effect_raw_line[last_idx:start_index])
                            output_description.append('X')
                            last_idx = end_index
                        if last_idx < len(effect_raw_line):
                            output_description.append(effect_raw_line[last_idx:])
                        output_description = ''.join(output_description)

                        actual_stats = []
                        ranges = []
                        for match in quantity_matches:
                            st = float(match[0])
                            actual_stats.append(st)
                            if match[1] == '':
                                # eg "32% reduced Attribute Requirements" so no second match
                                ranges.append([st, st])
                            else:
                                range_raw = match[1] # something like (20-26)
                                ranges.append([float(x) for x in range_raw.strip('()').split('-')])
                                
                        effects.append(PoEEffect(
                            actual_stats = actual_stats,
                            ranges = ranges,
                            description = output_description,
                            comment_lines = [],
                        ))

                final_mods.append(PoEMod(
                    category = category,
                    title = title,
                    tier = tier,
                    tags = tags,
                    effects = effects,
                ))

        special_types = []
        if leftover:
            # This is probably something like:
            # Synthesised Item
            # Elder Item
            # Fractured Item

            # Check if normal item; if so, edit
            item_lvl_match = validateAndReturn(modifier_lines[0], r'Item Level: (.*)')
            if item_lvl_match:
                ilvl = int(item_lvl_match[0])
            else:
                special_types = modifier_lines
        
        return PoEItem(
            iclass = iclass,
            rarity = rarity,
            name = name,
            base = base,
            traits = trait_dict,
            req = req_obj,
            sockets = socket_obj,
            ilvl = ilvl,
            mods = final_mods,
            special_types = special_types,
        )

    except Exception as e:
        cprint(f'Error in item "{name}" from "{file_from}"', 'red')
        for line in traceback.format_exception(e):
            cprint(line, 'red')

        return None
        

def getMatchingModIndices(modlist_1, modlist_2):
    matching = []
    for lidx, lm in enumerate(modlist_1):
        for ridx, rm in enumerate(modlist_2):
            all_match = True
            for l_effect in lm.effects:
                for r_effect in rm.effects:
                    if l_effect.description != r_effect.description:
                        all_match = False
                        break
                if not all_match:
                    break
            
            if all_match:
                matching.append([lidx, ridx])

    return matching


def loadRecombsFromFileList(recombination_files_full):
    recombination_files = [p.name for p in recombination_files_full]
    
    recombs = {}
    for full_fpath in recombination_files_full:
        fpath = full_fpath.name
        recombs[fpath] = {}
        
        with open(full_fpath, 'r') as f:
            raw_json = json.load(f)
    
        for item_type in ['input1', 'input2', 'output']:
            raw_item_lines = raw_json[item_type]
            item = parseItem(raw_item_lines, fpath)
            if item is not None:
                recombs[fpath][item_type] = item
    
    # Add "doubled" and "kept" marker to PoEMods
    # This is imperfect as this is a description comparison, not a modgroup comparison ... need to look at poedb later
    for fpath in recombs:
        data = recombs[fpath]
    
        left_mods = data['input1'].mods
        right_mods = data['input2'].mods
        output_mods = data['output'].mods
    
        # Descriptions must match between PoEEffects for the PoEMod to be the same
        # NOTE that this marks implicits as doubled, although "doubled" is not meaningful for implicits (since implicits don't mix - they come from the base)
        lr_matching = getMatchingModIndices(left_mods, right_mods)
        for lidx, ridx in lr_matching:
            data['input1'].mods[lidx].doubled.append([lidx, ridx])
            data['input2'].mods[ridx].doubled.append([lidx, ridx])
    
        lo_matching = getMatchingModIndices(left_mods, output_mods)
        for lidx, oidx in lo_matching:
            data['input1'].mods[lidx].kept.append([lidx, oidx])
    
        ro_matching = getMatchingModIndices(right_mods, output_mods)
        for ridx, oidx in ro_matching:
            data['input2'].mods[ridx].kept.append([ridx, oidx])

    return recombs