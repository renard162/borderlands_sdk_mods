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
    current_stacks:int = 0
    new_stacks:int = 0
    death_flag:bool = False
    ticks_until_apply:int = -1

    def __str__(self) -> str:
        lines = [f"{f.name}={getattr(self, f.name)}" for f in fields(self)]
        return "AnarchyState(\n  " + "\n  ".join(lines) + "\n)"


@dataclass
class RationalAnarchistState:
    idx:int|None = None
    base_description:str|None = None
    extra_description:str|None = None
    

anarchy_state = AnarchyState()
rational_anarchist = RationalAnarchistState()


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
    set_rational_anarchist_description()


@SliderOption(
    identifier="Max stacks to lose on death",
    value=50,
    min_value=0,
    max_value=600,
    description="Maximum Anarchy stacks lost upon death.",
    step=5,
)
def option_max_stacks_to_lose(opt:SliderOption, new_value:float) -> None:
    opt.value = int(new_value)
    set_rational_anarchist_description()


option_persist_anarchy = BoolOption(
    identifier="Persists on game quit",
    value=True,
    description="Save the anarchy stack when quit game and restore on load",
    true_text="Yes",
    false_text="No",
)


cache_persistent_anarchy_data = HiddenOption("persistent_anarchy_data", {})


# =====================================================
# General functions
# =====================================================
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
    if (rational_anarchist.idx is None) or (current_build is None):
        return False
    skill_grade = current_build[rational_anarchist.idx].Grade
    return skill_grade > 0


def have_rational_anarchist_skill() -> bool:
    return rational_anarchist.idx is not None


def need_but_not_have_rational_anarchist() -> bool:
    return option_use_rational_anarchist.value and (not have_point_in_rational_anarchist())


# =====================================================
# Anarchy stacks functions
# =====================================================
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


# =====================================================
# Persistent stacks functions
# =====================================================
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
# Rational Anarchist description functions
# =====================================================
def get_rational_anarchist_object() -> UObject|None:
    try:
        return find_object(
                "SkillDefinition",
                RATIONAL_ANARCHIST_PATH
            )
    except Exception:
        return None


def get_rational_anarchist_base_description(skill:UObject|None=None) -> None:
    if skill is None:
        skill = get_rational_anarchist_object()
    if (skill is not None) and (rational_anarchist.base_description is None):
        rational_anarchist.base_description = skill.SkillDescription


def reset_rational_anarchist_extra_description() -> None:
    rational_anarchist.extra_description = None


def set_rational_anarchist_extra_description() -> None:
    if not option_use_rational_anarchist.value:
        reset_rational_anarchist_extra_description()
        return
    if option_max_stacks_to_lose.value == 0:
        rational_anarchist.extra_description = "Additionally, you no longer lose stacks of [skill]Anarchy[-skill] when you die."
        return
    max_stacks_to_lose = option_max_stacks_to_lose.value
    rational_anarchist.extra_description = (
        f"You lose no more than {max_stacks_to_lose} [skill]Anarchy[-skill] stacks upon death. "
       + "If this would reduce your [skill]Anarchy[-skill] stacks below 25, they are instead reset to zero."
    )


def update_rational_anarchist_description() -> None:
    if not have_rational_anarchist_skill():
        return
    skill = get_rational_anarchist_object()
    get_rational_anarchist_base_description(skill)
    if rational_anarchist.extra_description is None:
        skill.SkillDescription = rational_anarchist.base_description
        return
    skill.SkillDescription = f"{rational_anarchist.base_description} {rational_anarchist.extra_description}"


def set_rational_anarchist_description() -> None:
    set_rational_anarchist_extra_description()
    update_rational_anarchist_description()


def reset_rational_anarchist_description() -> None:
    reset_rational_anarchist_extra_description()
    update_rational_anarchist_description()


# =====================================================
# Hooks
# =====================================================
@hook("WillowGame.PlayerSkillTree:Initialize", Type.PRE)
def on_initialize(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    anarchy_state.is_first_save = True
    return True


@hook("WillowGame.WillowPlayerController:SaveGame", Type.PRE)
def on_save_game(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    if anarchy_state.is_first_save:
        anarchy_state.have_anarchy_skill = have_anarchy_skill()
        if not anarchy_state.have_anarchy_skill:
            return True
        rational_anarchist.idx = get_rational_anarchist_index()
        anarchy_state.save_file = get_save_file()
        set_rational_anarchist_description()
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
    return True


@hook("WillowGame.WillowPlayerPawn:SetupPlayerInjuredState", Type.PRE)
def on_ffyl(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    if not anarchy_state.have_anarchy_skill:
        return True
    if need_but_not_have_rational_anarchist():
        return True
    anarchy_state.current_stacks = get_current_anarchy_stacks()
    return True


@hook("WillowGame.WillowPlayerPawn:StartInjuredDeathSequence", Type.PRE)
def on_death(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    if not anarchy_state.have_anarchy_skill:
        return True
    if need_but_not_have_rational_anarchist():
        return True
    anarchy_state.death_flag = True
    return True


def on_tick(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    if anarchy_state.ticks_until_apply < 0:
        ON_TICK_HOOK.disable()
        return True
    if (anarchy_state.ticks_until_apply < 1) and (anarchy_state.new_stacks > 0):
        apply_new_anarchy_stacks()
        anarchy_state.current_stacks = get_current_anarchy_stacks()
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
    try:
        event_type = int(caller_params.EventType)
        event_instigator = caller_params.EventInstigator
    except Exception:
        return True
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
    return True


@hook("WillowGame.WillowPlayerController:ReturnToTitleScreen", Type.PRE)
def on_quit(caller_obj:UObject, caller_params:WrappedStruct, function_return:object, function:UFunction) -> bool:
    if (not anarchy_state.have_anarchy_skill) or (not option_persist_anarchy.value):
        return True
    anarchy_state.current_stacks = get_current_anarchy_stacks()
    if anarchy_state.current_stacks > 0:
        dump_persistent_data()
    return True


# =====================================================
# Mod register
# =====================================================
mod = build_mod(
    on_enable=set_rational_anarchist_description,
    on_disable=reset_rational_anarchist_description,
    options=[
        option_max_stacks_to_lose,
        option_use_rational_anarchist,
        option_persist_anarchy,
        cache_persistent_anarchy_data,
    ]
)

