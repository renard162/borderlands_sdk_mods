import json

from mods_base import get_pc, hook, HookType
from unrealsdk import find_object


def dbg_get_att(obj):
    output_dict = {'methods':[], 'properties':[], 'error':[]}

    for name in dir(obj):
        if name.startswith("_"):
            continue

        try:
            attr = getattr(obj, name)
        except Exception as err:
            output_dict['error'].append({name:str(err)})
            continue

        if callable(attr):
            output_dict['methods'].append(name)
        else:
            output_dict['properties'].append(name)

    return output_dict


def dbg_dump_att(obj, dump_address=None):
    if dump_address is None:
        dump_address = r'D:\debug.json'

    obj_attributes = dbg_get_att(obj)
    with open(dump_address, 'w') as j:
        json.dump(obj_attributes, j)

