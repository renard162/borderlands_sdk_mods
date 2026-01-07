from dataclasses import dataclass, fields
from pathlib import Path
import json
from json import JSONDecodeError

from mods_base import build_mod, get_pc, hook, SliderOption, BoolOption
from unrealsdk import find_object
from unrealsdk.unreal import UObject, UFunction, WrappedStruct
from unrealsdk.hooks import Type


DEBUG_MODE = True


# =====================================================
# Constants
# =====================================================
MOD_NAME = Path(__file__).resolve().parent.name
PERSIST_JSON = Path(__file__).resolve().parent.parent.parent / "settings" / f"{MOD_NAME}_persist.json"
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

    def __str__(self) -> str:
        lines = [f"{f.name}={getattr(self, f.name)}" for f in fields(self)]
        return "AnarchyState(\n  " + "\n  ".join(lines) + "\n)"


anarchy_state = AnarchyState()


# =====================================================
# Aux functions
# =====================================================
def debug_log(message:str):
    if not DEBUG_MODE:
        return
    with open(r"D:\temp\log.log", "a", encoding="utf-8") as f:
        f.write(f"{message}\n")

    
def debug_print(message:str):
    if not DEBUG_MODE:
        return
    print(message)


def get_skill_tree() -> list[dict]|None:
    pc = get_pc()
    if (pc.CharacterClass is not None) and (pc.PlayerSkillTree is not None):
        return pc.PlayerSkillTree.Skills
    elif (pc.GetCachedSaveGame() is not None):
        return pc.GetCachedSaveGame().SkillData
    return None


def have_anarchy_skill():
    full_skill_tree = get_skill_tree()
    if full_skill_tree is None:
        return False
    for idx,skill in enumerate(full_skill_tree):
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


def need_but_not_have_rational_anarchist():
    return option_use_rational_anarchist.value and (not have_point_in_rational_anarchist())


def get_current_anarchy_stacks():
    return int(
        find_object(
            "DesignerAttributeDefinition",
            ANARCHY_STACK_ATTR_PATH
        )
        .GetValue(get_pc())[0]
    )


def get_max_anarchy_stacks():
    return int(
        find_object(
            "DesignerAttributeDefinition",
            ANARCHY_MAX_STACK_ATTR_PATH
        )
        .GetValue(get_pc())[0]
    )


def apply_new_anarchy_stacks():
    pc = get_pc()
    find_object(
        "DesignerAttributeDefinition",
        ANARCHY_STACK_ATTR_PATH
    ).SetAttributeBaseValue(pc, int(anarchy_state.new_stacks))
    anarchy_state.new_stacks = 0


def get_save_file():
    save_file = get_pc().GetWillowGlobals().GetWillowSaveGameManager().LastLoadedFilePath
    return save_file


def load_json_data():
    try:
        with open(PERSIST_JSON, "r", encoding="utf-8") as j:
            json_data = json.load(j)
    except (FileNotFoundError, JSONDecodeError):
        json_data = {}
    return json_data


def dump_json_data(json_data:dict|None=None):
    if anarchy_state.save_file is None:
        return
    if json_data is None:
        json_data = load_json_data()
        json_data[anarchy_state.save_file] = anarchy_state.current_stacks
        debug_print(f"{json_data=}")
    try:
        with open(PERSIST_JSON, "w", encoding="utf-8") as j:
            json.dump(json_data, j, indent=4)
    except Exception as exp:
        print(f"AnarchyDeathCap error: {exp}")


# =====================================================
# Options
# =====================================================
@BoolOption(
    identifier="Requires Rational Anarchist",
    value=True,
    description="Anarchy stack loss cap only applies if Rational Anarchist is invested.",
    true_text="Yes",
    false_text="No",
)
def option_use_rational_anarchist(opt:BoolOption, new_value:bool) -> None:
    opt.value = new_value


@SliderOption(
    identifier="Max stacks to lose",
    value=50,
    min_value=0,
    max_value=600,
    description="Maximum Anarchy stacks lost upon death.",
    step=10,
)
def option_max_stacks_to_lose(opt:SliderOption, new_value:float) -> None:
    opt.value = int(new_value)


@BoolOption(
    identifier="Persists on game quit",
    value=True,
    description="Save the anarchy stack when quit game and restore on load",
    true_text="Yes",
    false_text="No",
)
def option_persist_anarchy(opt:BoolOption, new_value:bool) -> None:
    opt.value = new_value


