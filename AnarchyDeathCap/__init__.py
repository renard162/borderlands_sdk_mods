from dataclasses import dataclass, fields

from mods_base import build_mod, get_pc, hook, HookType, SliderOption, BoolOption, HiddenOption
from unrealsdk import find_object
from unrealsdk.unreal import UObject, UFunction, WrappedStruct
from unrealsdk.hooks import Type


# =====================================================
# Constants and global variables
# =====================================================
ANARCHY_PATH = "GD_Tulip_Mechromancer_Skills.EmbraceChaos.Anarchy"
RATIONAL_ANARCHIST_PATH = "GD_Tulip_Mechromancer_Skills.EmbraceChaos.RationalAnarchist"
ANARCHY_STACK_ATTR_PATH = "GD_Tulip_Mechromancer_Skills.Misc.Att_Anarchy_NumberOfStacks"
ANARCHY_MAX_STACK_ATTR_PATH = "GD_Tulip_Mechromancer_Skills.Misc.Att_Anarchy_StackCap"


@dataclass
class AnarchyState:
    save_file:str|None = None
    is_first_save:bool = False
    have_anarchy_skill:bool = False
    rational_anarchist_idx:int|None = None
    current_stacks:int = 0
    new_stacks:int = 0
    death_flag:bool = False
    ticks_until_apply:int = -1

    def __str__(self) -> str:
        lines = [f"{f.name}={getattr(self, f.name)}" for f in fields(self)]
        return "AnarchyState(\n  " + "\n  ".join(lines) + "\n)"


anarchy_state = AnarchyState()


# =====================================================
# Options
# =====================================================
option_use_rational_anarchist = BoolOption(
    identifier="Requires Rational Anarchist",
    value=True,
    description="Anarchy stack loss cap only applies if Rational Anarchist is invested.",
    true_text="Yes",
    false_text="No",
)


option_max_stacks_to_lose = SliderOption(
    identifier="Max stacks to lose on death",
    value=50,
    min_value=0,
    max_value=600,
    description="Maximum Anarchy stacks lost upon death.",
    step=5,
)


option_persist_anarchy = BoolOption(
    identifier="Persists on game quit",
    value=True,
    description="Save the anarchy stack when quit game and restore on load",
    true_text="Yes",
    false_text="No",
)


cache_persistent_anarchy_data = HiddenOption("persistent_anarchy_data", {})

debug_mode = HiddenOption("debug_mode", False)


# =====================================================
# Aux functions
# =====================================================
def debug_print(message:str) -> None:
    if not debug_mode.value:
        return
    print(message)


def get_skill_tree() -> list[dict]|None:
    pc = get_pc()
    if (pc.CharacterClass is not None) and (pc.PlayerSkillTree is not None):
        return pc.PlayerSkillTree.Skills
    elif (pc.GetCachedSaveGame() is not None):
        return pc.GetCachedSaveGame().SkillData
    return None


def have_anarchy_skill() -> bool:
    full_skill_tree = get_skill_tree()
    if full_skill_tree is None:
        return False
    for skill in full_skill_tree:
        if ANARCHY_PATH in str(skill.Definition):
            return True
    return False


def get_rational_anarchist_index() -> int|None:
    full_skill_tree = get_skill_tree()
    if full_skill_tree is None:
        return None
    for idx,skill in enumerate(full_skill_tree):
        if RATIONAL_ANARCHIST_PATH in str(skill.Definition):
            return idx
    return None


def have_point_in_rational_anarchist() -> bool:
    current_build = get_skill_tree()
    if (anarchy_state.rational_anarchist_idx is None) or (current_build is None):
        return False
    skill_grade = current_build[anarchy_state.rational_anarchist_idx].Grade
    return skill_grade > 0


def need_but_not_have_rational_anarchist() -> bool:
    return option_use_rational_anarchist.value and (not have_point_in_rational_anarchist())


def get_current_anarchy_stacks() -> int:
    return int(
        find_object(
            "DesignerAttributeDefinition",
            ANARCHY_STACK_ATTR_PATH
        )
        .GetValue(get_pc())[0]
    )


def get_max_anarchy_stacks() -> int:
    return int(
        find_object(
            "DesignerAttributeDefinition",
            ANARCHY_MAX_STACK_ATTR_PATH
        )
        .GetValue(get_pc())[0]
    )


def apply_new_anarchy_stacks() -> None:
    pc = get_pc()
    find_object(
        "DesignerAttributeDefinition",
        ANARCHY_STACK_ATTR_PATH
    ).SetAttributeBaseValue(pc, int(anarchy_state.new_stacks))
    anarchy_state.new_stacks = 0


def get_save_file() -> str:
    save_file = get_pc().GetWillowGlobals().GetWillowSaveGameManager().LastLoadedFilePath
    return save_file


def load_persistent_data() -> dict[str,int]:
    return cache_persistent_anarchy_data.value


