import itertools
import os
import random
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from termcolor import colored, cprint

from poe_types import *
from utils import loadRecombsFromFileList


# Load historical recombs for easier item bases and recomb data
json_dir = Path().parent / 'data/json'
recombination_files = sorted(os.listdir(json_dir))
recombination_files_full = [json_dir / name for name in recombination_files]
recombs = loadRecombsFromFileList(recombination_files_full)

# Calculate pool size before_after
before_after = defaultdict(list)
for fpath in recombination_files:
    data = recombs[fpath]
    countSlots = lambda item, slot: sum([m.getSlot() == slot for m in item.mods])
    input_prefix_count = countSlots(data['input1'], 'Prefix') + countSlots(data['input2'], 'Prefix')
    input_suffix_count = countSlots(data['input1'], 'Suffix') + countSlots(data['input2'], 'Suffix')
    output_prefix_count = countSlots(data['output'], 'Prefix')
    output_suffix_count = countSlots(data['output'], 'Suffix')
    
    before_after[input_prefix_count].append(output_prefix_count)
    before_after[input_suffix_count].append(output_suffix_count)

# Put it in a frequency version to make it simpler
bafreq = {}
for in_pool in sorted(list(before_after.keys())): 
    freq = Counter(before_after[in_pool])
    total = freq.total()
    bafreq[in_pool] = {outcome: round(num/total,  3) for outcome, num in freq.items()}

# Recomb crafting methods
junk_prefix_dict = {
    'category': 'Prefix',
    'title': '',
    'tier': -1,
    'tags': [],
    'effects': [PoEEffect(**
        {
            'actual_stats': [],
            'ranges': [],
            'description': 'Junk Prefix',
            'comment_lines': [],
        }
    )],
}
junk_suffix_dict = deepcopy(junk_prefix_dict)
junk_suffix_dict['category'] = 'Suffix'
junk_suffix_dict['effects'][0].description = 'Junk Suffix'


def check_recombineItems(item1, item2, valuable_mods):
    if len(valuable_mods) == 0:
        return (False, 'No valuable mods so no point recombining')    
    # if len(item1.valuable_mod_indices) == 0 or len(item2.valuable_mod_indices) == 0:
    #     # Technically this could work as a worse Fenumal Plagued Arachnid, maybe should turn off later
    #     return (False, 'No valuables on left or right')
    return (True, '')


def recombineItems(item1, item2, valuable_mods):
    input_pools = {
        'Prefix': item1.getPrefixes() + item2.getPrefixes(),
        'Suffix': item1.getSuffixes() + item2.getSuffixes(),
    }

    # Assume no weighting, doubling, modgrouping, or influence requirements for v1 to make things simpler
    # TODO: Make a separate before_after table for doubled and non doubled
    # TODO: Average ilvl
    
    # Generate outcomes for individual pools
    pool_output_mod_chances = defaultdict(list)
    for pool_type, mod_pool in input_pools.items():
        for outcome, pc in bafreq[len(mod_pool)].items():
            N = outcome
            possible_mod_combos = list(itertools.combinations(range(len(mod_pool)), N))
            pool_output_mod_chances[pool_type].extend(
                [(pc / len(possible_mod_combos), x) for x in possible_mod_combos]
            )
    # display(pool_output_mod_chances)
    
    # Combine modpools into final output item
    final_output_mod_chances = []
    for prefix_outcome in pool_output_mod_chances['Prefix']:
        for suffix_outcome in pool_output_mod_chances['Suffix']:
            ppc, prefix_pool = prefix_outcome
            spc, suffix_pool = suffix_outcome
            final_output_mod_chances.append((ppc * spc, (prefix_pool, suffix_pool)))

    # display(final_output_mod_chances)

    # Pick each base for every output chance (so doubling the number of output states)
    item_output_chances = []
    for pc, mod_outcome in final_output_mod_chances:
        for i in range(0, 2):
            item_output_chances.append((i, pc/2, mod_outcome))

    # display(item_output_chances[:10])
    # print(len(item_output_chances))
    
    # The final output chances is a huge list (eg ~280 for (2,2) + (1,3)), so simplify down to "valuable" and "junk" modifiers
    # If "valuable" modifiers drop below a certain tier, they are considered junk now
    # TODO: This may not work after doubling is implemented (if doubling doesn't naturally happen)

    # Get valuable indices for each pool
    valuable_indices = defaultdict(set)
    for pool_type, mod_pool in input_pools.items():
        for i, m in enumerate(mod_pool):
            for vm in valuable_mods:
                if m.stringDescription() == vm.description and m.tier <= vm.min_tier:
                    valuable_indices[pool_type].add(i)

    # Convert states to final mod + placeholder junk mods - hopefully this reduces the number of states to consider
    output_to_percent = Counter()
    for item_base_index, output_prob, mod_pair_indices in item_output_chances:
        output_prefix_pool, output_suffix_pool = mod_pair_indices

        compressed_prefix_pool = tuple(
            sorted((
                (input_pools['Prefix'][m] if m in valuable_indices['Prefix'] else PoEMod(**junk_prefix_dict))
                for m in output_prefix_pool
            ), key=lambda mod: mod.stringDescription())
        )
        compressed_suffix_pool = tuple(
            sorted((
                (input_pools['Suffix'][m] if m in valuable_indices['Suffix'] else PoEMod(**junk_suffix_dict))
                for m in output_suffix_pool
            ), key=lambda mod: mod.stringDescription())
        )
        
        compressed_state = (
            item_base_index,
            compressed_prefix_pool,
            compressed_suffix_pool,
        )
        output_to_percent[compressed_state] += output_prob

    return output_to_percent