# =====================================================
# Hooks
# =====================================================
ON_INITIALIZE_HOOK = ("WillowGame.PlayerSkillTree:Initialize", Type.PRE)
@hook(*ON_INITIALIZE_HOOK)
def on_initialize(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    debug_print(f"\nEvent: Initialize\nHook: {ON_INITIALIZE_HOOK[0][11:]}, {ON_INITIALIZE_HOOK[1]}")
    anarchy_state.is_first_save = True
    debug_print(f"{anarchy_state}\n")
    return True


ON_SAVE_HOOK = ("WillowGame.WillowPlayerController:SaveGame", Type.PRE)
@hook(*ON_SAVE_HOOK)
def on_save_game(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    debug_print(f"\nEvent: SaveGame\nHook: {ON_SAVE_HOOK[0][11:]}, {ON_SAVE_HOOK[1]}")
    if anarchy_state.is_first_save:
        anarchy_state.have_anarchy_skill = have_anarchy_skill()
        if not anarchy_state.have_anarchy_skill:
            return True
        anarchy_state.rational_anarchist_idx = get_rational_anarchist_index()
        anarchy_state.save_file = get_save_file()
        if option_persist_anarchy.value:
            anarchy_persist_data = load_json_data()
            anarchy_state.new_stacks = anarchy_persist_data.get(anarchy_state.save_file, 0)
            apply_new_anarchy_stacks()
            anarchy_persist_data.pop(anarchy_state.save_file, None)
            dump_json_data(anarchy_persist_data)
        anarchy_state.is_first_save = False
    if not anarchy_state.have_anarchy_skill:
        return True
    anarchy_state.current_stacks = get_current_anarchy_stacks()
    debug_print(f"{anarchy_state}\n")
    return True


ON_FFYL_HOOK = ("WillowGame.WillowPlayerPawn:SetupPlayerInjuredState", Type.PRE)
@hook(*ON_FFYL_HOOK)
def on_ffyl(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    if not anarchy_state.have_anarchy_skill:
        return True
    debug_print(f"\nEvent: FFYL\nHook: {ON_FFYL_HOOK[0][11:]}, {ON_FFYL_HOOK[1]}")
    if need_but_not_have_rational_anarchist():
        return True
    anarchy_state.current_stacks = get_current_anarchy_stacks()
    debug_print(f"{anarchy_state}\n")
    return True


ON_DEATH_HOOK = ("WillowGame.WillowPlayerPawn:StartInjuredDeathSequence", Type.PRE)
@hook(*ON_DEATH_HOOK)
def on_death(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    if not anarchy_state.have_anarchy_skill:
        return True
    debug_print(f"\nEvent: Death\nHook: {ON_DEATH_HOOK[0][11:]}, {ON_DEATH_HOOK[1]}")
    if need_but_not_have_rational_anarchist():
        return True
    anarchy_state.death_flag = True
    debug_print(f"{anarchy_state}\n")
    return True


ON_RESPAWN_HOOK = ("WillowGame.SkillEffectManager:NotifySkillEvent", Type.POST_UNCONDITIONAL)
@hook(*ON_RESPAWN_HOOK)
def on_respawn(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    if (not anarchy_state.have_anarchy_skill) or (not anarchy_state.death_flag):
        return True
    debug_print(f"\nEvent: Respawn\nHook: {ON_RESPAWN_HOOK[0][11:]}, {ON_RESPAWN_HOOK[1]}")
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
    max_stacks = get_max_anarchy_stacks()
    anarchy_state.new_stacks = min(new_stacks, max_stacks)
    apply_new_anarchy_stacks()
    anarchy_state.current_stacks = get_current_anarchy_stacks()
    debug_print(f"{max_stacks=}\n {anarchy_state}\n")
    return True


ON_QUIT_HOOK = ("WillowGame.WillowPlayerController:ReturnToTitleScreen", Type.PRE)
@hook(*ON_QUIT_HOOK)
def on_quit(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    debug_print(f"\nEvent: Quit\nHook: {ON_QUIT_HOOK[0][11:]}, {ON_QUIT_HOOK[1]}")
    if (not anarchy_state.have_anarchy_skill) or (not option_persist_anarchy.value):
        return True
    anarchy_state.current_stacks = get_current_anarchy_stacks()
    if anarchy_state.current_stacks > 0:
        dump_json_data()
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
    ]
)