def dump_persistent_data(anarchy_data:dict|None=None) -> None:
    if anarchy_state.save_file is None:
        return
    if anarchy_data is None:
        anarchy_data = load_persistent_data()
        anarchy_data[anarchy_state.save_file] = anarchy_state.current_stacks
    cache_persistent_anarchy_data.value = anarchy_data
    cache_persistent_anarchy_data.save()


# =====================================================
# Hooks
# =====================================================
@hook("WillowGame.PlayerSkillTree:Initialize", Type.PRE)
def on_initialize(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    debug_print("\nEvent: Initialize")
    anarchy_state.is_first_save = True
    debug_print(f"{anarchy_state}\n")
    return True


@hook("WillowGame.WillowPlayerController:SaveGame", Type.PRE)
def on_save_game(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    debug_print("\nEvent: SaveGame")
    if anarchy_state.is_first_save:
        anarchy_state.have_anarchy_skill = have_anarchy_skill()
        if not anarchy_state.have_anarchy_skill:
            return True
        anarchy_state.rational_anarchist_idx = get_rational_anarchist_index()
        anarchy_state.save_file = get_save_file()
        if option_persist_anarchy.value:
            anarchy_persist_data = load_persistent_data()
            anarchy_state.new_stacks = anarchy_persist_data.get(anarchy_state.save_file, 0)
            apply_new_anarchy_stacks()
            anarchy_persist_data.pop(anarchy_state.save_file, None)
            dump_persistent_data(anarchy_persist_data)
        anarchy_state.is_first_save = False
    if not anarchy_state.have_anarchy_skill:
        return True
    anarchy_state.current_stacks = get_current_anarchy_stacks()
    debug_print(f"{anarchy_state}\n")
    return True


@hook("WillowGame.WillowPlayerPawn:SetupPlayerInjuredState", Type.PRE)
def on_ffyl(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    if not anarchy_state.have_anarchy_skill:
        return True
    debug_print("\nEvent: FFYL")
    if need_but_not_have_rational_anarchist():
        return True
    anarchy_state.current_stacks = get_current_anarchy_stacks()
    debug_print(f"{anarchy_state}\n")
    return True


@hook("WillowGame.WillowPlayerPawn:StartInjuredDeathSequence", Type.PRE)
def on_death(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    if not anarchy_state.have_anarchy_skill:
        return True
    debug_print("\nEvent: Death")
    if need_but_not_have_rational_anarchist():
        return True
    anarchy_state.death_flag = True
    debug_print(f"{anarchy_state}\n")
    return True


def on_tick(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    if anarchy_state.ticks_until_apply < 0:
        ON_TICK_HOOK.disable()
        return True
    if (anarchy_state.ticks_until_apply < 1) and (anarchy_state.new_stacks > 0):
        debug_print("\nEvent: Tick")
        apply_new_anarchy_stacks()
        anarchy_state.current_stacks = get_current_anarchy_stacks()
        debug_print(f"{anarchy_state}\n")
    anarchy_state.ticks_until_apply -= 1
    return True

ON_TICK_HOOK = HookType(
    on_tick,
    hook_identifier="on_tick_post_respawn",
    hook_funcs=[("WillowGame.WillowPlayerController:PlayerTick", Type.POST)]
)


@hook("WillowGame.SkillEffectManager:NotifySkillEvent", Type.POST_UNCONDITIONAL)
def on_respawn(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    if (not anarchy_state.have_anarchy_skill) or (not anarchy_state.death_flag):
        return True
    debug_print("\nEvent: Respawn")
    try:
        event_type = int(caller_params.EventType)
        event_instigator = caller_params.EventInstigator
    except Exception as exp:
        debug_print(f"Exception checking event: {exp}")
        return True
    debug_print(f"Event parameters: {event_type=} {event_instigator=}")
    if (event_type != 34) or (event_instigator != get_pc()):
        return True
    anarchy_state.death_flag = False
    if need_but_not_have_rational_anarchist():
        return True
    new_stacks = max(anarchy_state.current_stacks - option_max_stacks_to_lose.value, 0)
    new_stacks = 0 if have_point_in_rational_anarchist() and (new_stacks < 25) else new_stacks
    max_stacks = get_max_anarchy_stacks()
    anarchy_state.new_stacks = min(new_stacks, max_stacks)
    anarchy_state.current_stacks = 0
    anarchy_state.ticks_until_apply = 600
    ON_TICK_HOOK.enable()
    debug_print(f"{max_stacks=}\n {anarchy_state}\n")
    return True


@hook("WillowGame.WillowPlayerController:ReturnToTitleScreen", Type.PRE)
def on_quit(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    debug_print("\nEvent: Quit")
    if (not anarchy_state.have_anarchy_skill) or (not option_persist_anarchy.value):
        return True
    anarchy_state.current_stacks = get_current_anarchy_stacks()
    if anarchy_state.current_stacks > 0:
        dump_persistent_data()
    debug_print(f"{anarchy_state}\n")
    return True


# =====================================================
# Mod register
# =====================================================
mod = build_mod(
    options=[
        option_max_stacks_to_lose,
        option_use_rational_anarchist,
        option_persist_anarchy,
        cache_persistent_anarchy_data,
        debug_mode,
    ]
)