def pprintRecombinatorOutcomes(output_to_percent, valuable_inputs, compression_level = 1):
    # print('Relevant outcomes:', len(output_to_percent))
    
    # For now, compress different bases into a single item
    user_outcomes = Counter()
    for state, percent in list(output_to_percent.items()):
        ps_short = (len(state[1]), len(state[2]))
        user_state = (
            ps_short,
            tuple(sorted([m.stringDescription() for m in state[1] if not m.stringDescription().startswith('Junk')])),
            tuple(sorted([m.stringDescription() for m in state[2] if not m.stringDescription().startswith('Junk')])),
        )

        if compression_level == 0:
            print(f'{round(percent*100, 2)}% {ps_short}')
            for pool_idx in range(1, 3):
                for m in state[pool_idx]:
                    print(m.stringDescription())
            print()
        
        user_outcomes[user_state] += percent


    level2_outcomes = Counter()
    level3_prefix_suffix = {}
    for outcome, percent in sorted(user_outcomes.items(), key=lambda x: x[1], reverse=True):
        ps_short = outcome[0]
        
        valuables = len(outcome[1]) + len(outcome[2])
        valuable_score = valuables - max(valuable_inputs) # Number of mods lost relative to parent inputs
        if valuable_score < 0 or valuables == 0:
            goodness = 'red'
        if valuable_score == 0:
            goodness = 'yellow'
        if valuable_score > 0:
            goodness = 'green'

        if goodness not in level3_prefix_suffix:
            level3_prefix_suffix[goodness] = defaultdict(float)
        level3_prefix_suffix[goodness][ps_short] += percent

        level2_state = (
            goodness,
            *outcome[1:]
        )
        level2_outcomes[level2_state] += percent
        
        if compression_level == 1:
            cprint(f'{round(percent*100, 2)}% {ps_short}', goodness)
            for sm in outcome[1]:
                print(f'(Prefix) {sm}')
            for sm in outcome[2]:
                print(f'(Suffix) {sm}')
            print()
    
    level3_outcomes = Counter()
    for outcome, percent in sorted(level2_outcomes.items(), key=lambda x: x[1], reverse=True):
        goodness = outcome[0]
        valuables = len(outcome[1]) + len(outcome[2])

        if valuables == 0:
            level3_outcomes['BRICK'] += percent
        else:
            level3_outcomes[goodness] += percent
        
        if compression_level == 2:
            cprint(f'{round(percent*100, 2)}%', goodness)
            for sm in outcome[1]:
                print(f'(Prefix) {sm}')
            for sm in outcome[2]:
                print(f'(Suffix) {sm}')
            if valuables == 0:
                cprint('BRICK', 'red', attrs=['bold'])
            print()

    if compression_level == 3:
        messages = {
            'red': 'Lose mods',
            'yellow': 'Stay max mods',
            'green': 'Gain mods',
            'BRICK': 'BRICK',
        }
        for goodness, percent in sorted(level3_outcomes.items(), key=lambda x: x[1], reverse=True):
            pcstr = round(percent * 100, 1)

            color = goodness
            if goodness == 'BRICK':
                color = 'red'
            cprint(f'{messages[goodness]}: {pcstr}%', color)
            
            if goodness != 'BRICK':
                for ps_short, ps_percent in sorted(level3_prefix_suffix[goodness].items(), key=lambda x: x[1], reverse=True):
                    print('   ', ps_short, f'{str(round(ps_percent * 100, 1)).rjust(5)}%')

        # display(level3_prefix_suffix)


@dataclass
class ValuableMod:
    description: str
    min_tier: int
